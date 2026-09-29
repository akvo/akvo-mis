"""Endpoints served on a *workspace's* host during an inspection.

They live here rather than in admin_views because they answer on the
tenant host and are authorised by the inspection token rather than by a
console session -- the console's cookie is host-only and never reaches
this origin.
"""
import datetime
import hashlib
import secrets

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response

from api.v1.v1_users.admin_serializers import TenantListSerializer
from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_users.models import Tenant, TenantInspection

INSPECT_TAG = ["Platform Console"]
CODE_TTL_SECONDS = 60


@extend_schema(tags=INSPECT_TAG,
               summary="Exchange a one-time code for an inspection session")
@api_view(["POST"])
@permission_classes([AllowAny])
def exchange_code(request, version):
    """Burn the code, set the cookie, and let the app take over.

    Anonymous by necessity: the browser arriving here holds nothing for
    this origin yet. The code is the credential, and it is single-use
    and 60 seconds old at most.
    """
    invalid = Response(
        {"message": "Invalid or expired inspection link"},
        status=status.HTTP_400_BAD_REQUEST,
    )
    code = request.data.get("code")
    if not code:
        return invalid
    digest = hashlib.sha256(str(code).encode()).hexdigest()
    cutoff = timezone.now() - datetime.timedelta(seconds=CODE_TTL_SECONDS)
    inspection = TenantInspection.objects.filter(
        code_hash=digest, code_used_at=None, created_at__gte=cutoff
    ).first()
    if inspection is None:
        return invalid
    # Burned before the token is minted. A second request racing this
    # one finds code_used_at set and gets the same refusal.
    inspection.code_used_at = timezone.now()
    inspection.save(update_fields=["code_used_at"])

    token = TenantInspectionToken.for_inspection(inspection)
    response = Response(
        {"subdomain": inspection.tenant.subdomain},
        status=status.HTTP_200_OK,
    )
    # Set exactly as login() sets it: host-only, no domain attribute, so
    # the session is confined to this workspace's origin. Because it is
    # the same cookie the app already reads, every existing page works
    # unchanged -- no sessionStorage, no axios interceptor.
    response.set_cookie(
        "AUTH_TOKEN",
        str(token),
        expires=timezone.now() + TenantInspectionToken.lifetime,
    )
    return response


class IsInspecting(BasePermission):
    """Only a live inspection session may use these.

    The operator's status was already re-verified by get_user, so
    reaching here at all means they still hold the flag.
    """

    def has_permission(self, request, view):
        return isinstance(request.auth, TenantInspectionToken)


def switchable():
    """The workspaces an inspection session may move to.

    Suspended and deleted ones are absent because their hosts no longer
    resolve -- offering them would be offering a dead link. The prefetch
    feeds TenantListSerializer.get_name, which reads each workspace's
    root administration unit from the cache rather than querying per
    row.
    """
    return (
        Tenant.objects.filter(is_active=True, deleted_at=None)
        .prefetch_related("administrations")
        .order_by("subdomain")
    )


@extend_schema(tags=INSPECT_TAG,
               summary="Workspaces this session may switch to")
@api_view(["GET"])
@permission_classes([IsInspecting])
def switchable_tenants(request, version):
    return Response(
        TenantListSerializer(switchable(), many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=INSPECT_TAG, summary="Inspect a different workspace")
@api_view(["POST"])
@permission_classes([IsInspecting])
def switch_tenant(request, version):
    """Mint a fresh session for another workspace.

    Authorised by the inspection token itself, because the console's
    cookie is host-only and never reaches this origin. The accepted
    trade is that the token reaches any workspace rather than one; it
    stays read-only, is re-authorised here, and dies the moment the
    operator is revoked.
    """
    tenant = get_object_or_404(switchable(), pk=request.data.get("tenant_id"))
    code = secrets.token_urlsafe(32)
    TenantInspection.objects.create(
        # request.user is the operator, re-verified by get_user on this
        # very request -- so the new row names who really switched.
        operator=request.user,
        tenant=tenant,
        code_hash=hashlib.sha256(code.encode()).hexdigest(),
    )
    return Response(
        {"code": code, "subdomain": tenant.subdomain},
        status=status.HTTP_200_OK,
    )
