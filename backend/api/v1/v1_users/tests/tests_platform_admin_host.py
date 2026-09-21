from django.test import TestCase, override_settings

from api.v1.v1_users.models import Tenant
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


class AdminHostInertTestCase(TestCase):
    """With no base domain there is no console. This is how mohhs,
    unicef-fsm and the whole test suite run."""

    def test_inert_without_a_base_domain(self):
        self.assertFalse(is_admin_host("admin.app.com"))
