from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import (
    TENANT_PASSWORD,
    TenantTestHelperMixin,
)
from api.v1.v1_users.models import SystemUser, Tenant

LOGIN = "/api/v1/login"
TENANT_INFO = "/api/v1/tenant-info"


@override_settings(BASE_DOMAIN="app.com")
class LoginHostTestCase(TestCase, TenantTestHelperMixin):
    """Signing in happens at your own workspace's address.

    The middleware cannot do this one: a login request carries no token
    yet, so there is no session for it to compare against the host.
    """

    def setUp(self):
        self.acme = self.create_tenant(
            "acme", ["Country", "Province"], "Kenya"
        )
        self.beta = self.create_tenant("beta", ["Country", "Region"], "Uganda")
        self.credentials = {
            "email": self.acme.admin.email,
            "password": TENANT_PASSWORD,
        }

    def test_own_workspace_signs_in(self):
        response = self.client.post(
            LOGIN, self.credentials, HTTP_HOST="acme.app.com"
        )
        self.assertEqual(response.status_code, 200)

    def test_other_workspace_is_refused(self):
        response = self.client.post(
            LOGIN, self.credentials, HTTP_HOST="beta.app.com"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("workspace", response.json()["message"])

    def test_base_domain_does_not_sign_in(self):
        # The main site signs people up; it has no workspace to sign in
        # to. Refused before the password is even looked at.
        response = self.client.post(
            LOGIN, self.credentials, HTTP_HOST="app.com"
        )
        self.assertEqual(response.status_code, 400)

    def test_tenant_less_account_is_refused_on_a_workspace(self):
        operator = SystemUser.objects.create_superuser(
            email="operator@akvo.org",
            password=TENANT_PASSWORD,
            first_name="Op",
            last_name="Erator",
        )
        response = self.client.post(
            LOGIN,
            {"email": operator.email, "password": TENANT_PASSWORD},
            HTTP_HOST="acme.app.com",
        )
        self.assertEqual(response.status_code, 401)

    def test_unverified_account_is_told_to_verify_on_its_own_workspace(self):
        user = SystemUser.objects.create_superuser(
            email="new@acme.org",
            password=TENANT_PASSWORD,
            first_name="",
            last_name="",
            tenant=self.acme.tenant,
            is_active=False,
        )
        response = self.client.post(
            LOGIN,
            {"email": user.email, "password": TENANT_PASSWORD},
            HTTP_HOST="acme.app.com",
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()["unverified"])

    def test_unverified_account_says_nothing_on_another_workspace(self):
        # The "resend your activation email" branch is an account
        # existence oracle by design, but only for the workspace the
        # account belongs to. Elsewhere it must stay shut.
        SystemUser.objects.create_superuser(
            email="new@acme.org",
            password=TENANT_PASSWORD,
            first_name="",
            last_name="",
            tenant=self.acme.tenant,
            is_active=False,
        )
        response = self.client.post(
            LOGIN,
            {"email": "new@acme.org", "password": TENANT_PASSWORD},
            HTTP_HOST="beta.app.com",
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("unverified", response.json())


class SingleHostLoginTestCase(TestCase, TenantTestHelperMixin):
    def test_login_is_unchanged_without_a_base_domain(self):
        acme = self.create_tenant("acme", ["Country", "Province"], "Kenya")
        response = self.client.post(
            LOGIN, {"email": acme.admin.email, "password": TENANT_PASSWORD}
        )
        self.assertEqual(response.status_code, 200)


class ProfileSubdomainTestCase(TestCase, TenantTestHelperMixin):
    """The profile says which address the session belongs to.

    The frontend compares it against the host it is served on; without
    it, a user on the wrong workspace has nowhere to be redirected to.
    """

    def test_profile_carries_the_users_own_workspace(self):
        acme = self.create_tenant("acme", ["Country", "Province"], "Kenya")
        response = self.client.get(
            "/api/v1/profile", **self.bearer(acme.admin)
        )
        self.assertEqual(response.json()["subdomain"], "acme")

    def test_tenant_less_account_has_no_workspace(self):
        operator = SystemUser.objects.create_superuser(
            email="operator@akvo.org",
            password=TENANT_PASSWORD,
            first_name="Op",
            last_name="Erator",
        )
        response = self.client.get("/api/v1/profile", **self.bearer(operator))
        self.assertEqual(response.json()["subdomain"], "")


@override_settings(BASE_DOMAIN="app.com")
class TenantInfoTestCase(TestCase, TenantTestHelperMixin):
    """What a visitor may know about a workspace before signing in."""

    def setUp(self):
        self.acme = self.create_tenant(
            "acme", ["Country", "Province"], "Kenya"
        )

    def test_workspace_host_names_its_workspace(self):
        response = self.client.get(TENANT_INFO, HTTP_HOST="acme.app.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"subdomain": "acme"})

    def test_nothing_beyond_that_one_field_is_exposed(self):
        # Anonymous and cacheable, so the field list is the whole of the
        # security review — assert it exhaustively rather than by sample.
        # The workspace's name used to be here too, for a login-page
        # caption that no longer exists.
        response = self.client.get(TENANT_INFO, HTTP_HOST="acme.app.com")
        self.assertEqual(set(response.json().keys()), {"subdomain"})

    def test_base_domain_returns_nothing(self):
        response = self.client.get(TENANT_INFO, HTTP_HOST="app.com")
        self.assertEqual(response.status_code, 204)

    def test_a_workspace_answers_before_it_is_configured(self):
        # No hierarchy exists between activation and the configure form,
        # and the answer must not depend on one: the frontend needs to
        # know this host is a workspace in order to show its login page.
        Tenant.objects.create(subdomain="fresh")
        response = self.client.get(TENANT_INFO, HTTP_HOST="fresh.app.com")
        self.assertEqual(response.json(), {"subdomain": "fresh"})
