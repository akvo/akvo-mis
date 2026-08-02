from django.test import TestCase, override_settings

from api.v1.v1_users.models import Tenant
from utils.tenant_host import is_base_domain, resolve_tenant_from_host


@override_settings(BASE_DOMAIN="app.com")
class ResolveTenantFromHostTestCase(TestCase):
    def setUp(self):
        self.acme = Tenant.objects.create(subdomain="acme")

    def test_base_domain_resolves_to_none(self):
        self.assertIsNone(resolve_tenant_from_host("app.com"))
        self.assertIsNone(resolve_tenant_from_host("www.app.com"))

    def test_subdomain_resolves_to_tenant(self):
        self.assertEqual(resolve_tenant_from_host("acme.app.com"), self.acme)

    def test_port_and_case_are_handled(self):
        self.assertEqual(
            resolve_tenant_from_host("ACME.app.com:3000"), self.acme
        )

    def test_unknown_subdomain_resolves_to_none(self):
        self.assertIsNone(resolve_tenant_from_host("nope.app.com"))

    def test_foreign_host_resolves_to_none(self):
        self.assertIsNone(resolve_tenant_from_host("example.org"))

    def test_nested_label_resolves_to_none(self):
        # One label only. "acme.staging.app.com" is not acme's host, and
        # accepting it would let any depth of prefix reach a tenant.
        self.assertIsNone(resolve_tenant_from_host("acme.staging.app.com"))

    @override_settings(BASE_DOMAIN="")
    def test_no_base_domain_configured_resolves_to_none(self):
        self.assertIsNone(resolve_tenant_from_host("acme.app.com"))


@override_settings(BASE_DOMAIN="app.com")
class IsBaseDomainTestCase(TestCase):
    """The base domain is the tenant-less signup context.

    Everything else that fails to resolve is an unknown workspace, which
    is what lets the middleware tell "no tenant here by design" apart
    from "no tenant by that name".
    """

    def test_base_and_www_are_the_base_domain(self):
        self.assertTrue(is_base_domain("app.com"))
        self.assertTrue(is_base_domain("WWW.app.com:3000"))

    def test_subdomain_is_not_the_base_domain(self):
        self.assertFalse(is_base_domain("acme.app.com"))

    def test_foreign_host_is_not_the_base_domain(self):
        self.assertFalse(is_base_domain("example.org"))

    @override_settings(BASE_DOMAIN="")
    def test_every_host_is_the_base_domain_when_unconfigured(self):
        # Single-host deployments — including the test client's
        # "testserver" — have exactly one context, and it is tenant-less.
        self.assertTrue(is_base_domain("testserver"))
        self.assertTrue(is_base_domain("anything.example.org"))
