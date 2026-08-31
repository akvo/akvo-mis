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
