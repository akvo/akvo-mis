from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import (
    TENANT_PASSWORD,
    TenantTestHelperMixin,
)
from api.v1.v1_users.models import SystemUser

LOGIN = "/api/v1/login"
OPERATOR_PASSWORD = "Secret#Pass123"


@override_settings(BASE_DOMAIN="app.com")
class PlatformAdminLoginTestCase(TestCase, TenantTestHelperMixin):
    """Operators sign in at the console; everyone else does not.

    The console must not become an oracle for which addresses exist in
    which workspace, so a workspace account typed in here is refused
    with the message the base domain already gives.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.operator.set_password(OPERATOR_PASSWORD)
        self.operator.save()

    def operator_credentials(self):
        return {"email": "ops@akvo.org", "password": OPERATOR_PASSWORD}

    def workspace_credentials(self):
        return {
            "email": self.acme.admin.email,
            "password": TENANT_PASSWORD,
        }

    def test_operator_signs_in_on_the_admin_host(self):
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="admin.app.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_workspace_account_is_refused_on_the_admin_host(self):
        response = self.client.post(
            LOGIN, self.workspace_credentials(), HTTP_HOST="admin.app.com"
        )
        self.assertEqual(response.status_code, 400)

    def test_operator_is_refused_on_a_workspace_host(self):
        # TenantAwareBackend scopes the lookup to the host's tenant, and
        # an operator's tenant is NULL, so no row matches and the view
        # answers with its generic credentials failure.
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="acme.app.com"
        )
        self.assertEqual(response.status_code, 401)

    def test_operator_is_refused_on_the_base_domain(self):
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="app.com"
        )
        self.assertEqual(response.status_code, 400)
