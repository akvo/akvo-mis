from django.test import TestCase, RequestFactory
from django.test.utils import override_settings

from api.v1.v1_users.models import Tenant
from utils.tenant_host import public_tenant


class PublicTenantTestCase(TestCase):
    """Which workspace an anonymous reader is looking at (spec D-4)."""

    def setUp(self):
        self.factory = RequestFactory()
        # Migration 0004_backfill_default_tenant seeds a "default"
        # Tenant row via a data migration, which Django applies to the
        # test database same as any schema migration. Start each test
        # from a known-empty table rather than let that row leak in.
        Tenant.objects.all().delete()

    def anon_request(self, tenant=None):
        request = self.factory.get("/api/v1/dashboards")
        request.tenant = tenant
        return request

    @override_settings(BASE_DOMAIN="app.com")
    def test_the_host_names_the_workspace(self):
        tenant = Tenant.objects.create(subdomain="acme")
        self.assertEqual(public_tenant(self.anon_request(tenant)), tenant)

    @override_settings(BASE_DOMAIN="app.com")
    def test_the_base_domain_names_none(self):
        Tenant.objects.create(subdomain="acme")
        self.assertIsNone(public_tenant(self.anon_request(None)))

    @override_settings(BASE_DOMAIN="")
    def test_single_host_resolves_the_sole_tenant(self):
        tenant = Tenant.objects.create(subdomain="default")
        self.assertEqual(public_tenant(self.anon_request(None)), tenant)

    @override_settings(BASE_DOMAIN="")
    def test_single_host_with_two_tenants_serves_nothing(self):
        Tenant.objects.create(subdomain="one")
        Tenant.objects.create(subdomain="two")
        self.assertIsNone(public_tenant(self.anon_request(None)))

    @override_settings(BASE_DOMAIN="")
    def test_single_host_with_no_tenants_serves_nothing(self):
        self.assertIsNone(public_tenant(self.anon_request(None)))
