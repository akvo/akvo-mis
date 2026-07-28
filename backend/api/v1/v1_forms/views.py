# Create your views here.
import json
import re
from uuid import uuid4

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
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from utils.custom_permissions import FormBuilderAccess
from rest_framework.response import Response

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.http import HttpResponse
from django_q.tasks import async_task

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import (
    FormStatus,
    FormTypes,
    _CAMEL_FIELDS,
)
from api.v1.v1_forms.functions import (
    create_published_version,
    export_form_definition,
    get_published_forms_payload,
    normalize_form_definition,
    restore_from_snapshot,
    save_form,
    store_version_snapshot,
    duplicate_form as _duplicate_form,
    validate_form_definition,
    validate_form_payload,
)
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
    ImportPreflightSerializer,
    ImportFormSerializer,
)
from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_profile.constants import FeatureAccessTypes
from api.v1.v1_profile.models import (
    Administration,
    DataAccessTypes,
    UserRole,
)
from api.v1.v1_data.functions import get_cache, create_cache
from utils.custom_pagination import Pagination
from utils.custom_serializer_fields import validate_serializers_message
import utils.storage as storage


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
            q_dict = {
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
                "variable_name": q.get("variable_name"),
                "translations": q.get("translations"),
                "option": q.get("option", []),
                "disable_delete": (
                    True if q["id"] in answered_q_ids else None
                ),
            }
            questions.append(
                {k: v for k, v in q_dict.items() if v is not None}
            )
        question_groups.append({
            "id": g["id"],
            "name": g.get("name"),
            "label": g.get("label"),
            "order": g.get("order"),
            "repeatable": g.get("repeatable", False),
            "repeat_text": g.get("repeat_text"),
            "translations": g.get("translations"),
            "question": questions,
        })

    return {
        "id": form.id,
        "name": schema.get("name", form.name),
        "description": schema.get("description"),
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
        "languages": schema.get("languages"),
        "default_language": schema.get("default_language"),
        "translations": schema.get("translations"),
        "question_group": question_groups,
    }


