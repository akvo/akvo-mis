from unittest import mock

from django.core.cache import caches
from django.test import TestCase
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from utils.throttling import (
    EmailDispatchEmailThrottle,
    EmailDispatchIPThrottle,
)


def drf_request(factory, path, data=None, **extra):
    """A request shaped the way DRF hands one to a throttle.

    APIRequestFactory returns a plain WSGIRequest, which has no
    `.data`. DRF wraps it in its own Request before check_throttles
    runs, so an unwrapped request here would test a shape production
    never sees.
    """
    return Request(
        factory.post(path, data, **extra),
        parsers=[JSONParser(), FormParser(), MultiPartParser()],
    )


class ThrottleKeyTestCase(TestCase):
    """How the throttles identify a caller.

    These are unit tests against the throttle classes rather than
    endpoint tests, because the question here is only "what is the
    key", and a wrong key is invisible from a 200.
    """

    def setUp(self):
        caches["throttle"].clear()
        self.factory = APIRequestFactory()

    def key_for(self, throttle_class, **extra):
        request = drf_request(self.factory, "/api/v1/register", {}, **extra)
        return throttle_class().get_cache_key(request, None)

    def test_zero_proxies_ignores_the_forwarded_header(self):
        """With NUM_PROXIES=0, REMOTE_ADDR decides and nothing else.

        This is the configuration local development, the test suite and
        every single-host deployment run with -- `env.example` ships 0.
        If the header counted here, a bot would get a fresh throttle
        bucket per request by varying one header.

        Set explicitly rather than relied on as the settings default,
        so that a developer with NUM_PROXIES in their own .env does not
        see this fail for an unrelated reason.
        """
        with self.settings(REST_FRAMEWORK={"NUM_PROXIES": 0}):
            spoofed = self.key_for(
                EmailDispatchIPThrottle,
                HTTP_X_FORWARDED_FOR="9.9.9.9",
                REMOTE_ADDR="127.0.0.1",
            )
            plain = self.key_for(
                EmailDispatchIPThrottle, REMOTE_ADDR="127.0.0.1"
            )
        self.assertEqual(spoofed, plain)

    def test_client_prefix_cannot_move_the_key_behind_the_gclb(self):
        """With NUM_PROXIES=2, the client is second from the right.

        The GCLB preserves whatever the caller sent and appends
        "<client-ip>, <GFE-ip>", so the leftmost entries are
        attacker-controlled and only the right-hand end is trustworthy.
        Two calls from one client must share a key however much junk
        the caller prepends.
        """
        with self.settings(REST_FRAMEWORK={"NUM_PROXIES": 2}):
            honest = self.key_for(
                EmailDispatchIPThrottle,
                HTTP_X_FORWARDED_FOR="203.0.113.7, 35.191.0.1",
            )
            prefixed = self.key_for(
                EmailDispatchIPThrottle,
                HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7, 35.191.0.1",
            )
        self.assertEqual(honest, prefixed)

    def test_email_key_is_case_and_whitespace_insensitive(self):
        request = drf_request(
            self.factory,
            "/api/v1/register", {"email": "  Founder@Acme.ORG "}
        )
        other = drf_request(
            self.factory,
            "/api/v1/register", {"email": "founder@acme.org"}
        )
        throttle = EmailDispatchEmailThrottle()
        self.assertEqual(
            throttle.get_cache_key(request, None),
            throttle.get_cache_key(other, None),
        )

    def test_email_key_does_not_contain_the_address(self):
        """The address is hashed, so no mailbox reaches a cache dump."""
        request = drf_request(
            self.factory,
            "/api/v1/register", {"email": "founder@acme.org"}
        )
        key = EmailDispatchEmailThrottle().get_cache_key(request, None)
        self.assertNotIn("founder", key)
        self.assertNotIn("acme.org", key)

    def test_no_email_is_not_throttled_by_the_email_throttle(self):
        """None means "do not throttle" to DRF.

        The per-IP throttle beside it still applies, so a body with no
        address is not unlimited -- it is just not attributable to a
        mailbox.
        """
        request = drf_request(self.factory, "/api/v1/register", {})
        self.assertIsNone(
            EmailDispatchEmailThrottle().get_cache_key(request, None)
        )

    def test_non_object_body_is_not_throttled_by_the_email_throttle(self):
        """A bare JSON list leaves request.data without .get.

        Unguarded this is an AttributeError inside the throttle, which
        surfaces as a 500 on a malformed request that deserves a 400.
        """
        request = drf_request(
            self.factory,
            "/api/v1/register", [1, 2], format="json"
        )
        self.assertIsNone(
            EmailDispatchEmailThrottle().get_cache_key(request, None)
        )


class ThrottleRateTestCase(TestCase):
    """That a rate, once set, is actually enforced on the key."""

    def setUp(self):
        caches["throttle"].clear()
        self.factory = APIRequestFactory()

    def test_the_fourth_request_is_refused_at_three_per_hour(self):
        request = drf_request(
            self.factory,
            "/api/v1/register",
            {"email": "founder@acme.org"},
            REMOTE_ADDR="127.0.0.1",
        )
        with mock.patch.object(
            EmailDispatchEmailThrottle, "rate", "3/hour"
        ):
            allowed = [
                EmailDispatchEmailThrottle().allow_request(request, None)
                for _ in range(4)
            ]
        self.assertEqual(allowed, [True, True, True, False])

    def test_a_different_address_has_its_own_budget(self):
        first = drf_request(
            self.factory,
            "/api/v1/register", {"email": "a@acme.org"}
        )
        second = drf_request(
            self.factory,
            "/api/v1/register", {"email": "b@acme.org"}
        )
        with mock.patch.object(
            EmailDispatchEmailThrottle, "rate", "1/hour"
        ):
            EmailDispatchEmailThrottle().allow_request(first, None)
            self.assertFalse(
                EmailDispatchEmailThrottle().allow_request(first, None)
            )
            self.assertTrue(
                EmailDispatchEmailThrottle().allow_request(second, None)
            )

    def test_rates_are_inert_under_the_test_suite_by_default(self):
        """Without an explicit patch, nothing throttles.

        This is what keeps the rest of the suite green. If this test
        fails, every endpoint test that calls one endpoint more than ten
        times is about to start failing too, by shuffle order.
        """
        request = drf_request(
            self.factory,
            "/api/v1/register", {"email": "founder@acme.org"}
        )
        allowed = [
            EmailDispatchEmailThrottle().allow_request(request, None)
            for _ in range(20)
        ]
        self.assertTrue(all(allowed))
