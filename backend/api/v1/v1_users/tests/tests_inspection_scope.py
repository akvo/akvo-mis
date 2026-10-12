from django.test import TestCase, override_settings

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_users.models import SystemUser, TenantInspection


@override_settings(BASE_DOMAIN="app.com")
class InspectionScopeTestCase(TestCase, TenantTestHelperMixin):
    """An inspection session is one workspace's, and only reads.

    for_user() is untouched. The authentication class swaps the acting
    tenant in memory, so every scoping mechanism resolves to the
    inspected workspace without any of them knowing about inspection.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.beta = self.create_tenant("beta", ["Country"], "Uganda")
        Forms.objects.create(
            name="acme-form", tenant=self.acme.tenant,
            status=FormStatus.published,
        )
        Forms.objects.create(
            name="beta-form", tenant=self.beta.tenant,
            status=FormStatus.published,
        )
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.inspection = TenantInspection.objects.create(
            operator=self.operator, tenant=self.acme.tenant,
            code_hash="x" * 64,
        )
        token = TenantInspectionToken.for_inspection(self.inspection)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def get(self, path):
        return self.client.get(path, HTTP_HOST="acme.app.com", **self.auth)

    def test_profile_reports_the_inspection(self):
        response = self.get("/api/v1/profile")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_inspecting"])

    def test_the_session_reads_the_inspected_workspace(self):
        response = self.get("/api/v1/forms/published")
        self.assertEqual(response.status_code, 200)
        names = [form["name"] for form in response.json()]
        self.assertIn("acme-form", names)
        self.assertNotIn("beta-form", names)

    def test_an_ordinary_session_never_reports_inspecting(self):
        response = self.client.get(
            "/api/v1/profile", HTTP_HOST="acme.app.com",
            **self.bearer(self.acme.admin),
        )
        self.assertFalse(response.json()["is_inspecting"])

    def test_the_swap_is_never_persisted(self):
        self.get("/api/v1/profile")
        self.operator.refresh_from_db()
        # UserActivity re-fetches by pk and saves only last_login, so
        # the in-memory tenant and is_superuser cannot reach the row.
        self.assertIsNone(self.operator.tenant_id)
        self.assertFalse(self.operator.is_superuser)
