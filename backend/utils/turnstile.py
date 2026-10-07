"""Verify a Cloudflare Turnstile token at sign-up.

Turnstile rather than reCAPTCHA: no Google account coupling, no
consent-banner question for a platform NGOs put their name on, free at
this scale, and the same verify-the-token-server-side shape.

Inert unless TURNSTILE_SECRET is set. See that setting for why
enabling is two steps and why their order matters.
"""
import requests
from django.conf import settings
from sentry_sdk import capture_exception

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# Short, and explicit. Without a timeout this call would hang on the
# single backend pod, inside a request that is already holding a
# synchronous SMTP connection.
TIMEOUT_SECONDS = 5


def turnstile_failure_reason(token, remote_ip=None):
    """A message to refuse the registration with, or None to allow it.

    Returns None in three cases: the check is off, the token verifies,
    and Cloudflare could not be reached.

    That third one is deliberate. Pre-launch, with no observed abuse,
    an outage at Cloudflare closing the sign-up form entirely is the
    worse outcome, so this fails open and reports itself. It is a
    judgement about today rather than a principle, and inverting it is
    the one `return None` below -- which is written out rather than
    folded into the try block so that the decision is visible to
    whoever revisits it.
    """
    if not settings.TURNSTILE_SECRET:
        return None
    if not token:
        # No outbound call: a missing token is a client-side fact, and
        # during the config.js cache window it is the expected one.
        return "Please complete the verification challenge."
    payload = {
        "secret": settings.TURNSTILE_SECRET,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        response = requests.post(
            VERIFY_URL, data=payload, timeout=TIMEOUT_SECONDS
        )
        verdict = response.json()
    except Exception:
        # Broad on purpose: a verification outage must not become a 500
        # on the sign-up form, and the failure modes here include
        # timeouts, DNS, TLS and a non-JSON body. Captured rather than
        # swallowed -- `send_email` is what swallowing silently looks
        # like a year later.
        capture_exception()
        return None
    if verdict.get("success"):
        return None
    return "Verification failed. Please try again."
