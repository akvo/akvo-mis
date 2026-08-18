import os
from typing import cast
import requests
import mimetypes
from rest_framework.request import Request

from rest_framework.viewsets import ModelViewSet
from api.v1.v1_mobile.authentication import (
    IsMobileAssignment,
    MobileAssignmentToken,
)
from mis.settings import (
    MASTER_DATA,
    BASE_DIR,
    APK_UPLOAD_SECRET,
    APK_SHORT_NAME,
    WEBDOMAIN,
)
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, Prefetch

from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)

from utils.custom_pagination import Pagination
from .serializers import (
    MobileAssignmentFormsSerializer,
    MobileApkSerializer,
    MobileAssignmentListRequestSerializer,
    MobileAssignmentSerializer,
    MobileDataPointDownloadListSerializer,
    SyncDeviceFormDataSerializer,
    SyncDeviceParamsSerializer,
    DraftFormDataSerializer,
)
from .models import MobileAssignment, MobileApk
from api.v1.v1_forms.models import Forms, Questions, QuestionTypes
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.serializers import WebFormDetailSerializer
from api.v1.v1_data.serializers import (
    SubmitPendingFormSerializer,
    SubmitUpdateDraftFormSerializer,
)
from api.v1.v1_files.serializers import (
    UploadImagesSerializer,
    AttachmentsSerializer,
)
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_profile.models import Administration, Entity, EntityData
from api.v1.v1_users.models import Organisation
from utils.custom_generator import generate_sqlite, sqlite_path
from api.v1.v1_files.functions import handle_upload
from utils.custom_helper import CustomPasscode
from utils.default_serializers import DefaultResponseSerializer
from utils.custom_serializer_fields import (
    validate_serializers_message,
)
from utils import storage

