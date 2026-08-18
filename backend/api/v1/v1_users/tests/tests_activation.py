from unittest import mock

from django.core import signing
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False)
class ActivationTestCase(TestCase):
    """The activation link proves the address, nothing more.

    The password was already set at sign-up, so activation only flips
    `is_active` — and hands back a session, because the very next thing
    the registrant must do is fill in the configuration form.
    """

    payload = {
        "email": "founder@acme.org",
        "password": "Secret#Pass123",
        "subdomain": "acme",
    }

    def setUp(self):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.client.post(
                "/api/v1/register", self.payload,
                content_type="application/json",
            )
        self.user = SystemUser.objects.get(email=self.payload["email"])

    def activate(self, token):
        return self.client.post(
            "/api/v1/register/activate", {"token": token},
            content_type="application/json",
        )

    def test_valid_token_activates_and_returns_a_session(self):
        res = self.activate(signing.dumps(self.user.pk))
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        body = res.json()
        # A full session, matching login and the old register: the token,
        # its expiry for the SPA's guard, and configured=false so the
        # frontend knows to route to the configuration form.
        self.assertIn("token", body)
        self.assertIn("expiration_time", body)
        self.assertFalse(body["configured"])

    def test_the_returned_token_works(self):
        token = self.activate(signing.dumps(self.user.pk)).json()["token"]
        res = self.client.get(
            "/api/v1/profile", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(res.status_code, 200)

    def test_login_works_after_activation(self):
        self.activate(signing.dumps(self.user.pk))
        res = self.client.post(
            "/api/v1/login",
            {"email": self.payload["email"],
             "password": self.payload["password"]},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)

    def test_garbage_token_is_rejected(self):
        res = self.activate("not-a-real-token")
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_token_is_rejected(self):
        # Signed the normal way but read back with the age limit exceeded.
        token = signing.dumps(self.user.pk)
        with mock.patch(
            "api.v1.v1_users.views.signing.loads",
            side_effect=signing.SignatureExpired("too old"),
        ):
            res = self.activate(token)
        self.assertEqual(res.status_code, 400)

    def test_missing_token_is_rejected(self):
        res = self.client.post(
            "/api/v1/register/activate", {}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)

    def test_activating_twice_is_a_no_op_success(self):
        token = signing.dumps(self.user.pk)
        self.assertEqual(self.activate(token).status_code, 200)
        self.assertEqual(self.activate(token).status_code, 200)

    def test_resend_sends_again_for_an_inactive_account(self):
        with mock.patch("api.v1.v1_users.views.send_email") as send:
            res = self.client.post(
                "/api/v1/register/resend-activation",
                {"email": self.payload["email"]},
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(send.call_count, 1)

    def test_resend_is_a_silent_success_for_an_unknown_address(self):
        # Always 200 and never a send, so the endpoint cannot be used to
        # enumerate which addresses are registered.
        with mock.patch("api.v1.v1_users.views.send_email") as send:
            res = self.client.post(
                "/api/v1/register/resend-activation",
                {"email": "nobody@example.org"},
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 200)
        send.assert_not_called()

    def test_resend_does_nothing_for_an_already_active_account(self):
        self.activate(signing.dumps(self.user.pk))
        with mock.patch("api.v1.v1_users.views.send_email") as send:
            res = self.client.post(
                "/api/v1/register/resend-activation",
                {"email": self.payload["email"]},
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 200)
        send.assert_not_called()
