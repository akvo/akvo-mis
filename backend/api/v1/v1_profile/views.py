# Create your views here.
from typing import cast
from wsgiref.util import FileWrapper
from django.contrib.admin.sites import site
from django.core.handlers.wsgi import WSGIRequest
from django.db import IntegrityError, transaction
from django.db.models import Max, ProtectedError, Q
from django.contrib.admin.utils import get_deleted_objects
from django.http.response import HttpResponse
from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from rest_framework.request import Request
from rest_framework.viewsets import ModelViewSet
from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttribute,
    Entity,
    EntityData,
    Levels,
    Role,
)
from api.v1.v1_profile.serializers import (
    AdministrationAttributeSerializer,
    AdministrationSerializer,
    EntityDataSerializer,
    EntitySerializer,
    DownloadAdministrationRequestSerializer,
    DownloadEntityDataRequestSerializer,
    LevelSerializer,
    ListEntityDataSerializer,
    RoleSerializer,
    RoleDetailSerializer,
)
from api.v1.v1_profile.job import create_download_job
from api.v1.v1_users.models import SystemUser
from api.v1.v1_jobs.constants import JobTypes
from utils.upload_administration import (
    generate_administration_excel,
    generate_entities_data_excel,
)
from utils.custom_helper import clean_array_param, maybe_int
from utils.default_serializers import DefaultResponseSerializer
from utils.custom_pagination import Pagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from utils.email_helper import send_email, EmailTypes
from utils.custom_serializer_fields import validate_serializers_message
from utils.custom_generator import administration_csv_delete
from utils.custom_permissions import IsSuperAdmin


