from unittest import mock

from django.core.cache import caches
from django.test import TestCase
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.v1.v1_users.models import SystemUser, Tenant
from utils.throttling import (
    EmailDispatchEmailThrottle,
    EmailDispatchIPThrottle,
    LoginEmailThrottle,
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

    def test_two_client_addresses_get_different_keys(self):
        """The assertion the prefix tests cannot make.

        Both NUM_PROXIES tests above compare two keys for equality, so
        a get_cache_key that returned a constant would satisfy them
        both -- and a constant key is exactly what a misconfigured
        NUM_PROXIES produces in a deployment, where every caller
        collapses onto the proxy's own address. This is the test that
        fails for that.
        """
        with self.settings(REST_FRAMEWORK={"NUM_PROXIES": 2}):
            one = self.key_for(
                EmailDispatchIPThrottle,
                HTTP_X_FORWARDED_FOR="203.0.113.7, 35.191.0.1",
            )
            two = self.key_for(
                EmailDispatchIPThrottle,
                HTTP_X_FORWARDED_FOR="198.51.100.4, 35.191.0.1",
            )
        self.assertNotEqual(one, two)

    def test_a_short_header_under_two_proxies_follows_the_client(self):
        """Why the default is 0 and not the deployed 2.

        DRF clamps its index with min(NUM_PROXIES, len(addrs)), so with
        NUM_PROXIES=2 and a one-entry header -- which is what arrives
        anywhere there is no GCLB in front -- the key is taken from the
        entry the *client* sent. Two callers varying that header get
        two budgets. This pins the hazard that justifies the default;
        if it ever stops holding, the comment on NUM_PROXIES is stale.
        """
        with self.settings(REST_FRAMEWORK={"NUM_PROXIES": 2}):
            spoofed_one = self.key_for(
                EmailDispatchIPThrottle, HTTP_X_FORWARDED_FOR="1.1.1.1"
            )
            spoofed_two = self.key_for(
                EmailDispatchIPThrottle, HTTP_X_FORWARDED_FOR="2.2.2.2"
            )
        self.assertNotEqual(spoofed_one, spoofed_two)

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

    def test_a_counter_survives_many_other_keys(self):
        """A throttle cache has a capacity, and the default is 300.

        Django's cache backends cull on every set() once MAX_ENTRIES is
        reached, deleting num_entries/CULL_FREQUENCY entries at random.
        With the defaults that is 100 random counters discarded per
        write past 300 keys -- so in a deployment, where one key exists
        per client address and per submitted email across four
        endpoints, no counter would live long enough to reach its
        budget and the throttles would quietly stop working under
        exactly the load they exist for.
        """
        victim = drf_request(
            self.factory, "/api/v1/register", {"email": "victim@acme.org"}
        )
        with mock.patch.object(
            EmailDispatchEmailThrottle, "rate", "1/hour"
        ):
            self.assertTrue(
                EmailDispatchEmailThrottle().allow_request(victim, None)
            )
            # Well past the 300-entry default.
            for n in range(400):
                other = drf_request(
                    self.factory,
                    "/api/v1/register",
                    {"email": "filler{0}@acme.org".format(n)},
                )
                EmailDispatchEmailThrottle().allow_request(other, None)
            self.assertFalse(
                EmailDispatchEmailThrottle().allow_request(victim, None)
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


class ThrottledEndpointTestCase(TestCase):
    """That the limits are actually wired to the endpoints.

    One endpoint per family is enough to prove the wiring; the key and
    rate logic is covered above. What these catch is a decorator that
    was never added, or added in the wrong order.
    """

    def setUp(self):
        caches["throttle"].clear()

    def register(self, email="founder@acme.org", subdomain="acme"):
        return self.client.post(
            "/api/v1/register",
            {
                "email": email,
                "password": "Secret#Pass123",
                "subdomain": subdomain,
            },
            content_type="application/json",
        )

    def test_register_refuses_past_the_per_email_limit(self):
        with mock.patch.object(
            EmailDispatchEmailThrottle, "rate", "2/hour"
        ):
            self.register(subdomain="acme")
            self.register(subdomain="acmetwo")
            response = self.register(subdomain="acmethree")
        self.assertEqual(response.status_code, 429)

    def test_register_refuses_past_the_per_ip_limit(self):
        """A different address each time, so only the IP key is spent."""
        with mock.patch.object(EmailDispatchIPThrottle, "rate", "2/hour"):
            self.register(email="a@acme.org", subdomain="acmea")
            self.register(email="b@acme.org", subdomain="acmeb")
            response = self.register(
                email="c@acme.org", subdomain="acmec"
            )
        self.assertEqual(response.status_code, 429)

    def test_every_mail_endpoint_refuses_past_the_per_email_limit(self):
        """One body, several endpoints, one shared budget.

        `register` has its own case above because its payload is
        bigger; these take the same body and differ only in URL.
        """
        endpoints = (
            "/api/v1/user/forgot-password",
            "/api/v1/register/resend-activation",
            # AllowAny, calls send_email with caller-supplied content:
            # the same relay exposure as the other two.
            "/api/v1/feedback",
        )
        for url in endpoints:
            with self.subTest(url=url):
                caches["throttle"].clear()
                body = {"email": "nobody@acme.org"}
                with mock.patch.object(
                    EmailDispatchEmailThrottle, "rate", "1/hour"
                ):
                    self.client.post(
                        url, body, content_type="application/json"
                    )
                    response = self.client.post(
                        url, body, content_type="application/json"
                    )
                self.assertEqual(response.status_code, 429)

    def test_login_refuses_past_the_per_email_limit(self):
        with mock.patch.object(LoginEmailThrottle, "rate", "2/hour"):
            for _ in range(2):
                self.client.post(
                    "/api/v1/login",
                    {"email": "nobody@acme.org", "password": "wrong"},
                    content_type="application/json",
                )
            response = self.client.post(
                "/api/v1/login",
                {"email": "nobody@acme.org", "password": "wrong"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 429)

    def test_a_successful_login_clears_the_per_email_counter(self):
        """So a user's own typos cannot accumulate into a lockout.

        Any per-email login limit can be spent by anyone who knows the
        address, which is the reason the rate is generous. Clearing on
        success removes the commoner case: somebody who mistypes their
        password a few times, gets in, and would otherwise carry those
        attempts for the rest of the hour.
        """
        tenant = Tenant.objects.create(subdomain="loginclear")
        SystemUser.objects.create_superuser(
            email="member@acme.org",
            password="Secret#Pass123",
            first_name="M",
            last_name="X",
            tenant=tenant,
        )
        with mock.patch.object(LoginEmailThrottle, "rate", "3/hour"):
            for _ in range(2):
                self.client.post(
                    "/api/v1/login",
                    {"email": "member@acme.org", "password": "wrong"},
                    content_type="application/json",
                )
            good = self.client.post(
                "/api/v1/login",
                {"email": "member@acme.org", "password": "Secret#Pass123"},
                content_type="application/json",
            )
            self.assertEqual(good.status_code, 200)
            # The budget was 3 and three requests have been made. Without
            # the reset the next one is refused.
            again = self.client.post(
                "/api/v1/login",
                {"email": "member@acme.org", "password": "wrong"},
                content_type="application/json",
            )
        self.assertNotEqual(again.status_code, 429)

    def test_unparseable_body_is_a_400_not_a_500(self):
        """ParseError must reach DRF's handler, not die in a throttle.

        The email throttle touches request.data, which is where the
        parse happens. Catching it there would turn a malformed body
        into a silent success; letting it propagate gives the 400 it
        deserves.
        """
        with mock.patch.object(
            EmailDispatchEmailThrottle, "rate", "5/hour"
        ):
            response = self.client.post(
                "/api/v1/register",
                "{not json",
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)
