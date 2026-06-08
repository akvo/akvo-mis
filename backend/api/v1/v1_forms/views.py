# Create your views here.
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    inline_serializer,
)

from rest_framework import status, serializers, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from utils.custom_permissions import FormBuilderAccess, IsSuperAdmin
from rest_framework.response import Response

from django.db.models import Q
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.serializers import (
    FormPublishedVersionSerializer,
    ListFormSerializer,
    WebFormDetailSerializer,
    FormDataSerializer,
    FormApproverRequestSerializer,
    FormApproverResponseSerializer,
    FormDetailSerializer,
    FormUpdateRequestSerializer,
)
from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_profile.constants import FeatureAccessTypes
from api.v1.v1_forms.functions import (
    create_published_version,
    restore_from_snapshot,
    save_form,
    store_version_snapshot,
    duplicate_form as _duplicate_form,
    validate_form_payload,
)
from api.v1.v1_profile.models import (
    Administration,
    DataAccessTypes,
    UserRole,
)
from api.v1.v1_data.functions import get_cache, create_cache
from utils.custom_pagination import Pagination
from utils.custom_serializer_fields import validate_serializers_message


def _form_detail_from_snapshot(form, pv):
    """Build a FormDetailSerializer-compatible dict from a snapshot.

    Used by retrieve() and update() for published forms. Resolves in ≤ 3 DB
    queries: form row (already loaded) + latest snapshot (pv) + one batch
    Answers query for disable_delete flags (NF-8).
    """
    schema = pv.schema
    all_q_ids = [
        q["id"]
        for g in schema.get("question_group", [])
        for q in g.get("question", [])
    ]
    answered_q_ids = (
        set(
            Answers.objects.filter(question_id__in=all_q_ids)
            .values_list("question_id", flat=True)
            .distinct()
        )
        if all_q_ids else set()
    )
    latest_pv = form.published_versions.order_by("-version").first()

    question_groups = []
    for g in schema.get("question_group", []):
        questions = []
        for q in g.get("question", []):
            type_str = q.get("type", "").lower()
            if type_str == "administration":
                type_str = "cascade"
            questions.append({
                "id": q["id"],
                "order": q.get("order"),
                "name": q.get("name"),
                "label": q.get("label"),
                "short_label": q.get("short_label"),
                "type": type_str,
                "meta": q.get("meta", False),
                "required": q.get("required", True),
                "rule": q.get("rule"),
                "dependency": q.get("dependency"),
                "dependency_rule": q.get("dependency_rule", "AND"),
                "api": q.get("api"),
                "extra": q.get("extra"),
                "tooltip": q.get("tooltip"),
                "fn": q.get("fn"),
                "pre": q.get("pre"),
                "display_only": q.get("display_only", False),
                "option": q.get("option", []),
                "disable_delete": (
                    True if q["id"] in answered_q_ids else None
                ),
            })
        question_groups.append({
            "id": g["id"],
            "name": g.get("name"),
            "label": g.get("label"),
            "order": g.get("order"),
            "repeatable": g.get("repeatable", False),
            "repeat_text": g.get("repeat_text"),
            "question": questions,
        })

    return {
        "id": form.id,
        "name": schema.get("name", form.name),
        "version": form.version,
        "latest_version": (
            latest_pv.version if latest_pv else form.version
        ),
        "status": FormStatus.FieldStr.get(form.status, "draft"),
        "published_at": (
            form.published_at.isoformat() if form.published_at else None
        ),
        "active_version_id": form.active_version_id,
        "type": form.type,
        "approval_instructions": schema.get("approval_instructions"),
        "parent": form.parent_id,
        "question_group": question_groups,
    }


def _normalize_editor_payload(data):
    """Translate akvo-react-form-editor field names to backend conventions.

    The editor sends plural/camelCase keys; save_form expects singular/
    snake_case. Also maps the legacy 'photo' type to 'image'.

    Only touches question_group when the key (or its plural alias) is actually
    present — payloads that only update top-level fields (e.g. {"name": "…"})
    must pass through untouched so save_form skips group processing.
    """
    if not isinstance(data, dict):
        return data
    out = dict(data)
    # question_groups → question_group
    if "question_groups" in out and "question_group" not in out:
        out["question_group"] = out.pop("question_groups")
    # Only normalize group contents when the key is explicitly present.
    if "question_group" not in out:
        return out
    groups = []
    for g in out.get("question_group", []):
        g = dict(g)
        if "repeatText" in g and "repeat_text" not in g:
            g["repeat_text"] = g.pop("repeatText")
        if "questions" in g and "question" not in g:
            g["question"] = g.pop("questions")
        qs = []
        for q in g.get("question", []):
            q = dict(q)
            if "options" in q and "option" not in q:
                q["option"] = q.pop("options")
            _CAMEL_FIELDS = {
                "displayOnly": "display_only",
                "shortLabel": "short_label",
                "variableName": "variable_name",
                "hiddenString": "hidden_string",
                "requiredDoubleEntry": "required_double_entry",
                "addonBefore": "addon_before",
                "addonAfter": "addon_after",
                "dataApiUrl": "data_api_url",
            }
            for camel, snake in _CAMEL_FIELDS.items():
                if camel in q and snake not in q:
                    q[snake] = q.pop(camel)
            if q.get("type") == "photo":
                q["type"] = "image"
            q.pop("questionGroupId", None)
            qs.append(q)
        g["question"] = qs
        groups.append(g)
    out["question_group"] = groups
    return out


