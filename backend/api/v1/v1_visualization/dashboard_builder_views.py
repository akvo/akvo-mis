# =========================================================
# Dashboard builder: /manage/dashboards (VIZ-005)
# =========================================================
# Mirrors FormBuilderViewSet (FB-002): the queryset is scoped with
# for_user() so no action can reach a row outside the caller's tenant,
# and permissions come from a per-action map rather than a check
# scattered through each method.
#
# No pagination_class. VIZ-001 §6 says "paginated", but both merged
# consumers do Array.isArray(res.data) ? res.data : [], and
# DashboardBuilder resolves slug -> id by scanning the whole list, so
# an envelope would break the builder silently. See the spec, D-1.

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_profile.constants import FeatureAccessTypes
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.dashboard_builder_serializers import (
    DashboardDetailSerializer,
    DashboardListSerializer,
    serialize_sources,
)
from api.v1.v1_visualization.dashboard_functions import (
    SLUG_PATTERN,
    apply_widgets,
    copy_name,
    copy_slug,
    derive_slug,
    suggest_slug,
    validate_dashboard_payload,
)
from api.v1.v1_visualization.dashboard_snapshot import build_snapshot
from api.v1.v1_visualization.models import Dashboard, DashboardWidget
from utils.custom_permissions import DashboardAccess


class DenyUnmappedAction(BasePermission):
    """The safe reading of an action nobody mapped.

    Not exported: an action missing from ACCESS_PER_ACTION is a mistake
    in this file, and nowhere else has that map.
    """

    def has_permission(self, request, view):
        return False


