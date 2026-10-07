"""Rate limits for the public, unauthenticated auth endpoints.

Two throttles per endpoint family, because the two fail in different
directions. A per-IP limit is defeated by any residential proxy pool,
and those are cheap. A per-email limit is what protects the thing
actually worth protecting when mail is involved -- one mailbox from
being flooded, and our sending reputation from being spent -- but it is
keyed on something the caller chooses, so it cannot stand alone either.

These subclass SimpleRateThrottle rather than AnonRateThrottle on
purpose: AnonRateThrottle exempts authenticated callers, and an
authenticated caller hammering forgot-password is exactly as expensive
as an anonymous one.

Rates come from settings.THROTTLE_RATES through DRF's
DEFAULT_THROTTLE_RATES. One trap worth knowing: DRF binds
`SimpleRateThrottle.THROTTLE_RATES` to `api_settings.
DEFAULT_THROTTLE_RATES` in its own class body, at import time, so
`override_settings(REST_FRAMEWORK=...)` does NOT change a rate. Tests
patch the class attribute instead:

    with mock.patch.object(LoginIPThrottle, "rate", "2/hour"):

which works because `__init__` only calls `get_rate()` when `rate` is
falsy.
"""
import hashlib

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle

# Bound once, and shared by every throttle. Both backends this alias
# resolves to -- FileBasedCache in a deployment, LocMemCache under test
# -- are safe to use from more than one thread.
throttle_cache = caches["throttle"]


class _ScopedThrottle(SimpleRateThrottle):
    cache = throttle_cache
    # Declared so that `rate` is a real class attribute. DRF only ever
    # assigns self.rate inside __init__, which leaves nothing for a test
    # to patch; None keeps get_rate() in charge of the actual value.
    rate = None


class _IPKeyedThrottle(_ScopedThrottle):

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class _EmailKeyedThrottle(_ScopedThrottle):
    """Throttle on the email address in the request body.

    The address is read before validation, because throttles run before
    the serializer does. It may therefore be any string the caller
    sent; a nonsense key throttles a nonsense caller, which is fine. A
    request with no usable address returns None -- DRF's "do not
    throttle" -- and is left to the per-IP throttle beside it.

    The address is hashed rather than used raw so that no mailbox
    reaches a cache dump, a traceback, or a cache file name.
    """

    def get_cache_key(self, request, view):
        # A JSON body that is not an object -- a bare list, say --
        # leaves request.data without .get, and an AttributeError here
        # would answer a malformed request with a 500 where a 400
        # belongs. An unparseable body raises ParseError instead, which
        # DRF already turns into that 400, so it is left to propagate.
        data = request.data if isinstance(request.data, dict) else {}
        email = data.get("email")
        if not isinstance(email, str) or not email.strip():
            return None
        digest = hashlib.sha256(
            email.strip().lower().encode("utf-8")
        ).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


class EmailDispatchIPThrottle(_IPKeyedThrottle):
    scope = "email_dispatch_ip"


class EmailDispatchEmailThrottle(_EmailKeyedThrottle):
    scope = "email_dispatch_email"


class LoginIPThrottle(_IPKeyedThrottle):
    scope = "login_ip"


class LoginEmailThrottle(_EmailKeyedThrottle):
    scope = "login_email"
