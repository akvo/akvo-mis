from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin

PROFILE = "/api/v1/profile"


@override_settings(BASE_DOMAIN="app.com", ALLOW_TENANT_HEADER=True)
class TenantMiddlewareTestCase(TestCase, TenantTestHelperMixin):
    """The host decides which workspace a request is for, and a session
    is only valid on its own workspace's host."""

    def setUp(self):
        self.acme = self.create_tenant(
            "acme", ["Country", "Province"], "Kenya"
        )
        self.beta = self.create_tenant("beta", ["Country", "Region"], "Uganda")

    def test_host_attaches_the_tenant_to_the_request(self):
        response = self.client.get(PROFILE, HTTP_HOST="acme.app.com")
        self.assertEqual(response.wsgi_request.tenant, self.acme.tenant)

    def test_base_domain_has_no_tenant(self):
        response = self.client.get(PROFILE, HTTP_HOST="app.com")
        self.assertIsNone(response.wsgi_request.tenant)

    def test_unknown_subdomain_is_404(self):
        response = self.client.get(PROFILE, HTTP_HOST="nope.app.com")
        self.assertEqual(response.status_code, 404)

    def test_foreign_host_is_404(self):
        # Not the base domain and not a workspace. Nothing here is for it.
        response = self.client.get(PROFILE, HTTP_HOST="example.org")
        self.assertEqual(response.status_code, 404)

    def test_own_subdomain_passes(self):
        response = self.client.get(
            PROFILE, HTTP_HOST="acme.app.com", **self.bearer(self.acme.admin)
        )
        self.assertEqual(response.status_code, 200)

    def test_other_tenants_subdomain_is_403(self):
        response = self.client.get(
            PROFILE, HTTP_HOST="beta.app.com", **self.bearer(self.acme.admin)
        )
        self.assertEqual(response.status_code, 403)

    def test_base_domain_is_not_enforced(self):
        # The signup context belongs to no tenant, so there is nothing to
        # mismatch against — a session reaching it is not a violation.
        response = self.client.get(
            PROFILE, HTTP_HOST="app.com", **self.bearer(self.acme.admin)
        )
        self.assertEqual(response.status_code, 200)

    def test_anonymous_request_on_a_tenant_host_is_not_403(self):
        # Enforcement compares an account against a host; with no account
        # there is nothing to compare, so the view answers as it always
        # did. Every public endpoint stays reachable for free.
        response = self.client.get(PROFILE, HTTP_HOST="acme.app.com")
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_left_to_the_view(self):
        response = self.client.get(
            PROFILE,
            HTTP_HOST="acme.app.com",
            HTTP_AUTHORIZATION="Bearer not-a-token",
        )
        self.assertEqual(response.status_code, 401)

    def test_header_stands_in_for_the_host(self):
        # The test client cannot vary /etc/hosts, so the override is the
        # only way a test reaches a subdomain without one.
        response = self.client.get(
            PROFILE, HTTP_X_TENANT_SUBDOMAIN="acme"
        )
        self.assertEqual(response.wsgi_request.tenant, self.acme.tenant)

    def test_unknown_header_subdomain_is_404(self):
        response = self.client.get(PROFILE, HTTP_X_TENANT_SUBDOMAIN="nope")
        self.assertEqual(response.status_code, 404)

    @override_settings(ALLOW_TENANT_HEADER=False)
    def test_header_is_ignored_when_not_allowed(self):
        # Production must not let a request header choose its workspace.
        response = self.client.get(
            PROFILE, HTTP_HOST="app.com", HTTP_X_TENANT_SUBDOMAIN="acme"
        )
        self.assertIsNone(response.wsgi_request.tenant)


class SingleHostTestCase(TestCase, TenantTestHelperMixin):
    """With BASE_DOMAIN unset the middleware must do nothing at all.

    This is the state the whole existing suite runs in — host
    `testserver`, users with and without tenants — and it is what makes
    the iteration safe to merge before any DNS exists.
    """

    def setUp(self):
        self.acme = self.create_tenant(
            "acme", ["Country", "Province"], "Kenya"
        )

    def test_testserver_is_never_404(self):
        response = self.client.get(PROFILE)
        self.assertEqual(response.status_code, 401)

    def test_no_tenant_is_attached(self):
        response = self.client.get(PROFILE)
        self.assertIsNone(response.wsgi_request.tenant)

    def test_authenticated_request_is_not_enforced(self):
        response = self.client.get(PROFILE, **self.bearer(self.acme.admin))
        self.assertEqual(response.status_code, 200)
