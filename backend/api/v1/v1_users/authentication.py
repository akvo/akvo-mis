"""Authentication for a read-only cross-workspace inspection session.

The token carries the workspace to act as. `for_user()` is not modified
anywhere in this feature -- instead `get_user` hands back an operator
whose tenant has been swapped in memory, and every existing scoping
mechanism resolves from there. That is what lets the entire existing
React app work unchanged against someone else's workspace.
"""
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken


class TenantInspectionToken(AccessToken):
    token_type = "tenant_inspection"
    lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]

    @classmethod
    def for_inspection(cls, inspection):
        token = cls()
        token["operator_id"] = inspection.operator_id
        token["tenant_id"] = inspection.tenant_id
        return token

    @classmethod
    def for_user(cls, _):
        raise NotImplementedError(
            ".for_user() is not used on this token type."
        )
