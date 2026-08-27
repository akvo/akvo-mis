# =========================================================
# The public namespace: /public/dashboards (VIZ-010)
# =========================================================
# The only anonymous surface in the app. VIZ-001 D-7 ruled one out and
# named the condition for reversing it — "a deliberate feature with its
# own token model" — and this is that feature.
#
# Three properties make it safe, and all three are structural rather than
# checked:
#
# 1. The tenant comes from the host (D-2). `TenantMiddleware` has already
#    resolved it and 404'd a host that names no workspace, so a request
#    here either belongs to exactly one tenant or never arrives. The base
#    domain resolves to None and is refused below, because a workspace's
#    dashboards are not the signup page's to serve.
#
# 2. The caller names a dashboard and a widget, never a form (D-3). There
#    is no `form_id` on the wire to enumerate, and no query grammar for an
#    anonymous caller to author. Contrast /visualization/values, which
#    takes a sequential form id straight from the query string.
#
# 3. Publication and visibility are both required (D-5). Unpublishing
#    removes a dashboard from here immediately, because the queryset
#    filters on status rather than on published_config being present.
#
# Everything not found is 404, never 403: a 403 confirms the slug exists,
# which is the leak in miniature.

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.v1.v1_profile.models import Administration
from api.v1.v1_visualization.constants import (
    DashboardStatus,
    DashboardVisibility,
)
from api.v1.v1_visualization.dashboard_read_views import (
    read_snapshot,
    serialize_identity,
)
from api.v1.v1_visualization.dashboard_snapshot import (
    annotate_broken_for_tenant,
)
from api.v1.v1_visualization.dashboard_widget_data import (
    resolve_widget_data,
)
from api.v1.v1_visualization.models import Dashboard


def public_filters(request, dashboard):
    """The caller's entire input surface (VIZ-001 §4.4).

    Anything else a caller sends is ignored rather than rejected — an
    unknown parameter is not an attack, it is a stale bookmark — but an
    administration outside this dashboard's tenant is a 400, because
    honouring it would narrow one workspace's dashboard by another's
    geography.
    """
    params = request.query_params
    administration_id = params.get("administration_id")
    if administration_id:
        exists = Administration.objects.filter(
            pk=administration_id
        ).exists()
        if not exists:
            raise ValidationError(
                {"administration_id": "not found"}
            )
    return {
        "from_date": params.get("from_date"),
        "to_date": params.get("to_date"),
        "administration_id": administration_id,
        "page": params.get("page") or 1,
    }


class PublicDashboardViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            # The base domain, or a deployment with BASE_DOMAIN unset.
            # Neither names a workspace, so neither has public
            # dashboards to serve.
            return Dashboard.objects.none()
        return (
            Dashboard.objects.for_tenant(tenant)
            .filter(
                status=DashboardStatus.published,
                visibility=DashboardVisibility.public,
            )
            .select_related("root_form")
            .order_by("-published_at", "-id")
        )

    def list(self, request, *args, **kwargs):
        rows = []
        for dashboard in self.get_queryset():
            row = serialize_identity(dashboard)
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
        row["widgets"] = annotate_broken_for_tenant(
            snapshot["widgets"], request.tenant
        )
        return Response(row)

    @action(detail=True, url_path=r"widgets/(?P<widget_id>[0-9]+)/data")
    def widget_data(self, request, widget_id=None, **kwargs):
        dashboard = self.get_object()
        widgets = annotate_broken_for_tenant(
            read_snapshot(dashboard)["widgets"], request.tenant
        )
        widget = next(
            (w for w in widgets if str(w.get("id")) == str(widget_id)),
            None,
        )
        if widget is None:
            # A widget id from another dashboard is indistinguishable
            # from one that never existed, which is the point.
            raise NotFound()
        data = resolve_widget_data(
            dashboard, widget, public_filters(request, dashboard)
        )
        return Response({"data": data})
