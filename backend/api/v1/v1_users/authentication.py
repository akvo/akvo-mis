"""Authentication for a read-only cross-workspace inspection session.

The token carries the workspace to act as. `for_user()` is not modified
anywhere in this feature -- instead `get_user` hands back an operator
whose tenant has been swapped in memory, and every existing scoping
mechanism resolves from there. That is what lets the entire existing
React app work unchanged against someone else's workspace.
"""
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.tokens import AccessToken

from api.v1.v1_mobile.authentication import AssignmentAwareJWTAuthentication
from api.v1.v1_users.models import SystemUser, Tenant

# The one write an inspection session may make: a fresh code row for the
# workspace it is moving to. Named as a path rather than inferred from
# anything, so allowing a second write means editing this line on
# purpose. Both read-only guards consult it.
INSPECTION_WRITE_PATHS = ("/api/v1/inspect/switch",)

# The other direction: paths refused whatever the method, because they
# write on a GET. Both of these queue a Jobs row and a django_q task
# from a plain GET, so a method test alone lets a "read-only" session
# create rows and buy worker time indefinitely.
#
# The method is a sound proxy for "writes" everywhere else in this API
# -- a sweep of every GET-only view found no other that touches a row --
# but where it is not, the exception is named rather than inferred, the
# same shape as the allowlist above. Whoever writes the next mutating
# GET adds it here.
INSPECTION_BLOCKED_PATHS = (
    "/api/v1/download/generate",
    "/api/v1/download/datapoint-report",
)


def inspection_write_refused(method, path):
    """Would this request write, for an inspection session?

    One definition, called by both guards. They detect the token
    independently -- that is what makes two guards worth more than one
    -- but they must not disagree about what counts as a write, because
    then each would be enforcing a different rule and neither the whole
    one.
    """
    if path.startswith(INSPECTION_BLOCKED_PATHS):
        return True
    if method in SAFE_METHODS:
        return False
    return path not in INSPECTION_WRITE_PATHS


class TenantInspectionToken(AccessToken):
    token_type = "tenant_inspection"
    lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]

    @classmethod
    def for_inspection(cls, inspection):
        token = cls()
        token["operator_id"] = inspection.operator_id
        token["tenant_id"] = inspection.tenant_id
        return token


class InspectionAwareJWTAuthentication(AssignmentAwareJWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        _, token = result
        # Guard two of two. It lives in authentication, not in a
        # permission class, because this project sets no
        # DEFAULT_PERMISSION_CLASSES and DRF's per-view
        # permission_classes *replaces* the default rather than
        # composing with it -- so a permission-class guard would apply
        # to no view that declares its own permissions, which is every
        # view here. Authentication runs for every DRF request whatever
        # the view declares, and cannot be switched off by adding an
        # endpoint.
        if isinstance(token, TenantInspectionToken):
            if inspection_write_refused(request.method, request.path):
                raise PermissionDenied(
                    "This inspection session is read only"
                )
        return result

    def get_user(self, validated_token):
        if not isinstance(validated_token, TenantInspectionToken):
            return super().get_user(validated_token)

        # Re-checked on every request rather than trusted from the
        # token. Revoking an operator ends every live inspection at
        # once, which no token lifetime can do; the cost is one indexed
        # primary-key lookup.
        operator = SystemUser.objects.filter(
            pk=validated_token["operator_id"],
            is_platform_admin=True,
            is_active=True,
            deleted_at=None,
        ).first()
        if operator is None:
            raise AuthenticationFailed("Operator access revoked")

        tenant = Tenant.objects.filter(
            pk=validated_token["tenant_id"], is_active=True, deleted_at=None
        ).first()
        if tenant is None:
            raise AuthenticationFailed("Workspace is no longer available")

        # In memory only. The sole write path on the request user is
        # UserActivity, which re-fetches by pk and saves last_login
        # alone, so neither attribute can reach the database.
        #
        # is_superuser is necessary, not incidental: an operator holds
        # no role rows in this workspace, so without it ability.js and
        # every FeatureAccess check would produce a crippled view that
        # looks right and behaves wrong. It is a synthetic state no real
        # user holds, and it goes away when user impersonation lands.
        operator.tenant = tenant
        operator.is_superuser = True
        operator.is_inspecting = True
        return operator
