"""Platform console endpoints.

Every view here queries `Tenant.objects` directly rather than through
`for_user()`. That is deliberate and visible: an operator is
tenant-less, so `for_user` would filter on `tenant IS NULL` and return
nothing. Cross-tenant reading has to be opted into explicitly, and this
module is the only place it happens.

Nothing here returns a workspace's data. There is no delete endpoint
for datapoints or dashboards anywhere under /admin/ -- the absence is
the enforcement, not a flag.
"""
import logging
import os

from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.admin_serializers import (
    TenantFeaturesSerializer,
    TenantListSerializer,
    TenantRenameSerializer,
    TenantSummarySerializer,
)
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.models import Dashboard
from utils.custom_generator import sqlite_path
from utils.custom_permissions import IsPlatformAdmin
from utils.tenant_host import tenant_may_embed

logger = logging.getLogger(__name__)

CONSOLE_TAG = ["Platform Console"]


def console_tenants():
    """Every workspace, deleted ones included.

    The console is the one reader that must see a deleted workspace:
    it is the only place its state can be explained.

    The prefetch is for `TenantListSerializer.get_name`, which reads the
    root administration unit of every row. Without it the cost of
    listing is one query per workspace.
    """
    return (
        Tenant.objects.all()
        .prefetch_related("administrations")
        .order_by("subdomain")
    )