@extend_schema(
    request=inline_serializer(
        "BatchUserComment",
        fields={
            "name": serializers.CharField(),
            "email": serializers.CharField(),
            "message": serializers.CharField(),
        },
    ),
    responses={200: DefaultResponseSerializer},
    tags=["Feedback"],
    description="Send feedback",
    summary="Send feedback",
)
@api_view(["POST"])
def send_feedback(request, version):
    name = request.data.get("name")
    email = request.data.get("email")
    message = request.data.get("message")
    # TODO:: change email
    data = {
        "send_to": ["tech.consultancy@akvo.org"],
        "subject": "Feedback from {0} <{1}>".format(name, email),
        "body": "This is feedback from {0} <{1}>. Message: {2}".format(
            name, email, message
        ),
    }
    send_email(context=data, type=EmailTypes.feedback)
    return Response(
        {"message": "Feedback was sent successfully."},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    responses={200: ListEntityDataSerializer},
    tags=["Entities"],
    summary="Get list of entity data by entity type & administration",
)
@api_view(["GET"])
def list_entity_data(request, version, entity_id, administration_id):
    instance = EntityData.objects.for_user(request.user).filter(
        entity__id=entity_id, administration__id=administration_id
    ).all()
    return Response(
        ListEntityDataSerializer(instance=instance, many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Administration"])
class AdministrationViewSet(ModelViewSet):
    serializer_class = AdministrationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    def get_queryset(self):
        queryset = Administration.objects.for_user(
            self.request.user
        ).select_related(
            'level'
        ).prefetch_related(
            'parent_administration',
            'attributes'
        ).all()

        search = self.request.query_params.get("search")
        parent_id = self.request.query_params.get("parent")
        level_id = self.request.query_params.get("level")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )

        if parent_id:
            if Administration.objects.filter(id=parent_id).exists():
                parent = Administration.objects.only('path').get(id=parent_id)
                queryset = queryset.filter(
                    path__startswith=f"{parent.path or ''}{parent.id}."
                )

        if level_id:
            if Levels.objects.filter(id=level_id).exists():
                queryset = queryset.filter(level_id=level_id)

        return queryset.order_by("id")

    def get_serializer(self, *args, **kwargs):
        if self.action == "list":
            kwargs.update({"compact": True})
        return super().get_serializer(*args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="parent",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="level",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            administration_csv_delete(id=instance.pk)
            instance.delete()
        except ProtectedError:
            _, _, _, protected = get_deleted_objects(
                [instance], cast(WSGIRequest, request), site
            )
            error = (
                f'Cannot delete "Administration: {instance}" because it is '
                "referenced by other data"
            )
            return Response(
                {"error": error, "referenced_by": protected},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Administration"])
class AdministrationAttributeViewSet(ModelViewSet):
    serializer_class = AdministrationAttributeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return AdministrationAttribute.objects.for_user(
            self.request.user
        ).order_by("id")


@extend_schema(tags=["Entities"])
class EntityViewSet(ModelViewSet):
    serializer_class = EntitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    def get_queryset(self):
        queryset = Entity.objects.for_user(self.request.user)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by("id")


@extend_schema(tags=["Entities"])
class EntityDataViewSet(ModelViewSet):
    serializer_class = EntityDataSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    def get_queryset(self):
        queryset = EntityData.objects.for_user(
            self.request.user
        ).select_related(
            "administration", "entity"
        ).all()
        search = self.request.query_params.get("search")
        adm_id = self.request.query_params.get("administration")
        entity_id = self.request.query_params.get("entity")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        if adm_id:
            try:
                adm_root = Administration.objects.get(id=adm_id)
                adms = Administration.objects.filter(
                    Q(path__startswith=f"{adm_root.path or ''}{adm_root.id}.")
                    | Q(id=adm_root.id)
                )
                queryset = queryset.filter(administration__in=adms)
            except Administration.DoesNotExist:
                pass
        if entity_id:
            try:
                entities = [int(e) for e in entity_id.split(",")]
                queryset = queryset.filter(entity__in=entities)
            except Entity.DoesNotExist:
                pass

        return queryset.order_by("id")

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="administration",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="entity",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


@extend_schema(
    tags=["File"],
    summary="Export template for Administration bulk upload",
    parameters=[
        OpenApiParameter(
            name="attributes",
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
            explode=False,
        )
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_administrations_template(request: Request, version):
    attributes = clean_array_param(
        request.query_params.get("attributes", ""), maybe_int
    )
    filepath = generate_administration_excel(
        cast(SystemUser, request.user), attributes
    )
    filename = filepath.split("/")[-1].replace(" ", "-")
    with open(filepath, "rb") as template_file:
        response = HttpResponse(
            FileWrapper(template_file),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


@extend_schema(
    tags=["File"],
    summary=("Export prefilled template for Administration bulk upload"),
    parameters=[
        OpenApiParameter(
            name="attributes",
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
            explode=False,
        ),
        OpenApiParameter(
            name="level",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_prefilled_administrations_template(request: Request, version):
    serializer = DownloadAdministrationRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    attributes = clean_array_param(
        request.query_params.get("attributes", ""), maybe_int
    )
    administration = request.query_params.get("administration")
    job = create_download_job(
        adm_id=administration,
        user_id=request.user.id,
        job_type=JobTypes.download_administration,
        job_info={"administration": administration, "attributes": attributes},
    )
    file_url = f"/download/file/{job.result}?type=download_administration"
    data = {
        "task_id": job.task_id,
        "file_url": file_url,
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["File"],
    summary="Export entity data",
    parameters=[
        OpenApiParameter(
            name="entity_ids",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
            explode=False,
        ),
        OpenApiParameter(
            name="adm_id",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_entity_data(request: Request, version):
    serializer = DownloadEntityDataRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    entity_ids = clean_array_param(
        request.query_params.get("entity_ids", ""), maybe_int
    )
    adm_id = request.query_params.get("adm_id")
    entities = Entity.objects.filter(pk__in=entity_ids).values("id", "name")
    entities = [e for e in entities]
    job = create_download_job(
        adm_id=adm_id,
        user_id=request.user.id,
        job_type=JobTypes.download_entities,
        job_info={"administration": adm_id, "entities": entities},
    )
    file_url = f"/download/file/{job.result}?type=download_entities"
    data = {
        "task_id": job.task_id,
        "file_url": file_url,
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["File"],
    summary="Export template for Entities data bulk upload",
    parameters=[
        OpenApiParameter(
            name="entity_types",
            required=True,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
            explode=False,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_entities_data_template(request: Request, version):
    serializer = DownloadEntityDataRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    entity_ids = clean_array_param(
        request.query_params.get("entity_types", ""), maybe_int
    )
    filepath = generate_entities_data_excel(
        cast(SystemUser, request.user), entity_ids
    )
    filename = filepath.split("/")[-1].replace(" ", "-")
    with open(filepath, "rb") as template_file:
        response = HttpResponse(
            FileWrapper(template_file),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


@extend_schema(
    tags=["File"],
    summary="Export entity data with prefilled administrative list",
    parameters=[
        OpenApiParameter(
            name="entity_ids",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
            explode=False,
        ),
        OpenApiParameter(
            name="adm_id",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_pre_entities_data_template(request: Request, version):
    serializer = DownloadEntityDataRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    entity_ids = clean_array_param(
        request.query_params.get("entity_ids", ""), maybe_int
    )
    adm_id = request.query_params.get("adm_id")
    administration = None
    if adm_id:
        administration = Administration.objects.for_user(
            request.user
        ).filter(pk=adm_id).first()
    TESTING = settings.TEST_ENV
    filepath = generate_entities_data_excel(
        cast(SystemUser, request.user),
        entity_ids=entity_ids,
        administration=administration,
        prefilled=True,
        testing=TESTING
    )
    filename = filepath.split("/")[-1].replace(" ", "-")
    with open(filepath, "rb") as template_file:
        response = HttpResponse(
            FileWrapper(template_file),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


@extend_schema(tags=["Levels"])
class LevelViewSet(ModelViewSet):
    """Tenant-scoped hierarchy depth management.

    A tenant's depth is set once during onboarding, so the shape of this
    viewset is deliberately narrow: append a tier, rename any tier, remove
    the deepest one. Arbitrary insertion or reordering would mean
    re-pathing every administrative unit beneath, which the spec rejects as
    disproportionate.
    """

    serializer_class = LevelSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    # A handful of tiers in strict depth order — paging them (the project
    # default is LimitOffsetPagination) would only make the screen walk
    # pages to render one table.
    pagination_class = None

    def get_queryset(self):
        return Levels.objects.for_user(self.request.user).order_by("level")

    def _deepest_level(self):
        return Levels.objects.for_user(self.request.user).aggregate(
            m=Max("level")
        )["m"]

    def _units_below_root(self):
        """Has the tenant built units under its root yet?

        Once it has, changing the depth would strand or re-path them, so
        add and delete freeze. A count of exactly 1 is the root alone.
        Rename ignores this gate — naming a tier moves nothing.
        """
        return Administration.objects.for_user(self.request.user).count() > 1

    def _rejected(self, message):
        return Response(
            {"message": message}, status=status.HTTP_400_BAD_REQUEST
        )

    def create(self, request, *args, **kwargs):
        if self._units_below_root():
            return self._rejected(
                "Levels cannot be added once administrative units exist"
            )
        try:
            # The savepoint is not optional: an IntegrityError caught
            # without one leaves the connection unusable for the rest of
            # the transaction, so the 400 below could not be built if a
            # transaction were ever open around the request.
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError:
            # perform_create reads the current maximum and writes max + 1
            # without a lock, so two requests in flight together both pick
            # the same depth and the loser trips unique_level_per_tenant.
            # Locking the table for a screen a tenant uses once during
            # onboarding would be the wrong trade; telling the caller to
            # look again is enough.
            return self._rejected(
                "Another level was added at the same time; reload and retry"
            )

    def perform_create(self, serializer):
        # Append at the tenant's max + 1; a tenant with no levels starts at 0.
        current_max = self._deepest_level()
        serializer.save(
            tenant=self.request.user.tenant,
            level=0 if current_max is None else current_max + 1,
        )

    def destroy(self, request, *args, **kwargs):
        # get_object() resolves through get_queryset, so another tenant's
        # level is a 404 rather than a rejection that confirms it exists.
        level = self.get_object()
        if level.level != self._deepest_level():
            return self._rejected("Only the deepest level can be removed")
        if self._units_below_root():
            return self._rejected(
                "Levels cannot be removed once administrative units exist"
            )
        # With the two gates above passed, the only unit that can still sit
        # at this level is the root at level 0 — this is what stops a tenant
        # from deleting the last tier out from under its own root.
        if Administration.objects.for_user(request.user).filter(
            level=level
        ).exists():
            return self._rejected("This level still has administrative units")
        # Role.administration_level cascades, so deleting the level would
        # take the role, its access rows and every user assignment with it.
        if Role.objects.filter(administration_level=level).exists():
            return self._rejected(
                "This level is in use by one or more roles; remove them first"
            )
        return super().destroy(request, *args, **kwargs)


@extend_schema(tags=["Roles"])
class RoleViewSet(ModelViewSet):
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = Pagination

    def get_queryset(self):
        queryset = Role.objects.for_user(self.request.user).order_by(
            "administration_level__level"
        )
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    def get_serializer_class(self):
        if self.request and self.action in [
            "list",
            "retrieve"
        ]:
            return RoleDetailSerializer
        return super().get_serializer_class()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            _, _, _, protected = get_deleted_objects(
                [instance], cast(WSGIRequest, request), site
            )
            error = (
                f'Cannot delete "Role: {instance}" because it is '
                "referenced by other data"
            )
            return Response(
                {"error": error, "referenced_by": protected},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