@extend_schema(
    responses={200: ListFormSerializer(many=True)},
    tags=["Form"],
    summary="To get list of forms",
    description="To get list of forms",
)
@api_view(["GET"])
def list_form(request, version):
    instance = Forms.objects.filter(
        parent__isnull=True,
        status=FormStatus.published,
    ).all()
    return Response(
        ListFormSerializer(instance=instance, many=True).data,
        status=status.HTTP_200_OK,
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
    instance = get_object_or_404(Forms, pk=form_id)
    # Include form.version in the cache key so that publishing, activating,
    # or editing a published form (which bumps the version) automatically
    # bypasses the stale cache entry without an explicit cache clear.
    cache_name = (
        f"webform-{form_id}-{administration.id}-v{instance.version}"
    )
    cache_data = get_cache(cache_name)
    if cache_data:
        return Response(cache_data, content_type="application/json;")
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
    instance = get_object_or_404(Forms, pk=form_id)
    cache_name = f"form-{form_id}-v{instance.version}"
    cache_data = get_cache(cache_name)
    if cache_data:
        return Response(cache_data, content_type="application/json;")
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


@extend_schema_view(
    list=extend_schema(
        tags=["Manage Forms"],
        summary="List all forms",
        responses={200: ListFormSerializer(many=True)},
        description="List all forms",
    ),
    create=extend_schema(
        tags=["Manage Forms"],
        summary="Create a new draft form",
    ),
    retrieve=extend_schema(
        tags=["Manage Forms"],
        summary="Get form detail",
    ),
    update=extend_schema(
        tags=["Manage Forms"],
        summary="Update form in-place (auto-increments version if published)",
        parameters=[
            OpenApiParameter(
                name="id",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            ),
            OpenApiParameter(
                name="allow_delete",
                required=False,
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    "When true, questions/groups removed from the payload are "
                    "soft-deleted (deleted_at set) instead of returning 400. "
                    "Required when answered questions need to be removed."
                )
            ),
        ],
        request=FormUpdateRequestSerializer,
    ),
    destroy=extend_schema(
        tags=["Manage Forms"],
        summary="Delete a form (superuser only)",
    ),
)
class FormBuilderViewSet(viewsets.ModelViewSet):
    pagination_class = Pagination

    def get_queryset(self):
        return Forms.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return ListFormSerializer
        return FormDetailSerializer

    def get_permissions(self):
        perm_map = {
            "list": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_view),
            ],
            "create": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_create),
            ],
            "retrieve": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_view),
            ],
            "update": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_edit),
            ],
            "destroy": [IsAuthenticated, IsSuperAdmin],
            "publish": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_publish),
            ],
            "duplicate": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_create),
            ],
            "versions": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_view),
                FormBuilderAccess(FeatureAccessTypes.form_edit),
            ],
            "activate": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_publish),
            ],
            "unpublish": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_publish),
            ],
        }
        return [p() for p in perm_map.get(self.action, [IsAuthenticated])]

    def create(self, request, *args, **kwargs):
        data = _normalize_editor_payload(request.data)
        errors = validate_form_payload(data)
        if errors:
            return Response(
                {"message": errors[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parent_id = data.get("parent")
        req_type = data.get("type")
        is_monitoring = req_type in (FormTypes.monitoring, "monitoring")
        if is_monitoring and parent_id:
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
            form = save_form(data)
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

    def retrieve(self, request, *args, **kwargs):
        form = self.get_object()
        if form.status == FormStatus.published:
            pv = (
                form.active_version
                or form.published_versions.order_by("-version").first()
            )
            if pv:
                return Response(_form_detail_from_snapshot(form, pv))
        return Response(FormDetailSerializer(instance=form).data)

    def update(self, request, *args, **kwargs):
        form = self.get_object()
        data = _normalize_editor_payload(request.data)
        errors = validate_form_payload(data, partial=True)
        if errors:
            return Response(
                {"message": errors[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if form.status == FormStatus.published:
            # Snapshot-only PUT: store payload as snapshot, no live row
            # changes (FR-4, D-6).
            pv = store_version_snapshot(form, data, request.user)
            form.refresh_from_db()
            return Response(_form_detail_from_snapshot(form, pv))

        # Draft PUT: update live rows in-place.
        allow_delete_param = request.query_params.get("allow_delete")
        if allow_delete_param is not None:
            data = {
                **data,
                "allow_delete": allow_delete_param.lower() in ("true", "1"),
            }
        try:
            updated = save_form(data, instance=form)
        except ValueError as exc:
            parts = str(exc).split("|", 1)
            detail = parts[1] if len(parts) > 1 else ""
            return Response(
                {"message": parts[0], "details": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(FormDetailSerializer(instance=updated).data)

    def destroy(self, request, *args, **kwargs):
        form = self.get_object()
        if FormData.objects.filter(form=form).exists():
            return Response(
                {"message": "Cannot delete form with existing submissions"},
                status=status.HTTP_409_CONFLICT,
            )
        form.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Manage Forms"],
        summary=(
            "Publish / re-publish form — "
            "make available for data collection"
        ),
        request=None,
        description=(
            "Handles all publish transitions:\n"
            "• Draft (first publish): builds snapshot from live rows, "
            "activates it, sets status=published.\n"
            "• Draft (re-publish after unpublish): sets status=published, "
            "no new snapshot created.\n"
            "• Published with pending PUT snapshots: activates the latest "
            "snapshot (no new snapshot created).\n"
            "• Published, nothing pending: no-op."
        ),
    )
    @action(detail=True, methods=["post"])
    def publish(self, request, *args, **kwargs):
        form = self.get_object()
        if form.status == FormStatus.published:
            # Already published: activate the latest pending PUT snapshot if
            # one exists. Does NOT create a new snapshot (D-2).
            latest_pv = form.published_versions.order_by("-version").first()
            if latest_pv and latest_pv != form.active_version:
                restore_from_snapshot(form, latest_pv)
                form.refresh_from_db()
        else:
            # Draft → published (first publish OR re-publish after unpublish).
            # create_published_version handles the published_at guard so it is
            # only set on the very first publish, never overwritten.
            create_published_version(form, request.user, activate=True)
            form.refresh_from_db()
        return Response(FormDetailSerializer(instance=form).data)

    @extend_schema(
        tags=["Manage Forms"],
        summary=(
            "Unpublish form — "
            "hide from data collection, allow corrections"
        ),
        request=None,
        description=(
            "Sets status=draft. Auto-activates the latest PUT snapshot first "
            "so live rows equal the admin's latest intended state. "
            "The form remains fully editable via draft PUT. "
            "Call /publish to make it available again."
        ),
    )
    @action(detail=True, methods=["post"])
    def unpublish(self, request, *args, **kwargs):
        form = self.get_object()
        if form.status != FormStatus.published:
            return Response(
                {"message": "Form is not published"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Auto-activate latest snapshot so live rows reflect the latest
        # intended state before the form enters editable draft mode (D-7).
        latest_pv = form.published_versions.order_by("-version").first()
        if latest_pv and latest_pv != form.active_version:
            restore_from_snapshot(form, latest_pv)
            form.refresh_from_db()
        form.status = FormStatus.draft
        form.save(update_fields=["status"])
        return Response(FormDetailSerializer(instance=form).data)

    @extend_schema(
        tags=["Manage Forms"],
        summary="Duplicate a form as a new draft",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def duplicate(self, request, *args, **kwargs):
        form = self.get_object()
        new_form = _duplicate_form(form)
        return Response(
            FormDetailSerializer(instance=new_form).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Manage Forms"],
        summary="List published version snapshots for a form",
    )
    @action(detail=True, methods=["get"])
    def versions(self, request, *args, **kwargs):
        form = self.get_object()
        published = form.published_versions.all().order_by("version")
        return Response(
            FormPublishedVersionSerializer(published, many=True).data
        )

    @extend_schema(
        tags=["Manage Forms"],
        summary="Get a single published version snapshot with schema",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"versions/(?P<version_id>[^/.]+)",
    )
    def version_detail(self, request, version_id=None, *args, **kwargs):
        form = self.get_object()
        pv = get_object_or_404(form.published_versions, pk=version_id)
        data = FormPublishedVersionSerializer(pv).data
        data["schema"] = pv.schema
        return Response(data)

    @extend_schema(
        tags=["Manage Forms"],
        summary="Set a specific published version as the active schema",
        request=None,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"activate/(?P<version_id>[^/.]+)",
    )
    def activate(self, request, version_id=None, *args, **kwargs):
        form = self.get_object()
        # Validate the version belongs to this form.
        pv = get_object_or_404(form.published_versions, pk=version_id)
        restore_from_snapshot(form, pv)
        return Response(FormDetailSerializer(instance=form).data)
