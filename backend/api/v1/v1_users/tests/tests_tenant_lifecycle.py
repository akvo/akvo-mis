from django.test import TestCase, override_settings
from django.utils import timezone

from api.v1.v1_profile.tests.mixins import (
    TENANT_PASSWORD,
    TenantTestHelperMixin,
)
from utils.tenant_host import resolve_tenant_from_host


@override_settings(BASE_DOMAIN="app.com")
class TenantLifecycleTestCase(TestCase, TenantTestHelperMixin):
    """Suspension and deletion are enforced in one place.

    `resolve_tenant_from_host` filters, so an unreachable workspace
    produces the same 404 a typo'd subdomain does and no caller has to
    learn a new state -- including a request carrying a JWT minted
    before the suspension.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.token = self.bearer(self.acme.admin)

    def test_defaults_are_active(self):
        self.assertTrue(self.acme.tenant.is_active)
        self.assertIsNone(self.acme.tenant.deleted_at)
        self.assertEqual(self.acme.tenant.features, {})

    def test_active_tenant_resolves(self):
        self.assertIsNotNone(resolve_tenant_from_host("acme.app.com"))

    def test_suspended_tenant_stops_resolving(self):
        self.acme.tenant.is_active = False
        self.acme.tenant.save(update_fields=["is_active"])
        self.assertIsNone(resolve_tenant_from_host("acme.app.com"))

    def test_deleted_tenant_stops_resolving(self):
        self.acme.tenant.deleted_at = timezone.now()
        self.acme.tenant.save(update_fields=["deleted_at"])
        self.assertIsNone(resolve_tenant_from_host("acme.app.com"))

    def test_a_live_session_dies_on_suspension(self):
        # The whole point of filtering in the resolver: without it this
        # session keeps working for the remaining 12 hours of its token.
        ok = self.client.get("/api/v1/profile", HTTP_HOST="acme.app.com",
                             **self.token)
        self.assertEqual(ok.status_code, 200)
        self.acme.tenant.is_active = False
        self.acme.tenant.save(update_fields=["is_active"])
        refused = self.client.get("/api/v1/profile",
                                  HTTP_HOST="acme.app.com", **self.token)
        self.assertEqual(refused.status_code, 404)

    def test_login_is_refused_while_suspended(self):
        self.acme.tenant.is_active = False
        self.acme.tenant.save(update_fields=["is_active"])
        response = self.client.post(
            "/api/v1/login",
            {"email": self.acme.admin.email, "password": TENANT_PASSWORD},
            HTTP_HOST="acme.app.com",
        )
        self.assertEqual(response.status_code, 404)

    def test_reactivation_restores_everything(self):
        self.acme.tenant.is_active = False
        self.acme.tenant.save(update_fields=["is_active"])
        self.acme.tenant.is_active = True
        self.acme.tenant.save(update_fields=["is_active"])
        response = self.client.get("/api/v1/profile",
                                   HTTP_HOST="acme.app.com", **self.token)
        self.assertEqual(response.status_code, 200)