apk_path = os.path.join(BASE_DIR, MASTER_DATA)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="keep_last_synced_at",
            required=False,
            default=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description=(
                "Whether to keep the existing last_synced_at value "
                "for the assignment. "
                "If false or not provided, "
                "last_synced_at will be reset to None, "
                "causing all datapoints to be returned. "
                "If true, last_synced_at will not be modified, "
                "and only datapoints created/updated "
                "after the existing last_synced_at will be returned."
            ),
        )
    ],
    request=MobileAssignmentFormsSerializer,
    responses={200: MobileAssignmentFormsSerializer},
    tags=["Mobile Device Form"],
    summary="To get list of mobile forms",
    description="To get list of mobile forms",
)
@api_view(["POST"])
def get_mobile_forms(request, version):
    code = request.data.get("code")
    serializer = MobileAssignmentFormsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        passcode = CustomPasscode().encode(code)
        mobile_assignment = MobileAssignment.objects.get(passcode=passcode)
        keep_last_synced_at = request.query_params.get(
            "keep_last_synced_at", "false"
        ).lower() == "true"
        if not keep_last_synced_at:
            mobile_assignment.last_synced_at = None
        mobile_assignment.save()
    except MobileAssignment.DoesNotExist:
        return Response(
            {"error": "Mobile Assignment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = MobileAssignmentFormsSerializer(mobile_assignment)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: WebFormDetailSerializer},
    tags=["Mobile Device Form"],
    summary="To get form in mobile form format",
)
@api_view(["GET"])
@permission_classes([IsMobileAssignment])
def get_mobile_form_details(request: Request, version, form_id):
    assignment = cast(MobileAssignmentToken, request.auth).assignment
    instance = get_object_or_404(
        Forms.objects.for_user(assignment.user), pk=form_id
    )
    data = WebFormDetailSerializer(
        instance=instance,
        context={
            "user": assignment.user,
            "mobile_assignment": assignment,
        },
    ).data
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    request=SyncDeviceFormDataSerializer,
    responses={200: DefaultResponseSerializer},
    tags=["Mobile Device Form"],
    parameters=[
        OpenApiParameter(
            name="is_draft",
            required=False,
            default=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="is_published",
            required=False,
            default=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="id",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
    ],
    summary="Submit pending form data",
)
@api_view(["POST"])
@permission_classes([IsMobileAssignment])
def sync_pending_form_data(request, version):
    params = SyncDeviceParamsSerializer(
        data=request.GET
    )
    if not params.is_valid():
        return Response(
            {
                "message": validate_serializers_message(params.errors)
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    assignment = cast(MobileAssignmentToken, request.auth).assignment
    form = get_object_or_404(
        Forms.objects.for_user(assignment.user),
        pk=request.data.get("formId"),
    )
    user = assignment.user
    administration = assignment.administrations.order_by(
        "level__level"
    ).first()
    if user.user_user_role.exists():
        user_role = user.user_user_role.filter(
            role__role_role_access__data_access=DataAccessTypes.submit
        ).first()
        if user_role:
            # If user has a role with data access, use that administration
            administration = user_role.administration

    is_draft = params.validated_data["is_draft"]
    # Allow empty answers for drafts only
    if not request.data.get("answers") and not is_draft:
        return Response(
            {"message": "Answers is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    answers = []
    qna = request.data.get("answers") or {}
    adm_id = administration.id
    adm_qs = Questions.objects.filter(
        type=QuestionTypes.cascade, form_id=form.id
    ).filter(
        Q(extra__isnull=True) | ~Q(extra__type__in=["entity"])
    ).order_by("order").first()
    adm_key = str(adm_qs.id) if adm_qs else None
    if adm_key and adm_key in qna:
        adm_id = qna[adm_key]
    # Handle repeat question values with indexes
    for q_key in list(qna):
        """
        Extract the base question ID from the key
        Keys can be like "1" or "1-1" or "1-2"
        where the base question ID is "1"
        """
        index = 0
        if '-' in str(q_key):
            [base_q_id, q_index] = str(q_key).split('-')
            index = q_index
        else:
            base_q_id = str(q_key)
        answers.append({
            "question": base_q_id,
            "value": qna[q_key],
            "index": index,
        })
    payload = {
        "administration": adm_id,
        "name": request.data.get("name"),
        "geo": request.data.get("geo"),
        "submitter": assignment.name,
        "duration": request.data.get("duration"),
    }
    if request.data.get("uuid"):
        payload["uuid"] = request.data["uuid"]
    if request.data.get("submission_key"):
        payload["submission_key"] = request.data["submission_key"]
    data = {
        "data": payload,
        "answer": answers,
    }
    serializer = SubmitPendingFormSerializer(
        data=data,
        context={
            "user": user,
            "form": form,
            "is_draft": is_draft,
        }
    )
    draft_exists = FormData.objects_draft.filter(
        form=form,
        created_by=user,
        uuid=request.data.get("uuid"),
        form__parent__isnull=True,
    ).first()
    if params.validated_data.get("id"):
        draft_exists = params.validated_data.get("id")
    if draft_exists:
        serializer = SubmitUpdateDraftFormSerializer(
            instance=draft_exists,
            data=data,
            context={
                "user": user,
                "form": form,
                "is_draft": is_draft,
            }
        )
    if not serializer.is_valid():
        return Response(
            {
                "message": validate_serializers_message(serializer.errors),
                "details": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    instance = serializer.save()
    is_published = request.GET.get("is_published", False)
    is_published = True if is_published in ["true", "True", "1"] else False
    if is_published and draft_exists:
        draft_exists.publish()
        direct_to_data = user.is_superuser or not draft_exists.has_approval
        if direct_to_data and not draft_exists.parent:
            draft_exists.save_to_file

    # The id lets the device store the backend identity of a draft right
    # after its first upload, so the next save syncs as ?id=<draft> instead
    # of creating a duplicate (the uuid fallback cannot match child forms).
    return Response(
        {"message": "ok", "id": instance.id},
        status=status.HTTP_200_OK,
    )


# The device asks for a logical table name; the tenant it resolves to comes
# from its own token, never from the URL. Mapping the name to a model rather
# than joining it onto a path also retires the traversal that the old raw
# os.path.join(file_name) allowed.
MASTER_DATA_MODELS = {
    "administrator": Administration,
    "organisation": Organisation,
    "entities": Entity,
    "entity_data": EntityData,
}


@extend_schema(tags=["Mobile Device Form"], summary="Get SQLITE File")
@api_view(["GET"])
@permission_classes([IsMobileAssignment])
def download_sqlite_file(request, version, file_name):
    model = MASTER_DATA_MODELS.get(file_name[: -len(".sqlite")])
    if not file_name.endswith(".sqlite") or model is None:
        return Response(
            {"message": "File not found."}, status=status.HTTP_404_NOT_FOUND
        )

    assignment = cast(MobileAssignmentToken, request.auth).assignment
    tenant = assignment.user.tenant
    file_path = sqlite_path(model, tenant=tenant)
    # Generated lazily: a tenant that registered after the last run of the
    # generate_sqlite command has no file yet, and a device asking for it is
    # exactly the moment we know it is needed.
    if not os.path.exists(file_path):
        generate_sqlite(model, tenant=tenant)

    content_type, _ = mimetypes.guess_type(file_path)
    with open(file_path, "rb") as file:
        file_content = file.read()

    response = HttpResponse(file_content, content_type=content_type)
    response["Content-Length"] = os.path.getsize(file_path)
    response["Content-Disposition"] = "attachment; filename=%s" % file_name
    return response


@extend_schema(
    tags=["Mobile Device Form"],
    summary="Upload Images from Device",
    request=UploadImagesSerializer,
    responses={
        (200, "application/json"): inline_serializer(
            "UploadImagesFromDevice",
            fields={
                "message": serializers.CharField(),
                "file": serializers.CharField(),
            },
        )
    },
)
@api_view(["POST"])
@permission_classes([IsMobileAssignment])
@parser_classes([MultiPartParser])
def upload_image_form_device(request, version):
    serializer = UploadImagesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            validate_serializers_message(serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )
    filename = handle_upload(request=request, folder="images")
    return Response(
        {
            "message": "File uploaded successfully",
            "file": f"{WEBDOMAIN}/images/{filename}",
        },
        status=status.HTTP_200_OK,
    )


class UploadAttachmentsView(APIView):
    permission_classes = [IsMobileAssignment]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Mobile Device Form"],
        summary="Upload Attachments from Device",
        request=AttachmentsSerializer,
        parameters=[
            OpenApiParameter(
                name="allowed_file_types",
                required=False,
                location=OpenApiParameter.QUERY,
                description=(
                    "List of allowed file types for the attachment. "
                ),
                type={"type": "array", "items": {"type": "string"}},
                enum=[
                    "pdf", "docx", "xlsx", "pptx", "txt", "csv", "zip", "rar",
                    "jpg", "jpeg", "png", "gif", "bmp", "doc", "xls", "ppt",
                    "mp4", "avi", "mov", "mkv", "flv", "wmv", "mp3", "wav",
                    "ogg", "flac", "aac", "wma", "m4a", "opus", "webm", "3gp",
                ],
            )
        ],
        responses={
            (200, "application/json"): inline_serializer(
                "UploadAttachmentsFromDevice",
                fields={
                    "message": serializers.CharField(),
                    "file": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request, version):
        allowed_file_types = request.GET.getlist("allowed_file_types")
        serializer = AttachmentsSerializer(
            data=request.data,
            context={
                "allowed_file_types": allowed_file_types,
            },
        )
        if not serializer.is_valid():
            return Response(
                validate_serializers_message(serializer.errors),
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:

            filename = handle_upload(request=request, folder="attachments")
            return Response(
                {
                    "message": "File uploaded successfully",
                    "file": f"{WEBDOMAIN}/attachments/{filename}",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "message": "File upload failed.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(tags=["Mobile APK"], summary="Get APK File")
@api_view(["GET"])
def download_apk_file(request, version):
    apk = MobileApk.objects.last()
    if not apk:
        return Response(
            {"message": "APK not found."}, status=status.HTTP_404_NOT_FOUND
        )
    file_name = f"{APK_SHORT_NAME}-{apk.apk_version}.apk"
    cache_file_name = os.path.join(apk_path, file_name)
    if os.path.exists(cache_file_name):
        # Get the file's content type
        content_type, _ = mimetypes.guess_type(cache_file_name)
        # Read the file content into a variable
        with open(cache_file_name, "rb") as file:
            file_content = file.read()
        # Create the response and set the appropriate headers
        response = HttpResponse(file_content, content_type=content_type)
        response["Content-Length"] = os.path.getsize(cache_file_name)
        response["Content-Disposition"] = (
            "attachment; filename=%s" % f"{file_name}"
        )
        return response
    download = requests.get(apk.apk_url)
    if download.status_code != 200:
        return HttpResponse(
            {"message": "File not found."}, status=status.HTTP_404_NOT_FOUND
        )
    file_cache = open(cache_file_name, "wb")
    file_cache.write(download.content)
    file_cache.close()
    # Get the file's content type
    content_type, _ = mimetypes.guess_type(cache_file_name)
    # Read the file content into a variable
    with open(cache_file_name, "rb") as file:
        file_content = file.read()
    # Read the file content into a variable
    response = HttpResponse(file_content, content_type=content_type)
    response["Content-Length"] = os.path.getsize(cache_file_name)
    response["Content-Disposition"] = (
        "attachment; filename=%s" % f"{file_name}"
    )
    return response


@extend_schema(tags=["Mobile APK"], summary="Check APK Version")
@api_view(["GET"])
def check_apk_version(request, version, current_version):
    apk = MobileApk.objects.last()
    if not apk or apk.apk_version <= current_version:
        return Response(
            {"message": "No update found."}, status=status.HTTP_404_NOT_FOUND
        )
    return Response({"version": apk.apk_version}, status=status.HTTP_200_OK)


@extend_schema(
    request=inline_serializer(
        name="UploadAPKFile",
        fields={
            "apk_url": serializers.FileField(),
            "apk_version": serializers.CharField(),
            "secret": serializers.CharField(),
        },
    ),
    tags=["Mobile APK"],
    summary="Post APK File",
)
@api_view(["POST"])
def upload_apk_file(request, version):
    if request.data.get("secret") != APK_UPLOAD_SECRET:
        return Response(
            {"message": "Secret is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = MobileApkSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )
    apk_version = serializer.validated_data.get("apk_version")
    download = requests.get(
        request.data.get("apk_url"), allow_redirects=True, stream=True
    )
    if download.status_code != 200:
        return HttpResponse(
            {"message": "File not found."}, status=status.HTTP_404_NOT_FOUND
        )
    filename = f"{APK_SHORT_NAME}-{apk_version}.apk"
    cache_file_name = os.path.join(apk_path, filename)
    file_cache = open(cache_file_name, "wb")
    file_cache.write(download.content)
    file_cache.close()
    storage.upload(
        cache_file_name, folder="apk",
        filename=f"{APK_SHORT_NAME}.apk"
    )
    serializer.save()
    return Response({"message": "ok"}, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Mobile Assignment"])
class MobileAssignmentViewSet(ModelViewSet):
    serializer_class = MobileAssignmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by name or email (case-insensitive)",
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        serializer = MobileAssignmentListRequestSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._validated_search = (
            serializer.validated_data.get("search") or None
        )
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        search = getattr(self, "_validated_search", None)
        mobile_users = MobileAssignment.objects.for_user(
            user
        ).prefetch_related("administrations", "forms").filter(user=user)
        adm_q = Q()
        if user.is_superuser:
            adm = Administration.objects.for_user(user).filter(
                parent__isnull=True
            ).first()
            adm_q = Q(
                administrations__path__startswith=f"{adm.id}."
            )
        for ur in user.user_user_role.filter(
            role__role_role_access__data_access=DataAccessTypes.submit
        ).all():
            adm = ur.administration
            path = f"{adm.path}{adm.id}." \
                if adm.path else f"{adm.id}."
            adm_q |= Q(administrations__path__startswith=path)
        if adm_q:
            descendant_users = MobileAssignment.objects.for_user(
                user
            ).prefetch_related(
                "administrations", "forms"
            ).filter(adm_q)
            mobile_users |= descendant_users
        qs = mobile_users.order_by("-id").distinct()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(user__email__icontains=search)
            )
        return qs


@extend_schema(
    responses={
        (200, "application/json"): inline_serializer(
            "FormsTreeResponse",
            fields={
                "id": serializers.IntegerField(),
                "name": serializers.CharField(),
                "type": serializers.CharField(),
                "children": serializers.ListField(
                    child=inline_serializer(
                        "FormsTreeChildResponse",
                        fields={
                            "id": serializers.IntegerField(),
                            "name": serializers.CharField(),
                            "type": serializers.CharField(),
                        },
                    )
                ),
            },
            many=True,
        )
    },
    tags=["Mobile Assignment"],
    summary="Get forms in tree structure for assignment selection",
    description=(
        "Returns published forms in a hierarchical tree structure "
        "with registration forms as parents and monitoring forms as children. "
        "Used for the mobile assignment form selection UI."
    ),
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_forms_tree(request, version):
    """Returns published forms in tree structure for assignment UI."""
    # Both the outer query and the children prefetch go through for_user:
    # scoping only the parents would still surface another tenant's
    # monitoring forms under a same-named registration form.
    registration_forms = Forms.objects.for_user(request.user).filter(
        parent__isnull=True,
        status=FormStatus.published
    ).prefetch_related(
        Prefetch(
            "children",
            queryset=Forms.objects.for_user(request.user).filter(
                status=FormStatus.published
            ).order_by("name")
        )
    ).order_by("name")

    result = []
    for reg in registration_forms:
        result.append({
            "id": reg.id,
            "name": reg.name,
            "type": "registration",
            "children": [
                {"id": m.id, "name": m.name, "type": "monitoring"}
                for m in reg.children.all()
            ]
        })
    return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    # Add form_id as query parameter for
    # filtering datapoints related to a specific form
    parameters=[
        OpenApiParameter(
            name="form_id",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        )
    ],
    responses={
        (200, "application/json"): inline_serializer(
            "MobileDeviceDownloadDatapointListResponse",
            fields={
                "total": serializers.IntegerField(),
                "data": MobileDataPointDownloadListSerializer(many=True),
                "page": serializers.IntegerField(),
                "current": serializers.IntegerField(),
            },
        )
    },
    tags=["Mobile Device Form"],
    summary="GET Download List for Syncing Datapoints",
)
@api_view(["GET"])
@permission_classes([IsMobileAssignment])
def get_datapoint_download_list(request, version):
    assignment = cast(MobileAssignmentToken, request.auth).assignment
    forms = assignment.forms.values("id")
    administrations = [
        {
            "id": a.id,
            "path": f"{a.path}{a.id}." if a.path else f"{a.id}."
        }
        for a in assignment.administrations.all()
    ]
    paginator = Pagination()

    # Start with base query for administration IDs
    form_id = request.GET.get("form_id")
    if form_id:
        find_form = Forms.objects.filter(
            id=form_id,
            parent__isnull=True,
        ).first()
        if not find_form or find_form.id not in [f["id"] for f in forms]:
            return Response(
                {"message": "Form not found in this assignment."},
                status=status.HTTP_404_NOT_FOUND,
            )
        forms = [find_form.pk]
    admin_id_query = Q(
        administration_id__in=[a["id"] for a in administrations],
        form_id__in=forms,
    )
    # Build path query by combining conditions for all administration paths
    path_query = Q()
    for admin in administrations:
        path_query |= Q(
            administration__path__startswith=admin["path"]
        )
    # Combine both queries with the form filter
    queryset = FormData.objects.for_user(assignment.user).filter(
        admin_id_query | (path_query & Q(form_id__in=forms))
    )
    if assignment.last_synced_at:
        queryset = queryset.filter(
            Q(created__gte=assignment.last_synced_at)
            | Q(updated__gte=assignment.last_synced_at)
        )

    queryset = queryset.filter(
        is_pending=False,
        is_draft=False,
    )
    queryset = queryset.values(
        "uuid",
        "id",
        "form_id",
        "name",
        "administration_id",
        "created",
        "updated",
    ).order_by("-created")

    instance = paginator.paginate_queryset(queryset, request)
    response = paginator.get_paginated_response(
        MobileDataPointDownloadListSerializer(instance, many=True).data
    )
    page = response.data["current"]
    total_page = response.data["total_page"]
    if page == total_page and not form_id:
        assignment.last_synced_at = timezone.now()
        assignment.save()
    return response


@extend_schema(
    tags=["Mobile Device Form"],
    summary="Mark datapoint sync as complete",
    responses={200: DefaultResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsMobileAssignment])
def mark_sync_complete(request, version):
    assignment = cast(MobileAssignmentToken, request.auth).assignment
    assignment.last_synced_at = timezone.now()
    assignment.save()
    return Response({"message": "ok"}, status=status.HTTP_200_OK)


@extend_schema(tags=["Mobile Draft Form Data"])
class DraftFormDataViewSet(ModelViewSet):
    serializer_class = DraftFormDataSerializer
    permission_classes = [IsMobileAssignment]
    pagination_class = Pagination

    def get_queryset(self):
        user = self.request.auth.assignment.user
        return FormData.objects_draft.for_user(user).filter(
            created_by=user
        ).order_by("-created")
