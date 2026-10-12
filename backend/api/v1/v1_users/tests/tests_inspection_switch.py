import json

from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_users.models import SystemUser, TenantInspection


@override_settings(BASE_DOMAIN="app.com")
class InspectionSwitchTestCase(TestCase, TenantTestHelperMixin):
    """Move between workspaces without returning to the console.

    The console and a workspace are different origins, so the tenant
    host cannot call /admin/* with the operator's console cookie. This
    endpoint is authorised by the inspection token instead.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.beta = self.create_tenant("beta", ["Country"], "Uganda")
        self.sleman = self.create_tenant("sleman", ["Country"], "Indonesia")
        self.sleman.tenant.is_active = False
        self.sleman.tenant.save(update_fields=["is_active"])
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        inspection = TenantInspection.objects.create(
            operator=self.operator, tenant=self.acme.tenant,
            code_hash="a" * 64,
        )
        token = TenantInspectionToken.for_inspection(inspection)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def switch(self, tenant_id):
        return self.client.post(
            "/api/v1/inspect/switch",
            json.dumps({"tenant_id": tenant_id}),
            content_type="application/json",
            HTTP_HOST="acme.app.com",
            **self.auth,
        )

    def test_lists_switchable_workspaces(self):
        response = self.client.get(
            "/api/v1/inspect/tenants", HTTP_HOST="acme.app.com", **self.auth
        )
        self.assertEqual(response.status_code, 200)
        subdomains = [row["subdomain"] for row in response.json()]
        self.assertIn("beta", subdomains)
        # A suspended workspace's host does not resolve, so offering it
        # would be offering a dead link.
        self.assertNotIn("sleman", subdomains)

    def test_the_list_names_each_workspace(self):
        # The dropdown shows the human label, which lives on the root
        # administration unit rather than in a column of its own.
        response = self.client.get(
            "/api/v1/inspect/tenants", HTTP_HOST="acme.app.com", **self.auth
        )
        names = {row["subdomain"]: row["name"] for row in response.json()}
        self.assertEqual(names["beta"], "Uganda")

    def test_switch_returns_a_code_and_records_the_visit(self):
        response = self.switch(self.beta.tenant.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn("code", response.json())
        self.assertEqual(response.json()["subdomain"], "beta")
        self.assertEqual(
            TenantInspection.objects.filter(
                tenant=self.beta.tenant
            ).count(),
            1,
        )

    def test_the_new_code_names_the_operator_who_switched(self):
        self.switch(self.beta.tenant.pk)
        record = TenantInspection.objects.get(tenant=self.beta.tenant)
        self.assertEqual(record.operator_id, self.operator.pk)
        self.assertIsNone(record.code_used_at)

    def test_switch_to_a_suspended_workspace_is_refused(self):
        self.assertEqual(self.switch(self.sleman.tenant.pk).status_code, 404)

    def test_a_revoked_operator_cannot_switch(self):
        self.operator.is_platform_admin = False
        self.operator.save(update_fields=["is_platform_admin"])
        self.assertEqual(self.switch(self.beta.tenant.pk).status_code, 401)

    def test_an_ordinary_session_cannot_switch(self):
        response = self.client.post(
            "/api/v1/inspect/switch",
            json.dumps({"tenant_id": self.beta.tenant.pk}),
            content_type="application/json",
            HTTP_HOST="acme.app.com",
            **self.bearer(self.acme.admin),
        )
        self.assertIn(response.status_code, (401, 403))

    def test_the_exemption_is_only_for_switching(self):
        # The guards let this one POST through by name. Nothing else on
        # /inspect/ may be written, or the exemption has become a hole.
        response = self.client.post(
            "/api/v1/inspect/exchange",
            json.dumps({"code": "whatever"}),
            content_type="application/json",
            HTTP_HOST="acme.app.com",
            **self.auth,
        )
        self.assertEqual(response.status_code, 403)
