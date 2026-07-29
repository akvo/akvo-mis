from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


class TenantIsolationTestCase(TestCase):
    """Two tenants, each with its own hierarchy, superadmin and form.

    Every isolation test asks the same question — can tenant A reach
    tenant B's rows — so the fixture lives here and each app extends
    make_tenant with whatever it needs to answer that for its endpoints.
    """

    def make_tenant(self, sub):
        tenant = Tenant.objects.create(subdomain=sub)
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        child_level = Levels.objects.create(
            name="district", level=1, tenant=tenant
        )
        root = Administration.objects.create(
            parent=None, level=level, name=sub, tenant=tenant
        )
        # Datapoints hang off a child unit, not the root: list endpoints
        # filter on administration__path__startswith, and a root's path
        # is NULL, so data parked on the root is invisible to its owner.
        child = Administration.objects.create(
            parent=root, level=child_level, name=f"{sub}-d", tenant=tenant
        )
        user = SystemUser.objects.create_superuser(
            email=f"admin@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        form = Forms.objects.create(
            name=f"{sub}-form", tenant=tenant, status=FormStatus.published
        )
        return {
            "tenant": tenant, "user": user, "form": form,
            "root": root, "child": child,
            "level": level, "child_level": child_level,
        }

    def auth(self, user):
        return {
            "HTTP_AUTHORIZATION":
                f"Bearer {RefreshToken.for_user(user).access_token}"
        }

    def setUp(self):
        self.a = self.make_tenant("acme")
        self.b = self.make_tenant("beta")
