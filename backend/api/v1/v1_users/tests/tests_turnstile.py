from unittest import mock

from django.test import TestCase
from django.test.utils import override_settings

from utils.turnstile import turnstile_failure_reason


@override_settings(USE_TZ=False, SIGNUP_ENABLED=True)
class TurnstileVerificationTestCase(TestCase):
    """The captcha, and the fact that it ships switched off.

    `TURNSTILE_SECRET` empty is the shipped state: the site key goes
    out first so clients start sending tokens as nginx's day-long cache
    of config.js turns over, and the secret follows once they do.
    """

    payload = {
        "email": "founder@acme.org",
        "password": "Secret#Pass123",
        "subdomain": "acme",
    }

    def register(self, **overrides):
        return self.client.post(
            "/api/v1/register",
            {**self.payload, **overrides},
            content_type="application/json",
        )

    @override_settings(TURNSTILE_SECRET="")
    def test_disabled_makes_no_outbound_call(self):
        """Off means off -- no network in the sign-up path at all."""
        with mock.patch("utils.turnstile.requests.post") as post:
            response = self.register()
        self.assertEqual(response.status_code, 200)
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_enabled_and_verified_registers(self):
        with mock.patch("utils.turnstile.requests.post") as post:
            post.return_value.json.return_value = {"success": True}
            response = self.register(captcha_token="a-token")
        self.assertEqual(response.status_code, 200)

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_enabled_and_rejected_is_a_400_on_the_field(self):
        with mock.patch("utils.turnstile.requests.post") as post:
            post.return_value.json.return_value = {"success": False}
            response = self.register(captcha_token="a-token")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["details"]["captcha_token"],
            ["Verification failed. Please try again."],
        )

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_enabled_with_no_token_is_a_400_on_the_field(self):
        """The stale-config.js window, which is up to a day wide.

        A browser holding a cached config.js from before the site key
        was set sends no token. That must be a 400 the form can show on
        the widget, not a 500 from posting None to Cloudflare.
        """
        with mock.patch("utils.turnstile.requests.post") as post:
            response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["details"]["captcha_token"],
            ["Please complete the verification challenge."],
        )
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_verification_outage_fails_open_and_reports(self):
        """A Cloudflare outage must not close the sign-up form.

        Pre-launch that is the worse failure, so this fails open and
        captures. Inverting it is one `return None` -- and a decision
        somebody should make on purpose, which is why the capture is
        asserted here rather than left implicit.
        """
        with mock.patch(
            "utils.turnstile.requests.post",
            side_effect=OSError("unreachable"),
        ):
            with mock.patch(
                "utils.turnstile.capture_exception"
            ) as capture:
                response = self.register(captcha_token="a-token")
        self.assertEqual(response.status_code, 200)
        capture.assert_called_once()

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_the_client_address_is_sent_for_verification(self):
        with mock.patch("utils.turnstile.requests.post") as post:
            post.return_value.json.return_value = {"success": True}
            self.register(captcha_token="a-token")
        self.assertEqual(
            post.call_args.kwargs["data"]["remoteip"], "127.0.0.1"
        )

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_an_oversize_token_is_refused_before_the_outbound_call(self):
        """Otherwise the fail-open path is an attacker's off switch.

        Unbounded, a caller can send a token large enough that
        Cloudflare answers with something that is not JSON. `.json()`
        raises, the broad except fires, and the registration proceeds
        with the captcha bypassed -- repeatably, and looking like an
        outage in Sentry. A length bound makes it a 400 on the field
        before anything is sent.
        """
        with mock.patch("utils.turnstile.requests.post") as post:
            response = self.register(captcha_token="x" * 500000)
        self.assertEqual(response.status_code, 400)
        self.assertIn("captcha_token", response.json()["details"])
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET="a-secret")
    def test_the_helper_needs_no_request(self):
        """Callable outside a view, so the rule is testable alone."""
        with mock.patch("utils.turnstile.requests.post") as post:
            post.return_value.json.return_value = {"success": True}
            self.assertIsNone(turnstile_failure_reason("a-token"))