class DashboardBuilderViewSet(viewsets.ModelViewSet):
    # REST_FRAMEWORK.DEFAULT_PAGINATION_CLASS is LimitOffsetPagination
    # project-wide, so simply omitting pagination_class here would still
    # wrap list() in a {count, next, previous, results} envelope. This
    # explicit None is what actually produces the bare array the brief
    # describes and the merged builder requires.
    pagination_class = None

    def get_queryset(self):
        queryset = Dashboard.objects.for_user(self.request.user)
        queryset = queryset.select_related("root_form", "created_by")
        if self.action == "list":
            # Only list touches every row's widgets (for the thumbnail
            # stubs). update() serialises its response from this same
            # get_object() instance *after* apply_widgets rewrites the
            # widget rows — a prefetch cache filled here would still
            # hold the pre-save rows and make the PUT response show
            # stale widgets, so the other actions must not carry it.
            queryset = queryset.prefetch_related("widgets")
        return queryset.order_by("-id")

    def get_serializer_class(self):
        if self.action == "list":
            return DashboardListSerializer
        return DashboardDetailSerializer

    # One access type per action. FormBuilderViewSet spells the same
    # mapping out as full permission lists; this is the same rule in the
    # form that cannot drift between two near-identical entries.
    ACCESS_PER_ACTION = {
        "list": FeatureAccessTypes.dashboard_view,
        "create": FeatureAccessTypes.dashboard_create,
        "retrieve": FeatureAccessTypes.dashboard_view,
        "update": FeatureAccessTypes.dashboard_edit,
        "destroy": FeatureAccessTypes.dashboard_delete,
        "sources": FeatureAccessTypes.dashboard_view,
        "publish": FeatureAccessTypes.dashboard_publish,
        "unpublish": FeatureAccessTypes.dashboard_publish,
        "duplicate": FeatureAccessTypes.dashboard_create,
    }

    def get_permissions(self):
        access = self.ACCESS_PER_ACTION.get(self.action)
        if access is None:
            # Deny rather than fall through to IsAuthenticated. An
            # action missing from the map above is an oversight, and the
            # safe reading of an oversight is "no access" rather than
            # "every signed-in user in the tenant". Nothing routed hits
            # this today; the branch exists so that adding a tenth
            # action and forgetting its entry fails closed.
            return [DenyUnmappedAction()]
        return [IsAuthenticated(), DashboardAccess(access)()]

    def create(self, request, *args, **kwargs):
        error = validate_dashboard_payload(request.data, request.user)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        name = request.data.get("name")
        requested_slug = request.data.get("slug")
        slug = derive_slug(name, requested_slug)
        if not SLUG_PATTERN.match(slug):
            # Report whichever field actually produced the bad slug: a
            # client-supplied slug that fails the pattern is a "slug"
            # problem even though the derived-from-name path is what
            # usually trips this.
            field, message = (
                ("slug", "slug may only contain lowercase letters, "
                         "numbers and hyphens")
                if (requested_slug or "").strip()
                else ("name", "name must contain at least one letter "
                              "or digit")
            )
            return Response(
                {"message": message, "field": field},
                status=status.HTTP_400_BAD_REQUEST,
            )
        live = Dashboard.objects.for_user(request.user)
        if live.filter(slug=slug).exists():
            return Response(
                {
                    "message": (
                        "a dashboard with this name already exists"
                    ),
                    "suggested_slug": suggest_slug(slug, live),
                },
                status=status.HTTP_409_CONFLICT,
            )

        dashboard = Dashboard.objects.create(
            name=name.strip(),
            slug=slug,
            description=request.data.get("description"),
            # Never from the payload: tenant comes from the
            # authenticated user, so a caller cannot plant a row in
            # someone else's workspace (MT-004).
            tenant=getattr(request.user, "tenant", None),
            root_form_id=request.data.get("root_form"),
            created_by=request.user,
            default_filters=request.data.get("default_filters") or {},
        )
        return Response(
            DashboardDetailSerializer(instance=dashboard).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        dashboard = self.get_object()
        error = validate_dashboard_payload(
            request.data, request.user, dashboard=dashboard
        )
        if error:
            # Nothing has been written yet, and nothing will be: the
            # stored dashboard is byte-identical after a rejected save.
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            name = request.data.get("name")
            if name:
                # The slug is not re-derived. A dashboard's slug is its
                # URL and renaming is a cosmetic edit.
                dashboard.name = name.strip()
            dashboard.description = request.data.get("description")
            dashboard.default_filters = (
                request.data.get("default_filters") or {}
            )
            dashboard.updated = timezone.now()
            dashboard.save()
            apply_widgets(dashboard, request.data.get("widgets") or [])

        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    def publish(self, request, *args, **kwargs):
        dashboard = self.get_object()
        snapshot = build_snapshot(dashboard)
        # Revalidate through the *same* function PUT uses (spec D-3).
        # `published_config` is what viewers read and nothing
        # revalidates it downstream, so publishing is the last place a
        # broken dashboard can be stopped. Calling the save-time
        # validator rather than writing a stored-rows twin is what keeps
        # the two from drifting; tests_dashboard_snapshot pins the shape
        # compatibility that makes it possible.
        error = validate_dashboard_payload(
            {"name": dashboard.name, "widgets": snapshot["widgets"]},
            request.user,
            dashboard=dashboard,
        )
        if error:
            # Nothing written: status, published_config and
            # published_at are all exactly as they were, so a failed
            # republish keeps serving the last good snapshot.
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            dashboard.published_config = snapshot
            dashboard.status = DashboardStatus.published
            # Rewritten on every publish, unlike Forms.published_at
            # (spec D-2): a form's date is provenance, a dashboard's
            # answers "how fresh is what I am looking at".
            dashboard.published_at = timezone.now()
            dashboard.save()
        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    def unpublish(self, request, *args, **kwargs):
        dashboard = self.get_object()
        if dashboard.status != DashboardStatus.published:
            # 400 rather than an idempotent 204, following
            # FormBuilderViewSet.unpublish: this is a button-triggered
            # state transition, and a caller arriving from a stale UI is
            # better told than silently agreed with.
            return Response(
                {"message": "Dashboard is not published"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # published_config is deliberately left in place. The read
        # namespace filters on status, so clearing it would destroy the
        # record of what was last live without changing what any caller
        # can reach.
        dashboard.status = DashboardStatus.draft
        dashboard.save(update_fields=["status"])
        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    def duplicate(self, request, *args, **kwargs):
        source = self.get_object()
        live = Dashboard.objects.for_user(request.user)
        with transaction.atomic():
            clone = Dashboard.objects.create(
                name=copy_name(source.name),
                slug=copy_slug(source.slug, live),
                description=source.description,
                # From the caller, never copied from the source: a
                # duplicate must not be able to move a dashboard into
                # another workspace (MT-004).
                tenant=getattr(request.user, "tenant", None),
                root_form=source.root_form,
                created_by=request.user,
                # Copied, not shared: the source's dict must not become
                # reachable through two rows.
                default_filters=dict(source.default_filters or {}),
                # A clone is a draft with no publication history of its
                # own. published_config and published_at are model
                # defaults, spelled out here because dropping them is
                # the point of the operation.
                status=DashboardStatus.draft,
                published_config=None,
                published_at=None,
            )
            DashboardWidget.objects.bulk_create(
                [
                    DashboardWidget(
                        dashboard=clone,
                        order=widget.order,
                        type=widget.type,
                        col_span=widget.col_span,
                        title=widget.title,
                        color=widget.color,
                        form_id=widget.form_id,
                        question_id=widget.question_id,
                        config=widget.config,
                    )
                    for widget in source.widgets.order_by("order", "id")
                ]
            )
        return Response(
            DashboardListSerializer(instance=clone).data,
            status=status.HTTP_201_CREATED,
        )

    def sources(self, request, *args, **kwargs):
        # This endpoint IS the family boundary as the UI sees it: if a
        # form is not here the builder cannot offer it, and if it
        # somehow does, validate_dashboard_payload rejects it on save.
        return Response(
            serialize_sources(self.get_object(), request.user)
        )