# Question fields that change casing between the editor (camelCase) and the
# backend (snake_case) — used by both _normalize_editor_payload (in) and
# _to_editor_format (out).
_SNAKE_TO_CAMEL_Q = {
    "short_label": "short_label",
    "display_only": "displayOnly",
    "dependency_rule": "dependencyRule",
    "hidden_string": "hiddenString",
    "required_double_entry": "requiredDoubleEntry",
    "addon_before": "addonBefore",
    "addon_after": "addonAfter",
    "data_api_url": "dataApiUrl",
    "disable_delete": "disableDelete",
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
    # defaultLanguage → default_language
    if "defaultLanguage" in out and "default_language" not in out:
        out["default_language"] = out.pop("defaultLanguage")
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
            for camel, snake in _CAMEL_FIELDS.items():
                if camel in q and snake not in q:
                    q[snake] = q.pop(camel)
            # variable → variable_name (editor uses 'variable'; inverse of
            # _to_editor_format which renames variable_name → variable)
            if "variable" in q and "variable_name" not in q:
                q["variable_name"] = q.pop("variable")
            if q.get("type") == "photo":
                q["type"] = "image"
            # tree type: editor sends option as a JSON string → tree_option
            if isinstance(q.get("option"), str):
                q["tree_option"] = q.pop("option")
                q["option"] = []
            q.pop("questionGroupId", None)
            qs.append(q)
        g["question"] = qs
        groups.append(g)
    out["question_group"] = groups
    return out


def _to_editor_format(data):
    """Convert API response dict to editor-compatible (camelCase) format.

    Inverse of _normalize_editor_payload. Applied before returning responses
    from form builder CRUD endpoints so the frontend can use the response
    directly as editor initialValue without any client-side transform.
    """
    if not isinstance(data, dict):
        return data
    out = dict(data)
    # default_language → defaultLanguage at form level
    if "default_language" in out:
        out["defaultLanguage"] = out.pop("default_language")
    groups = []
    for g in out.get("question_group", []):
        g = dict(g)
        questions = []
        for q in g.get("question", []):
            q = dict(q)
            # variable_name → variable (editor convention)
            if "variable_name" in q:
                q["variable"] = q.pop("variable_name")
            # snake_case → camelCase for standard question fields
            for snake, camel in _SNAKE_TO_CAMEL_Q.items():
                if snake in q:
                    q[camel] = q.pop(snake)
            questions.append(q)
        g["question"] = questions
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
    instance = Forms.objects.for_user(request.user).filter(
        parent__isnull=True,
        status=FormStatus.published,
    )
    return Response(
        ListFormSerializer(instance=instance, many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Form"],
    summary="Published forms with full content for the web frontend",
    description=(
        "Returns every published form (parents and children) with its full "
        "content definition. Replaces the window.forms global previously "
        "baked into config.min.js so newly published forms reflect without "
        "a config rebuild. Public, like config.js."
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def list_published_forms(request, version):
    response = Response(
        get_published_forms_payload(request.user),
        status=status.HTTP_200_OK,
    )
    response["Cache-Control"] = "no-cache"
    return response


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
    instance = get_object_or_404(
        Forms.objects.for_user(request.user), pk=form_id
    )
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
    instance = get_object_or_404(
        Forms.objects.for_user(request.user), pk=form_id
    )
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
    form = get_object_or_404(
        Forms.objects.for_user(request.user), pk=form_id
    )
    # Super admins bypass approver check
    if request.user.is_superuser:
        return Response({"count": 1}, status=status.HTTP_200_OK)
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
        summary="Permanently delete a form (requires form_delete access)",
    ),
)
class FormBuilderViewSet(viewsets.ModelViewSet):
    pagination_class = Pagination

    def get_queryset(self):
        # archive/restore/destroy operate on archived (soft-deleted) rows,
        # which the default manager cannot see (D-9, D-10).
        if self.action in ("archive", "restore", "destroy"):
            return Forms.objects_with_deleted.for_user(self.request.user)
        return Forms.objects.for_user(self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return ListFormSerializer
        return FormDetailSerializer

    # ── List with filtering, hierarchy and archived tab (FB-004) ──

    _STATUS_MAP = {
        "draft": FormStatus.draft,
        "published": FormStatus.published,
    }
    _TYPE_MAP = {
        "registration": FormTypes.registration,
        "monitoring": FormTypes.monitoring,
    }

    def _serialize_form(self, form):
        return ListFormSerializer(instance=form).data

    def list(self, request, *args, **kwargs):
        params = request.query_params
        archived = params.get("archived") == "true"
        search = (params.get("search") or "").strip()
        type_param = params.get("type")
        status_param = params.get("status")

        base = Forms.objects_deleted if archived else Forms.objects
        qs = base.for_user(request.user)
        if status_param in self._STATUS_MAP:
            qs = qs.filter(status=self._STATUS_MAP[status_param])

        # Flat modes: a single explicit type, or the archived tab. No nesting.
        if archived or type_param in self._TYPE_MAP:
            if type_param in self._TYPE_MAP:
                qs = qs.filter(type=self._TYPE_MAP[type_param])
            if search:
                qs = qs.filter(name__icontains=search)
            page = self.paginate_queryset(qs.order_by("-id"))
            data = [self._serialize_form(f) for f in page]
            return self.get_paginated_response(data)

        # "Active" tab, no type filter: registration parents with monitoring
        # children nested (D-2, D-4). Search also matches children, pulling
        # in their parent as a container (D-5).
        parents = qs.filter(type=FormTypes.registration)
        if search:
            parents = parents.filter(
                Q(name__icontains=search)
                | Q(
                    children__name__icontains=search,
                    children__deleted_at__isnull=True,
                )
            ).distinct()
        page = self.paginate_queryset(parents.order_by("-id"))
        data = []
        for parent in page:
            child_qs = parent.children.all()
            if status_param in self._STATUS_MAP:
                child_qs = child_qs.filter(
                    status=self._STATUS_MAP[status_param]
                )
            parent_matches = (not search) or (
                search.lower() in parent.name.lower()
            )
            if search and not parent_matches:
                # Parent pulled in only by a matching child (D-5): return
                # just the matching children.
                child_qs = child_qs.filter(name__icontains=search)
            row = dict(self._serialize_form(parent))
            row["children"] = [
                self._serialize_form(c) for c in child_qs.order_by("-id")
            ]
            data.append(row)
        return self.get_paginated_response(data)

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
            "destroy": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_delete),
            ],
            "archive": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_publish),
            ],
            "restore": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_publish),
            ],
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
            "export_definition": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_view),
            ],
            "import_preflight": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_create),
            ],
            "import_definition": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_create),
            ],
            "import_status": [
                IsAuthenticated,
                FormBuilderAccess(FeatureAccessTypes.form_create),
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
            form = save_form(data, user=request.user)
        except ValueError as exc:
            parts = str(exc).split("|", 1)
            detail = parts[1] if len(parts) > 1 else ""
            return Response(
                {"message": parts[0], "details": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            _to_editor_format(FormDetailSerializer(instance=form).data),
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
                return Response(
                    _to_editor_format(_form_detail_from_snapshot(form, pv))
                )
        return Response(
            _to_editor_format(FormDetailSerializer(instance=form).data)
        )

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
            return Response(
                _to_editor_format(_form_detail_from_snapshot(form, pv))
            )

        # Draft PUT: update live rows in-place.
        allow_delete_param = request.query_params.get("allow_delete")
        if allow_delete_param is not None:
            data = {
                **data,
                "allow_delete": allow_delete_param.lower() in ("true", "1"),
            }
        try:
            updated = save_form(data, instance=form, user=request.user)
        except ValueError as exc:
            parts = str(exc).split("|", 1)
            detail = parts[1] if len(parts) > 1 else ""
            return Response(
                {"message": parts[0], "details": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            _to_editor_format(FormDetailSerializer(instance=updated).data)
        )

    def destroy(self, request, *args, **kwargs):
        form = self.get_object()
        if FormData.objects.filter(form=form).exists():
            return Response(
                {"message": "Cannot delete form with existing submissions"},
                status=status.HTTP_409_CONFLICT,
            )
        # Permanent removal. Forms is soft-deletable (D-1), so the default
        # .delete() would soft-delete — call hard_delete() explicitly (D-9).
        form.hard_delete()
        async_task("api.v1.v1_forms.tasks.refresh_form_config")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Manage Forms"],
        summary="Archive a form — reversible soft-delete",
        request=None,
        description=(
            "Soft-deletes the form (sets deleted_at). Archived forms are "
            "removed from data collection (web and mobile) via the default "
            "manager and moved to the Archived tab. Allowed even when the "
            "form has submissions; they are preserved. Reversible via "
            "/restore (D-1)."
        ),
    )
    @action(detail=True, methods=["post"])
    def archive(self, request, *args, **kwargs):
        form = self.get_object()
        if form.deleted_at is not None:
            return Response(
                {"message": "Form is already archived"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        form.soft_delete()
        async_task("api.v1.v1_forms.tasks.refresh_form_config")
        return Response(
            {
                "id": form.id,
                "status": "archived",
                "deleted_at": form.deleted_at,
            }
        )

    @extend_schema(
        tags=["Manage Forms"],
        summary="Restore an archived form (returns it to draft)",
        request=None,
        description=(
            "Clears deleted_at and sets status=draft. The form must be "
            "re-published to resume data collection (D-7)."
        ),
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, *args, **kwargs):
        form = self.get_object()
        if form.deleted_at is None:
            return Response(
                {"message": "Form is not archived"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        form.deleted_at = None
        form.status = FormStatus.draft
        form.save(update_fields=["deleted_at", "status"])
        return Response(
            {"id": form.id, "status": "draft", "deleted_at": None}
        )

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
        async_task("api.v1.v1_forms.tasks.refresh_form_config")
        return Response(
            _to_editor_format(FormDetailSerializer(instance=form).data)
        )

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
        async_task("api.v1.v1_forms.tasks.refresh_form_config")
        return Response(
            _to_editor_format(FormDetailSerializer(instance=form).data)
        )

    @extend_schema(
        tags=["Manage Forms"],
        summary="Duplicate a form as a new draft",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def duplicate(self, request, *args, **kwargs):
        form = self.get_object()
        new_form = _duplicate_form(form, user=request.user)
        return Response(
            _to_editor_format(FormDetailSerializer(instance=new_form).data),
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
        data = dict(FormPublishedVersionSerializer(pv).data)
        data["schema"] = _to_editor_format(pv.schema)
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
        return Response(
            _to_editor_format(FormDetailSerializer(instance=form).data)
        )

    # -----------------------------------------------------------------------
    # FB-007: Form Import/Export
    # -----------------------------------------------------------------------

    @extend_schema(
        tags=["Manage Forms"],
        summary="Export form definition as JSON (FB-007)",
        responses={(200, "application/json"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"], url_path="export")
    def export_definition(self, request, *args, **kwargs):
        form = self.get_object()
        payload = export_form_definition(form)
        slug = re.sub(r"[^a-z0-9]+", "-", form.name.lower()).strip("-")
        from django.utils import timezone as tz
        date_str = tz.now().strftime("%Y%m%d")
        filename = f"form-{form.id}-{slug}-{date_str}.json"
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        resp = HttpResponse(body, content_type="application/json")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @extend_schema(
        tags=["Manage Forms"],
        summary="Validate an import file without writing (preflight, FB-007)",
        request={"multipart/form-data": ImportPreflightSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="import/preflight",
        parser_classes=[MultiPartParser],
    )
    def import_preflight(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"message": "file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_size = getattr(
            settings, "FORM_IMPORT_MAX_FILE_SIZE", 5 * 1024 * 1024
        )
        if file_obj.size > max_size:
            return Response(
                {"message": "File too large"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            raw = json.loads(file_obj.read().decode("utf-8"))
        except Exception:
            return Response(
                {"message": "Invalid JSON file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm)
        errors = [i for i in issues if i.get("level") == "error"]
        warnings = [i for i in issues if i.get("level") == "warning"]

        # Match check
        file_form_id = norm.get("form_id")
        match_info = {"exists": False, "form": None, "name_mismatch": False}
        if file_form_id is not None:
            existing = Forms.objects.filter(id=file_form_id).first()
            if existing:
                submission_count = existing.form_data.count() if hasattr(
                    existing, "form_data"
                ) else 0
                match_info = {
                    "exists": True,
                    "form": {
                        "id": existing.id,
                        "name": existing.name,
                        "status": FormStatus.FieldStr.get(existing.status),
                        "submission_count": submission_count,
                        "updated": (
                            existing.updated.isoformat()
                            if existing.updated else None
                        ),
                    },
                    "name_mismatch": (
                        existing.name != norm.get("name")
                    ),
                }

        # Parent resolution info
        is_monitoring = norm.get("type") == FormTypes.monitoring
        parent_hint = norm.get("parent_hint")
        resolved_parent = None
        if is_monitoring and parent_hint and parent_hint.get("id"):
            p = Forms.objects.filter(id=parent_hint["id"]).first()
            if p:
                resolved_parent = {"id": p.id, "name": p.name}

        parent_info = {
            "required": is_monitoring,
            "hint": parent_hint,
            "resolved": resolved_parent,
        }

        is_valid = len(errors) == 0
        return Response(
            {
                "valid": is_valid,
                "errors": errors,
                "warnings": warnings,
                "form": {
                    "id": norm.get("form_id"),
                    "name": norm.get("name"),
                    "type": norm.get("type"),
                },
                "match": match_info,
                "parent": parent_info,
            },
            status=(
                status.HTTP_200_OK
                if is_valid
                else status.HTTP_400_BAD_REQUEST
            ),
        )

    @extend_schema(
        tags=["Manage Forms"],
        summary="Enqueue a form definition import job (FB-007)",
        request={"multipart/form-data": ImportFormSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser],
    )
    def import_definition(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"message": "file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_size = getattr(
            settings, "FORM_IMPORT_MAX_FILE_SIZE", 5 * 1024 * 1024
        )
        if file_obj.size > max_size:
            return Response(
                {"message": "File too large"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        mode = request.data.get("mode", "create_or_update")
        if mode not in ("create_or_update", "create_copy"):
            return Response(
                {"message": "mode must be create_or_update or create_copy"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent_id = request.data.get("parent_id")
        if parent_id:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                return Response(
                    {"message": "parent_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Server-side re-validation (preflight is advisory, never trusted)
        try:
            raw = json.loads(file_obj.read().decode("utf-8"))
        except Exception:
            return Response(
                {"message": "Invalid JSON file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm)
        errors = [i for i in issues if i.get("level") == "error"]
        if errors:
            return Response(
                {"valid": False, "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # update-mode: require form_edit permission
        file_form_id = norm.get("form_id")
        if (
            mode == "create_or_update"
            and file_form_id is not None
            and Forms.objects.filter(id=file_form_id).exists()
        ):
            edit_perm = FormBuilderAccess(FeatureAccessTypes.form_edit)()
            if not edit_perm.has_permission(request, self):
                return Response(status=status.HTTP_403_FORBIDDEN)

        # Persist file to upload storage (DD-6)
        file_obj.seek(0)
        fs = FileSystemStorage()
        uid = "_".join(str(uuid4()).split("-")[:-1])
        filename = f"import-form-{request.user.id}-{uid}.json"
        tmp = fs.save(f"./tmp/{file_obj.name}", file_obj)
        tmp_path = fs.path(tmp)
        storage.upload(file=tmp_path, filename=filename, folder="upload")

        job = Jobs.objects.create(
            type=JobTypes.import_form,
            status=JobStatus.on_progress,
            user=request.user,
            info={
                "file": filename,
                "mode": mode,
                "parent_id": parent_id,
                "form_id": file_form_id,
            },
        )
        task_id = async_task(
            "api.v1.v1_forms.tasks.import_form_job",
            job.id,
            hook="api.v1.v1_forms.tasks.import_form_job_result",
        )
        job.task_id = task_id
        job.save(update_fields=["task_id"])

        return Response(
            {"task_id": task_id, "job_id": job.id},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Manage Forms"],
        summary="Poll import job status (FB-007)",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"import/status/(?P<task_id>[^/.]+)",
    )
    def import_status(self, request, task_id=None, *args, **kwargs):
        try:
            job = Jobs.objects.get(
                task_id=task_id,
                type=JobTypes.import_form,
                user=request.user,
            )
        except Jobs.DoesNotExist:
            return Response(
                {"message": "Job not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        resp = {
            "status": JobStatus.FieldStr.get(job.status),
            "form": None,
            "errors": None,
            "warnings": None,
        }

        if job.status == JobStatus.done and job.result:
            try:
                result = json.loads(job.result)
                resp["form"] = {
                    "id": result.get("form_id"),
                    "name": result.get("form_name"),
                    "action": result.get("action"),
                }
                resp["warnings"] = result.get("warnings")
            except Exception:
                pass

        if job.status == JobStatus.failed and job.result:
            try:
                resp["errors"] = json.loads(job.result)
            except Exception:
                resp["errors"] = [{"code": "unknown", "message": job.result}]

        return Response(resp)
