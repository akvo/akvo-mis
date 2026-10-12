from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser

ADMIN_HOST = "admin.app.com"


@override_settings(BASE_DOMAIN="app.com")
class AdminUsersTestCase(TestCase, TenantTestHelperMixin):
    """An operator can see and deactivate a workspace's people.

    Names, addresses and status only -- never the data they submitted.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.beta = self.create_tenant("beta", ["Country"], "Uganda")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.auth = self.bearer(self.operator)

    def test_lists_only_that_workspaces_users(self):
        response = self.client.get(
            f"/api/v1/admin/tenants/{self.acme.tenant.pk}/users",
            HTTP_HOST=ADMIN_HOST, **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        emails = [row["email"] for row in response.json()]
        self.assertIn(self.acme.admin.email, emails)
        self.assertNotIn(self.beta.admin.email, emails)

    def test_deactivate_then_activate(self):
        pk = self.acme.admin.pk
        response = self.client.post(
            f"/api/v1/admin/users/{pk}/deactivate",
            HTTP_HOST=ADMIN_HOST, **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.acme.admin.refresh_from_db()
        self.assertFalse(self.acme.admin.is_active)
        self.client.post(
            f"/api/v1/admin/users/{pk}/activate",
            HTTP_HOST=ADMIN_HOST, **self.auth,
        )
        self.acme.admin.refresh_from_db()
        self.assertTrue(self.acme.admin.is_active)

    def test_an_operator_cannot_be_deactivated_here(self):
        # Operators are managed on their own page, and letting this
        # endpoint reach one would make "deactivate a workspace user"
        # a way to lock every operator out of the console.
        response = self.client.post(
            f"/api/v1/admin/users/{self.operator.pk}/deactivate",
            HTTP_HOST=ADMIN_HOST, **self.auth,
        )
        self.assertEqual(response.status_code, 404)

    def test_a_workspace_user_is_refused(self):
        response = self.client.get(
            f"/api/v1/admin/tenants/{self.acme.tenant.pk}/users",
            HTTP_HOST=ADMIN_HOST, **self.bearer(self.acme.admin),
        )
        self.assertEqual(response.status_code, 403)
