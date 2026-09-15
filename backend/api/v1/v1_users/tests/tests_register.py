from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class RegisterEndpointTestCase(TestCase):
    """Phase 1: claim the subdomain, prove nothing else yet.

    Registration deliberately creates no hierarchy and hands back no auth
    token. The names and the hierarchy belong to the configuration form,
    and the account cannot be used until the activation link is followed.
    """

    payload = {
        "email": "founder@acme.org",
        "password": "Secret#Pass123",
        "subdomain": "acme",
    }

    def register(self, host=None, **overrides):
        payload = {**self.payload, **overrides}
        # Registration lives on the base domain. Only the tests that set
        # BASE_DOMAIN need to say so — the rest run single-host, where
        # every host is the base domain.
        extra = {"HTTP_HOST": host} if host else {}
        return self.client.post(
            "/api/v1/register", payload,
            content_type="application/json", **extra
        )

    def registered_tenants(self):
        # The backfill data migration seeds a "default" tenant, so it is
        # present in every test database. These tests care only about the
        # tenants registration itself creates.
        return Tenant.objects.exclude(subdomain="default")

    def test_register_creates_an_inactive_superadmin_and_no_token(self):
        with mock.patch("api.v1.v1_users.views.send_email"):
            response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("token", response.json())
        user = SystemUser.objects.get(email="founder@acme.org")
        self.assertFalse(user.is_active)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.tenant.subdomain, "acme")
        # The hierarchy is phase 2's job, so the root is never a
        # placeholder named after the subdomain.
        self.assertFalse(Levels.objects.filter(tenant=user.tenant).exists())
        self.assertFalse(
            Administration.objects.filter(tenant=user.tenant).exists()
        )

    def test_register_sends_an_activation_link(self):
        with mock.patch("api.v1.v1_users.views.send_email") as send:
            self.register()
        self.assertEqual(send.call_count, 1)
        context = send.call_args.kwargs["context"]
        self.assertEqual(context["send_to"], ["founder@acme.org"])
        self.assertIn("/activate/", context["button_url"])

    @override_settings(BASE_DOMAIN="app.com", WEBDOMAIN="https://app.com")
    def test_the_activation_link_lands_on_the_new_workspace(self):
        # Registration happens on the main site, but activation hands
        # back a session — and that session is only valid on the
        # workspace's own host, so the link has to go there.
        with mock.patch("api.v1.v1_users.views.send_email") as send:
            self.register(host="app.com")
        url = send.call_args.kwargs["context"]["button_url"]
        self.assertTrue(url.startswith("https://acme.app.com/activate/"), url)

    def test_unverified_registrant_cannot_log_in(self):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.register()
        res = self.client.post(
            "/api/v1/login",
            {"email": self.payload["email"],
             "password": self.payload["password"]},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)
        # Distinguishable from a wrong password, so the login page can
        # offer to resend the activation email.
        self.assertIn("verify", res.json()["message"].lower())

    def test_wrong_password_does_not_mention_verification(self):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.register()
        res = self.client.post(
            "/api/v1/login",
            {"email": self.payload["email"], "password": "Wrong#Pass123"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)
        self.assertNotIn("verify", res.json()["message"].lower())

    def test_duplicate_subdomain_is_rejected_atomically(self):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.register()
            response = self.register(email="owner@beta.org")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"], "Subdomain is already registered"
        )
        self.assertFalse(
            SystemUser.objects.filter(email="owner@beta.org").exists()
        )

    def test_duplicate_email_is_rejected(self):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.register()
            response = self.register(subdomain="beta")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"], "Email is already registered"
        )
        self.assertEqual(self.registered_tenants().count(), 1)

    def test_losing_a_uniqueness_race_is_a_400(self):
        # Two simultaneous sign-ups can both pass the serializer's
        # existence checks; the loser hits the unique constraint at
        # insert. Stand in for that with a raising create.
        with mock.patch(
            "api.v1.v1_users.views.Tenant.objects.create",
            side_effect=IntegrityError("duplicate key"),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_malformed_subdomain_is_rejected(self):
        for bad in ("My App", "UPPER", "-lead", "trail-", "a_b"):
            response = self.register(subdomain=bad)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.registered_tenants().count(), 0)

    def test_weak_password_is_rejected(self):
        response = self.register(password="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.registered_tenants().count(), 0)

    def test_no_email_is_sent_when_registration_fails(self):
        with mock.patch("api.v1.v1_users.views.send_email") as send:
            self.register(password="12345678")
        send.assert_not_called()

    def test_tenantless_superuser_falls_back_to_unscoped_root(self):
        # Legacy path: seeders and createsuperuser make superusers with
        # no tenant; they must keep resolving a root administration.
        from django.core.management import call_command

        call_command("administration_seeder", "--test")
        user = SystemUser.objects.create_superuser(
            email="legacy-admin@example.org",
            password="Secret#Pass123",
            first_name="Legacy",
            last_name="Admin",
        )
        token = str(RefreshToken.for_user(user).access_token)
        profile = self.client.get(
            "/api/v1/profile",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(profile.status_code, 200)
        self.assertIsNotNone(profile.json()["administration"]["id"])
