from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin

PROFILE = "/api/v1/profile"


@override_settings(BASE_DOMAIN="app.com")
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

    def test_the_403_names_the_right_workspace(self):
        # Without this the frontend knows only that it is in the wrong
        # place, not where the right one is — the profile call that
        # would have told it is the very call being refused.
        response = self.client.get(
            PROFILE, HTTP_HOST="beta.app.com", **self.bearer(self.acme.admin)
        )
        self.assertEqual(response.json()["subdomain"], "acme")

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


@override_settings(BASE_DOMAIN="app.com")
class HealthCheckHostTestCase(TestCase, TenantTestHelperMixin):
    """Infrastructure reaches the pod directly, with no workspace host.

    A kubelet probe connects to the pod IP, so the request arrives with
    `Host: <pod-ip>:8000` — neither the base domain nor a workspace. The
    404 that is right for a typo'd subdomain is wrong here: it fails the
    readiness probe, which holds the rollout, so enabling BASE_DOMAIN
    would make every deploy time out.
    """

    HEALTH = "/api/v1/health/check"

    def setUp(self):
        self.acme = self.create_tenant(
            "acme", ["Country", "Province"], "Kenya"
        )

    def test_a_pod_ip_host_can_reach_the_health_check(self):
        response = self.client.get(self.HEALTH, HTTP_HOST="10.4.2.15:8000")
        self.assertEqual(response.status_code, 200)

    def test_a_cluster_dns_host_can_reach_the_health_check(self):
        # Service-to-service inside the cluster, and `kubectl
        # port-forward` during an incident, look the same way.
        response = self.client.get(
            self.HEALTH, HTTP_HOST="backend-service.akvo-mis-namespace.svc"
        )
        self.assertEqual(response.status_code, 200)

    def test_the_base_domain_still_reaches_the_health_check(self):
        response = self.client.get(self.HEALTH, HTTP_HOST="app.com")
        self.assertEqual(response.status_code, 200)

    def test_a_workspace_host_still_reaches_the_health_check(self):
        response = self.client.get(self.HEALTH, HTTP_HOST="acme.app.com")
        self.assertEqual(response.status_code, 200)

    def test_the_exemption_does_not_leak_to_other_paths(self):
        # Only liveness is exempt. An unrecognised host reaching anything
        # else is still nothing this deployment serves.
        response = self.client.get(PROFILE, HTTP_HOST="10.4.2.15:8000")
        self.assertEqual(response.status_code, 404)


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
