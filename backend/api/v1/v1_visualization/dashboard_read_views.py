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
# Authenticated, unlike /api/v1/forms. There is no anonymous dashboard
# surface — that is the CLEANUP-001 fix, and the reason the legacy
# /dashboard/:slug route goes away in VIZ-009.

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.dashboard_snapshot import annotate_broken
from api.v1.v1_visualization.models import Dashboard

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
    """
    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "slug": dashboard.slug,
        "description": dashboard.description,
        "root_form": {
            "id": dashboard.root_form_id,
            "name": dashboard.root_form.name,
        },
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
    # A dashboard is published *to the tenant*, so a token is the whole
    # requirement — no dashboard feature access on top of it.
    permission_classes = [IsAuthenticated]
    # Bare array, same reason as the builder list (VIZ-005 D-1): the
    # merged client does Array.isArray(res.data) ? res.data : [].
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        # Three filters, none of them optional: the soft-deletes manager
        # drops deleted rows, for_user applies the tenant, and status
        # applies publication. Unpublishing takes effect here rather
        # than by clearing published_config.
        return (
            Dashboard.objects.for_user(self.request.user)
            .filter(status=DashboardStatus.published)
            .select_related("root_form")
            .order_by("-published_at", "-id")
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
        # Annotated as it is served, never baked in at publish time: a
        # question can be deleted at any point afterwards, and a stale
        # is_broken: false would be worse than no annotation at all.
        row["widgets"] = annotate_broken(
            snapshot["widgets"], request.user
        )
        return Response(row)
