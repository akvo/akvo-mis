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
        self, request, email=None, password=None, tenant=None, **kwargs
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
