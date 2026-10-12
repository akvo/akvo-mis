from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_users.models import SystemUser, TenantInspection


@override_settings(BASE_DOMAIN="app.com")
class InspectionRevocationTestCase(TestCase, TenantTestHelperMixin):
    """Revoking an operator ends live inspections immediately.

    This is what a token lifetime cannot do, and why the lifetime is 12
    hours rather than something artificially short.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        inspection = TenantInspection.objects.create(
            operator=self.operator, tenant=self.acme.tenant,
            code_hash="z" * 64,
        )
        token = TenantInspectionToken.for_inspection(inspection)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def profile(self):
        return self.client.get(
            "/api/v1/profile", HTTP_HOST="acme.app.com", **self.auth
        )

    def test_works_while_the_operator_holds_the_flag(self):
        self.assertEqual(self.profile().status_code, 200)

    def test_revoking_the_flag_ends_it(self):
        self.operator.is_platform_admin = False
        self.operator.save(update_fields=["is_platform_admin"])
        self.assertEqual(self.profile().status_code, 401)

    def test_deactivating_the_operator_ends_it(self):
        self.operator.is_active = False
        self.operator.save(update_fields=["is_active"])
        self.assertEqual(self.profile().status_code, 401)

    def test_suspending_the_workspace_ends_it(self):
        self.acme.tenant.is_active = False
        self.acme.tenant.save(update_fields=["is_active"])
        self.assertEqual(self.profile().status_code, 404)
