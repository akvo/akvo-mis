"""Tenant-aware authentication backend.

Scopes authenticate() to the tenant supplied via the ``tenant`` keyword
argument. Replaces ModelBackend to ensure non-unique emails across tenants
do not raise MultipleObjectsReturned during authentication or fallthrough.
"""

from django.contrib.auth.backends import ModelBackend
from api.v1.v1_users.models import SystemUser


class TenantAwareBackend(ModelBackend):
    """Authenticate against a (email, password, tenant) triple."""

    def authenticate(
        self,
        request,
        email=None,
        password=None,
        tenant=None,
        tenant_less_only=False,
        **kwargs
    ):
        if not email or not password:
            return None

        if tenant is not None:
            # Query with deleted so views.py can distinguish deleted users
            user = SystemUser.objects_with_deleted.filter(
                email=email,
                tenant=tenant,
            ).first()
            if user is None:
                SystemUser().set_password(password)
                return None
            if user.check_password(password):
                if user.deleted_at or self.user_can_authenticate(user):
                    return user
            return None

        # When tenant is None (CLI commands, createsuperuser, tests, shell),
        # check all users matching this email and return the one whose password
        # matches.
        users = SystemUser.objects_with_deleted.filter(email=email)
        # The platform console is the one caller for which a null tenant
        # is a *requirement* rather than a missing context: an operator
        # belongs to no workspace. Without this narrowing the loop below
        # walks every workspace on the deployment, and an operator who
        # also holds a workspace account under the same address and
        # password is handed that account instead -- whichever row the
        # database returns first -- and is then refused for not being an
        # operator. It also keeps the console's login form from testing
        # a password against every workspace in the install.
        if tenant_less_only:
            users = users.filter(tenant__isnull=True)
        matched_user = None
        for u in users:
            if u.check_password(password):
                if u.deleted_at or self.user_can_authenticate(u):
                    matched_user = u
                    break

        if matched_user is None:
            SystemUser().set_password(password)
            return None

        return matched_user