@extend_schema(responses={200: TenantListSerializer(many=True)},
               tags=CONSOLE_TAG, summary="List every workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def list_tenants(request, version):
    queryset = console_tenants()
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(subdomain__icontains=search)
    return Response(
        TenantListSerializer(queryset, many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(responses={200: TenantListSerializer}, tags=CONSOLE_TAG,
               summary="One workspace, or soft-delete it")
@api_view(["GET", "DELETE"])
@permission_classes([IsPlatformAdmin])
def tenant_detail(request, version, tenant_id):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    if request.method == "DELETE":
        # Soft only. Every tenant FK is PROTECT, so a hard delete would
        # raise -- and making it work means flipping those to CASCADE
        # across every tenant-owned model, which is a separate and much
        # riskier piece of work.
        tenant.deleted_at = timezone.now()
        tenant.save(update_fields=["deleted_at"])
    return Response(
        TenantListSerializer(tenant).data, status=status.HTTP_200_OK
    )


@extend_schema(responses={200: TenantListSerializer}, tags=CONSOLE_TAG,
               summary="Suspend a workspace")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def deactivate_tenant(request, version, tenant_id):
    return _set_active(tenant_id, False)


@extend_schema(responses={200: TenantListSerializer}, tags=CONSOLE_TAG,
               summary="Restore a suspended workspace")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def activate_tenant(request, version, tenant_id):
    return _set_active(tenant_id, True)


def _set_active(tenant_id, active):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    tenant.is_active = active
    tenant.save(update_fields=["is_active"])
    return Response(
        TenantListSerializer(tenant).data, status=status.HTTP_200_OK
    )


@extend_schema(request=TenantFeaturesSerializer,
               responses={200: TenantListSerializer}, tags=CONSOLE_TAG,
               summary="Set a workspace's entitlements")
@api_view(["PUT"])
@permission_classes([IsPlatformAdmin])
def set_tenant_features(request, version, tenant_id):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    serializer = TenantFeaturesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Merged rather than replaced: the console sends the switches it
    # knows about, and a flag added in a later release must not be
    # cleared by an older client that has never heard of it.
    features = dict(tenant.features or {})
    features.update(serializer.validated_data)
    tenant.features = features
    try:
        tenant.save(update_fields=["features"])
    except IntegrityError:
        return Response(
            {"message": "Could not save entitlements"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        TenantListSerializer(tenant).data, status=status.HTTP_200_OK
    )


@extend_schema(responses={200: TenantSummarySerializer(many=True)},
               tags=CONSOLE_TAG, summary="Counts for every workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def tenants_summary(request, version):
    """How much is in each workspace, at a cost that does not grow.

    Every Count carries distinct=True because the joins multiply:
    counting forms and users in the same query without it returns
    forms x users for both. The soft-delete filters are part of the
    count rather than applied afterwards, so a deleted datapoint is
    never counted and never has to be subtracted.
    """
    queryset = console_tenants().annotate(
        # `_count` suffixes because Django refuses an annotation that
        # shadows a field or reverse accessor, and three of these five
        # are reverse accessors on Tenant. The serializer sources the
        # plain names from these.
        users_count=Count(
            "users", distinct=True, filter=Q(users__deleted_at=None)
        ),
        forms_count=Count(
            "forms", distinct=True, filter=Q(forms__deleted_at=None)
        ),
        dashboards_count=Count(
            "dashboards", distinct=True,
            filter=Q(dashboards__deleted_at=None),
        ),
        datapoints_count=Count(
            "forms__form_form_data", distinct=True,
            filter=Q(forms__form_form_data__deleted_at=None),
        ),
        devices_count=Count("users__mobile_assignments", distinct=True),
    )
    return Response(
        TenantSummarySerializer(queryset, many=True).data,
        status=status.HTTP_200_OK,
    )


def rename_impact(tenant):
    """What renaming this workspace will break.

    Counted from the workspace rather than stated generally, because a
    dialog that names 23 devices is not clicked through the way a
    generic warning is.
    """
    return {
        # Every enrolled device stores serverURL locally and never
        # re-fetches it; MobileAssignmentToken lasts 99999 days, so
        # they never re-authenticate either. Each one has to be
        # reconfigured by hand.
        "mobile_devices": MobileAssignment.objects.filter(
            user__tenant=tenant
        ).count(),
        "published_dashboards": Dashboard.objects.filter(
            tenant=tenant, deleted_at=None
        ).exclude(published_config=None).count(),
        "embedded_dashboards": (
            Dashboard.objects.filter(tenant=tenant, deleted_at=None)
            .exclude(embed_snippet=None)
            .exclude(embed_snippet="")
            .count()
            if tenant_may_embed(tenant)
            else 0
        ),
    }


@extend_schema(tags=CONSOLE_TAG,
               summary="What a rename would break for this workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def tenant_rename_impact(request, version, tenant_id):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    return Response(rename_impact(tenant), status=status.HTTP_200_OK)


@extend_schema(request=TenantRenameSerializer,
               responses={200: TenantListSerializer}, tags=CONSOLE_TAG,
               summary="Change a workspace's address")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def rename_tenant(request, version, tenant_id):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    serializer = TenantRenameSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    previous = tenant.subdomain
    tenant.subdomain = serializer.validated_data["subdomain"]
    try:
        tenant.save(update_fields=["subdomain"])
    except IntegrityError:
        # Uniqueness is the database's, as it is at registration. A
        # pre-check would only be a read before a write.
        return Response(
            {"message": "Subdomain is already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    _move_master_data(previous, tenant)
    return Response(
        TenantListSerializer(tenant).data, status=status.HTTP_200_OK
    )


def _move_master_data(previous, tenant):
    """Follow the device SQLite files to the new subdomain.

    Best effort, and deliberately not fatal. `download_sqlite_file`
    regenerates a missing file on the next device sync, so the worst
    case here is one slow sync and some orphaned files -- while failing
    the rename after the row has moved would leave the workspace half
    renamed, which is far worse.
    """
    new_dir = os.path.dirname(sqlite_path(Administration, tenant=tenant))
    old_dir = os.path.join(os.path.dirname(new_dir), previous)
    if not os.path.isdir(old_dir) or os.path.exists(new_dir):
        return
    try:
        os.rename(old_dir, new_dir)
    except OSError:
        logger.warning(
            "Could not move master data from %s to %s; the files will "
            "regenerate on the next device sync.", old_dir, new_dir,
        )
