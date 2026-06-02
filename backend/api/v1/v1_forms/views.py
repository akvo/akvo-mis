# Create your views here.
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    inline_serializer,
)

from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from utils.custom_permissions import IsFormBuilder
from rest_framework.response import Response

from django.db.models import Q
from django.utils import timezone
from api.v1.v1_forms.models import (
    Forms,
)
from api.v1.v1_forms.serializers import (
    ListFormSerializer,
    WebFormDetailSerializer,
    FormDataSerializer,
    FormApproverRequestSerializer,
    FormApproverResponseSerializer,
    FormDetailSerializer,
    FormVersionSerializer,
)
from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.functions import (
    save_form,
    version_on_edit,
    duplicate_form as _duplicate_form,
    validate_form_payload,
)
from api.v1.v1_profile.models import (
    Administration,
    DataAccessTypes,
    UserRole,
)
from api.v1.v1_data.functions import get_cache, create_cache
from utils.custom_serializer_fields import validate_serializers_message


@extend_schema(
    responses={200: ListFormSerializer(many=True)},
    tags=["Form"],
    summary="To get list of forms",
    description="To get list of forms",
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def list_form(request, version):
    if request.method == "POST":
        return _handle_create_form(request)
    instance = Forms.objects.filter(parent__isnull=True).all()
    return Response(
        ListFormSerializer(instance=instance, many=True).data,
        status=status.HTTP_200_OK,
    )


def _handle_create_form(request):
    """Shared create logic for list_form POST branch."""
    if not IsFormBuilder().has_permission(request, None):
        return Response(
            {"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        )
    errors = validate_form_payload(request.data)
    if errors:
        return Response(
            {"message": errors[0]}, status=status.HTTP_400_BAD_REQUEST
        )
    parent_id = request.data.get("parent")
    if request.data.get("type") == "monitoring" and parent_id:
        try:
            parent = Forms.objects.get(id=parent_id)
        except Forms.DoesNotExist:
            return Response(
                {"parent": "Parent form not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            parent.status != FormStatus.published
            or parent.type != FormTypes.registration
        ):
            return Response(
                {"parent": "Parent must be a published registration form"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    try:
        form = save_form(request.data)
    except ValueError as exc:
        parts = str(exc).split("|", 1)
        detail = parts[1] if len(parts) > 1 else ""
        return Response(
            {"message": parts[0], "details": detail},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        FormDetailSerializer(instance=form).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    responses={200: WebFormDetailSerializer},
    tags=["Form"],
    summary="To get form in webform format",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def web_form_details(request, version, form_id):
    administration = Administration.objects.filter(
        parent__isnull=True,
    ).first()
    if not request.user.is_superuser:
        user_role = request.user.user_user_role.filter(
            role__role_role_access__data_access=DataAccessTypes.submit
        ).first()
        if user_role:
            administration = user_role.administration
    cache_name = f"webform-{form_id}-{administration.id}"
    cache_data = get_cache(cache_name)
    if cache_data:
        return Response(cache_data, content_type="application/json;")
    instance = get_object_or_404(Forms, pk=form_id)
    instance = WebFormDetailSerializer(
        instance=instance, context={"user": request.user}
    ).data
    create_cache(cache_name, instance)
    return Response(instance, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: FormDataSerializer},
    tags=["Form"],
    summary="To get form data",
)
@api_view(["GET"])
def form_data(request, version, form_id):
    cache_name = f"form-{form_id}"
    cache_data = get_cache(cache_name)
    if cache_data:
        return Response(cache_data, content_type="application/json;")
    instance = get_object_or_404(Forms, pk=form_id)
    instance = FormDataSerializer(instance=instance).data
    create_cache(cache_name, instance)
    return Response(instance, status=status.HTTP_200_OK)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="administration_id",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="form_id",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={200: FormApproverResponseSerializer(many=True)},
    tags=["Form"],
    summary="To get approver user list",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def form_approver(request, version):
    serializer = FormApproverRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    adm = serializer.validated_data.get("administration_id")
    path = adm.path if adm.path else f"{adm.id}."
    instance = Administration.objects.filter(
        path__startswith=path,
    )
    ancestors = list(adm.ancestors.all()) if adm.ancestors else []
    instance = ancestors + [
        serializer.validated_data.get("administration_id")
    ] + list(instance)
    return Response(
        FormApproverResponseSerializer(
            instance=instance,
            many=True,
            context={"form": serializer.validated_data.get("form_id")},
        ).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    responses={
        (200, "application/json"): inline_serializer(
            "CheckFormApproverSerializer",
            fields={
                "count": serializers.IntegerField(),
            },
        )
    },
    tags=["Form"],
    summary="To check approver for defined form_id & logged in user",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_form_approver(request, form_id, version):
    form = get_object_or_404(Forms, pk=form_id)
    # Check if the user has any roles that allow them to approve the form
    # This will include checking the user's administration and its ancestors
    by_ancestors = Q()
    for ur in request.user.user_user_role.all():
        adm = ur.administration
        if adm.ancestors:
            ancestors = list(adm.ancestors.all()) + [adm]
            by_ancestors |= Q(administration__in=ancestors)
    approver = UserRole.objects.filter(
        by_ancestors,
        user__user_form__form=form,
        role__role_role_access__data_access=DataAccessTypes.approve,
    ).count()
    return Response({"count": approver}, status=status.HTTP_200_OK)


# ─── Form Builder CRUD Views ─────────────────────────────────────────────────


@extend_schema(
    tags=["Form Builder"],
    summary="Get, update or delete a form",
)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def form_detail(request, version, pk):
    try:
        form = Forms.objects.get(pk=pk)
    except Forms.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(FormDetailSerializer(instance=form).data)

    if request.method == "PUT":
        errors = validate_form_payload(request.data)
        if errors:
            return Response(
                {"message": errors[0]}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            if form.status == FormStatus.published:
                new_form = version_on_edit(form, request.data)
                return Response(
                    FormDetailSerializer(instance=new_form).data,
                    status=status.HTTP_201_CREATED,
                )
            updated = save_form(request.data, instance=form)
        except ValueError as exc:
            parts = str(exc).split("|", 1)
            detail = parts[1] if len(parts) > 1 else ""
            return Response(
                {"message": parts[0], "details": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(FormDetailSerializer(instance=updated).data)

    if request.method == "DELETE":
        if not request.user.is_superuser:
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        from api.v1.v1_data.models import FormData
        if FormData.objects.filter(form=form).exists():
            return Response(
                {"message": "Cannot delete form with existing submissions"},
                status=status.HTTP_409_CONFLICT,
            )
        form.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Form Builder"],
    summary="Publish a draft form",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def publish_form(request, version, pk):
    try:
        form = Forms.objects.get(pk=pk)
    except Forms.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if form.status == FormStatus.published:
        return Response(
            {"message": "Form is already published"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    form.status = FormStatus.published
    form.published_at = timezone.now()
    form.save()
    return Response(FormDetailSerializer(instance=form).data)


@extend_schema(
    tags=["Form Builder"],
    summary="Duplicate a form as a new draft",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def duplicate_form_view(request, version, pk):
    try:
        form = Forms.objects.get(pk=pk)
    except Forms.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    new_form = _duplicate_form(form)
    return Response(
        FormDetailSerializer(instance=new_form).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Form Builder"],
    summary="List version chain for a form",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFormBuilder])
def form_versions(request, version, pk):
    try:
        form = Forms.objects.get(pk=pk)
    except Forms.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    # Walk previous_version chain to find root
    root = form
    while root.previous_version_id:
        root = root.previous_version
    # Collect root + immediate next versions
    all_versions = list(
        Forms.objects.filter(id=root.id)
        | Forms.objects.filter(previous_version_id=root.id)
    ).copy()
    all_versions.sort(key=lambda f: f.version)
    return Response(FormVersionSerializer(all_versions, many=True).data)
