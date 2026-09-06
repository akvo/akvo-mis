# =========================================================
# The read namespace: /dashboards (VIZ-007)
# =========================================================
# What a viewer sees, as opposed to what an author edits. Separate from
# DashboardBuilderViewSet because every axis differs: the queryset is
# narrowed to published, the lookup is the slug, the permission is a
# token and nothing more, and the widgets come from the snapshot rather
# than the live rows.
#
# Keeping it a class of its own also keeps the security boundary
# readable: one queryset, unconditionally narrowed, with no action able
# to widen it.
#
# Anonymous readers are the point of this namespace (spec D-3), CLEANUP-
# 001 notwithstanding: that removal was of the previous public
# dashboard, which let an anonymous caller name any form id it liked.
# get_queryset() below is the boundary that replaces it — narrowed to
# published rows unconditionally, and widened only by who is asking.

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.v1.v1_visualization.constants import DashboardKind, DashboardStatus
from api.v1.v1_visualization.dashboard_snapshot import annotate_broken
from api.v1.v1_visualization.embed_views import embed_url_for
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.public_scope import has_any_dashboard_access
from utils.tenant_host import public_tenant

# REST_FRAMEWORK.DATETIME_FORMAT is "%d-%m-%Y %H:%M:%S" project-wide,
# and a ModelSerializer honours it — so the builder's endpoints render
# published_at in that format. A raw datetime dropped into a plain dict
# is rendered by DRF's JSON encoder as ISO-8601 instead, which would
# hand VIZ-008 two different formats for one field depending on which
# endpoint it happened to read. Borrowing the serializer field keeps the
# two identical without turning these responses into serializers.
DATETIME = serializers.DateTimeField()


def read_snapshot(dashboard):
    """`published_config`, tolerant of a row that has none.

    Publish writes the snapshot and the status together, so a published
    row without one is unreachable through the API. Degrading to an
    empty dashboard rather than raising means a row that reached that
    state some other way renders empty instead of 500ing the viewer.
    """
    config = dashboard.published_config or {}
    return {
        "default_filters": config.get("default_filters") or {},
        "widgets": config.get("widgets") or [],
    }


def serialize_identity(dashboard):
    """The fields served live from the row rather than the snapshot.

    Spec D-1: renaming a published dashboard reaches viewers at once,
    because a corrected typo should not require re-publishing work that
    is not finished.

    `root_form` is guarded here, in the one function both `list` and
    `retrieve` call, rather than at either call site: `list` runs this
    over every published row in a tenant, so an unguarded lookup would
    500 the whole anonymous list the moment one public embed (whose
    `root_form` is null by construction) appeared in it.
    """
    form = dashboard.root_form
    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "slug": dashboard.slug,
        "description": dashboard.description,
        "kind": DashboardKind.FieldStr.get(dashboard.kind),
        # None for an embed, which has no form family.
        "root_form": (
            None if form is None
            else {"id": form.id, "name": form.name}
        ),
        # None passes straight through: DateTimeField.to_representation
        # short-circuits on a falsy value.
        "published_at": DATETIME.to_representation(
            dashboard.published_at
        ),
    }


# "Dashboards" for what a viewer reads, "Manage Dashboards" for what an
# author edits — the same split as "Form" and "Manage Forms". Untagged,
# both routes fall back to the first path segment and Swagger files them
# under "v1".
#
# Decorated per method rather than with a class-level @extend_schema_view:
# urls.py wires these through as_view({...}) rather than a router, so
# drf-spectacular does not treat them as registered actions and drops a
# class-level override. `operation_id` is explicit for the same reason —
# both routes otherwise derive "v1_dashboards_retrieve" and collide, and
# spectacular resolves that by appending a numeral, which is neither
# stable nor readable in a generated client.
READ = "Dashboards"


class DashboardReadViewSet(viewsets.GenericViewSet):
    # Anonymous readers are the point of this namespace now (spec D-3).
    # The queryset below is narrowed unconditionally and widened only
    # by who is asking; no action can widen it further.
    permission_classes = [AllowAny]
    # Bare array, same reason as the builder list (VIZ-005 D-1): the
    # merged client does Array.isArray(res.data) ? res.data : [].
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        # status=published and the soft-deletes manager (which drops
        # deleted rows outright) apply to every branch below — the
        # three tiers only ever widen who else's published rows are
        # visible, never what "visible" means.
        user = self.request.user
        rows = Dashboard.objects.filter(
            status=DashboardStatus.published
        ).select_related("root_form")

        if user and user.is_authenticated:
            rows = rows.for_user(user)
            # Any dashboard feature access at all, not `dashboard_view`
            # alone: a role hand-configured with Edit but not View
            # could otherwise build a private dashboard and be unable
            # to open it, which an administrator will create by
            # accident and report as a bug.
            if not has_any_dashboard_access(user):
                rows = rows.filter(is_public=True)
            return rows.order_by("-published_at", "-id")

        tenant = public_tenant(self.request)
        if tenant is None:
            # Serve nothing. Filtering on `tenant IS NULL` would hand
            # tenant-less rows to anonymous callers on the base domain.
            return rows.none()
        return rows.filter(tenant=tenant, is_public=True).order_by(
            "-published_at", "-id"
        )

    @extend_schema(
        tags=[READ],
        operation_id="v1_dashboards_list",
        summary="List published dashboards in the caller's workspace",
        description=(
            "Drafts are not visible here — unpublishing takes effect by "
            "status, so it removes a dashboard from this list at once. "
            "Rows carry widget stubs (type and col_span) for thumbnails, "
            "not annotated widgets (VIZ-007 D-7)."
        ),
    )
    def list(self, request, *args, **kwargs):
        rows = []
        for dashboard in self.get_queryset():
            row = serialize_identity(dashboard)
            # Stubs, not annotated widgets (spec D-7): a card thumbnail
            # renders from type and col_span alone, and annotating every
            # dashboard in the list is work nothing on that screen can
            # display.
            row["widgets"] = [
                {"type": w.get("type"), "col_span": w.get("col_span")}
                for w in read_snapshot(dashboard)["widgets"]
            ]
            rows.append(row)
        return Response(rows)

    @extend_schema(
        tags=[READ],
        operation_id="v1_dashboards_retrieve",
        summary="Read a published dashboard by slug",
        description=(
            "Serves `published_config`, so editing a live dashboard does "
            "not change what colleagues see until it is republished. Name "
            "and description come from the row rather than the snapshot, "
            "so a corrected typo reaches viewers immediately (VIZ-007 "
            "D-1). Widgets are annotated with `is_broken` as they are "
            "served — never baked in at publish time, because a question "
            "can be deleted at any point afterwards."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Dashboard slug, unique within the workspace.",
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        dashboard = self.get_object()
        snapshot = read_snapshot(dashboard)
        row = serialize_identity(dashboard)
        row["default_filters"] = snapshot["default_filters"]
        # A URL on the embed host, not the markup itself: viewers
        # never run a snippet in this origin (VIZ-019 D-4a). None
        # when EMBED_HOST is unconfigured, which the viewer reports.
        row["embed_url"] = embed_url_for(dashboard)
        # Annotated as it is served, never baked in at publish time: a
        # question can be deleted at any point afterwards, and a stale
        # is_broken: false would be worse than no annotation at all.
        row["widgets"] = annotate_broken(
            snapshot["widgets"], dashboard.tenant
        )
        return Response(row)
