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
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_profile.constants import FeatureAccessTypes
from api.v1.v1_visualization.dashboard_builder_serializers import (
    DashboardDetailSerializer,
    DashboardListSerializer,
)
from api.v1.v1_visualization.dashboard_functions import (
    SLUG_PATTERN,
    derive_slug,
    suggest_slug,
    validate_dashboard_payload,
)
from api.v1.v1_visualization.models import Dashboard
from utils.custom_permissions import DashboardAccess


class DashboardBuilderViewSet(viewsets.ModelViewSet):
    # REST_FRAMEWORK.DEFAULT_PAGINATION_CLASS is LimitOffsetPagination
    # project-wide, so simply omitting pagination_class here would still
    # wrap list() in a {count, next, previous, results} envelope. This
    # explicit None is what actually produces the bare array the brief
    # describes and the merged builder requires.
    pagination_class = None

    def get_queryset(self):
        return Dashboard.objects.for_user(self.request.user).order_by(
            "-id"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return DashboardListSerializer
        return DashboardDetailSerializer

    def get_permissions(self):
        perm_map = {
            "list": [
                IsAuthenticated,
                DashboardAccess(FeatureAccessTypes.dashboard_view),
            ],
            "create": [
                IsAuthenticated,
                DashboardAccess(FeatureAccessTypes.dashboard_create),
            ],
            "retrieve": [
                IsAuthenticated,
                DashboardAccess(FeatureAccessTypes.dashboard_view),
            ],
            "update": [
                IsAuthenticated,
                DashboardAccess(FeatureAccessTypes.dashboard_edit),
            ],
            "destroy": [
                IsAuthenticated,
                DashboardAccess(FeatureAccessTypes.dashboard_delete),
            ],
            "sources": [
                IsAuthenticated,
                DashboardAccess(FeatureAccessTypes.dashboard_view),
            ],
        }
        return [p() for p in perm_map.get(self.action, [IsAuthenticated])]

    def create(self, request, *args, **kwargs):
        error = validate_dashboard_payload(request.data, request.user)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        name = request.data.get("name")
        slug = derive_slug(name, request.data.get("slug"))
        if not SLUG_PATTERN.match(slug):
            return Response(
                {
                    "message": (
                        "name must contain at least one letter or digit"
                    ),
                    "field": "name",
                },
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

        with transaction.atomic():
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
