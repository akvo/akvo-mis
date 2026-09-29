"""Endpoints served on a *workspace's* host during an inspection.

They live here rather than in admin_views because they answer on the
tenant host and are authorised by the inspection token rather than by a
console session -- the console's cookie is host-only and never reaches
this origin.
"""
import datetime
import hashlib

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_users.models import TenantInspection

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
