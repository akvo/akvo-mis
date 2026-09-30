from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser, Tenant
from utils.tenant_host import (
    is_admin_host,
    resolve_tenant_from_host,
)


@override_settings(BASE_DOMAIN="app.com")
class AdminHostTestCase(TestCase):
    """The console gets a host of its own, outside the workspace space.

    Mirrors is_embed_host: host parsing lives in one module, so a
    custom-domain tier later has one file to change.
    """

    def setUp(self):
        Tenant.objects.create(subdomain="acme")

    def test_recognises_the_admin_host(self):
        self.assertTrue(is_admin_host("admin.app.com"))
        self.assertTrue(is_admin_host("ADMIN.app.com:3000"))

    def test_rejects_every_other_host(self):
        self.assertFalse(is_admin_host("app.com"))
        self.assertFalse(is_admin_host("acme.app.com"))
        self.assertFalse(is_admin_host("admin.evil.com"))
        self.assertFalse(is_admin_host("sub.admin.app.com"))

    def test_the_admin_host_resolves_to_no_tenant(self):
        self.assertIsNone(resolve_tenant_from_host("admin.app.com"))

    def test_the_admin_host_is_not_a_missing_workspace(self):
        # The middleware 404s an unresolvable host. The console must
        # not be one, or every request to it dies before its view.
        response = self.client.get(
            "/api/v1/tenant-info", HTTP_HOST="admin.app.com"
        )
        self.assertNotEqual(response.status_code, 404)

    def test_registration_refuses_the_reserved_subdomain(self):
        response = self.client.post(
            "/api/v1/register",
            {
                "email": "founder@acme.org",
                "password": "Secret#Pass123",
                "subdomain": "admin",
            },
            content_type="application/json",
            # Registration is served on the base domain; without a host
            # the middleware 404s before the serializer is reached.
            HTTP_HOST="app.com",
        )
        self.assertEqual(response.status_code, 400)


@override_settings(BASE_DOMAIN="app.com")
class AdminHostCollisionTestCase(TestCase, TenantTestHelperMixin):
    """A workspace registered at the console's label before it was
    reserved.

    Nothing blocks this: which label the console uses is a decision the
    deployment may revisit, so refusing to migrate over a pre-existing
    row would trade a rare operational chore for a permanent
    constraint. The fix is to rename that workspace.

    What matters is that the collision cannot be turned into an
    escalation. It locks the host for everyone -- the squatter cannot
    reach their workspace and the operator cannot reach the console --
    rather than handing either one the other's powers.
    """

    def setUp(self):
        self.squatter = self.create_tenant("admin", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )

    def test_the_squatting_workspace_gains_no_console_access(self):
        response = self.client.get(
            "/api/v1/admin/tenants",
            HTTP_HOST="admin.app.com",
            **self.bearer(self.squatter.admin),
        )
        self.assertIn(response.status_code, (401, 403))

    def test_the_operator_cannot_be_impersonated_into_that_workspace(self):
        # The host resolves to the squatter, so the middleware sees a
        # tenant-less account on a workspace host and refuses it. An
        # operator locked out is the right side to fail on.
        response = self.client.get(
            "/api/v1/admin/tenants",
            HTTP_HOST="admin.app.com",
            **self.bearer(self.operator),
        )
        self.assertEqual(response.status_code, 403)

    def test_every_other_workspace_is_unaffected(self):
        beta = self.create_tenant("beta", ["Country"], "Uganda")
        response = self.client.get(
            "/api/v1/profile",
            HTTP_HOST="beta.app.com",
            **self.bearer(beta.admin),
        )
        self.assertEqual(response.status_code, 200)


class AdminHostInertTestCase(TestCase):
    """With no base domain there is no console. This is how mohhs,
    unicef-fsm and the whole test suite run."""

    def test_inert_without_a_base_domain(self):
        self.assertFalse(is_admin_host("admin.app.com"))
