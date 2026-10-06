"""What a workspace may be called, and why it may not.

Two families of rule live here, and the split between them is the
scope decision made visible.

`host_collision_reason` refuses names that would shadow a host this
deployment needs -- the console and the embed origin. Those are
security properties, not tidiness, so they apply everywhere a
subdomain is set, including the operator console.

`self_service_reason` answers a narrower question: why may a
*self-service registrant* not have this name? Profanity and reserved
system terms are refused on principle; country names and very short
names are merely withheld from sign-up, so an operator can still grant
them with a rename. There is one tier today and no flag for a second,
but the vocabulary is in place for when there is.

Both entry points return the sentence to show the user, or None. They
return rather than raise so the rules can be tested without a
serializer, and so the caller decides the status code and the field
the message attaches to.
"""
import unicodedata

from django.conf import settings

from utils.tenant_host import admin_subdomain, embed_hostname

# Kept as the existing wording, because the console path already
# returns it and its tests assert on it.
HOST_RESERVED_MESSAGE = "This subdomain is reserved."


RESERVED_MESSAGE = (
    "This name is reserved for system use. "
    "Please choose a different one."
)

# Compared against the normalised name, so hyphens need no second
# spelling: `no-reply` arrives here as `noreply`. Exact match only --
# `akvo-indonesia` is a plausible workspace and only the bare term
# reads as ours.
#
# A constant rather than a setting on purpose. Amending it is a
# one-line pull request; an environment variable would be a knob
# nobody turns, configured per deployment where nobody could audit it.
RESERVED_TERMS = frozenset(
    {
        # Hosts and routing.
        "www", "api", "app", "admin", "platform", "console", "portal",
        "auth", "login", "signup", "register", "static", "assets",
        "cdn", "media", "files", "storage", "upload", "uploads",
        "download", "downloads", "graphql", "rest", "v1", "v2", "ws",
        "metrics", "health", "healthz", "ping", "robots", "sitemap",
        "favicon",
        # Mail and domain control. RFC 2142 and the addresses a
        # certificate authority mails to validate domain control --
        # the group with a security rationale rather than a tidiness
        # one.
        "mail", "smtp", "imap", "pop", "pop3", "mx", "email",
        "webmail", "mailer", "noreply", "postmaster", "hostmaster",
        "webmaster", "abuse", "security", "autodiscover",
        "autoconfig", "dkim", "dmarc", "spf",
        # Environments.
        "dev", "development", "test", "testing", "staging", "stage",
        "prod", "production", "demo", "sandbox", "preview", "local",
        "localhost", "beta", "alpha",
        # Product and brand.
        "akvo", "mis", "akvomis", "flow", "akvoflow", "rsr",
        "support", "help", "helpdesk", "docs", "doc",
        "documentation", "status", "blog", "news", "about", "contact",
        "legal", "privacy", "terms", "pricing", "billing", "account",
        "accounts", "settings", "dashboard", "dashboards",
        # Generic and system. `default` earns its place twice over: it
        # is the seeded single-host tenant's subdomain, and a
        # workspace called `default` would be indistinguishable from
        # it in every log line.
        "public", "internal", "system", "root", "superuser",
        "default", "none", "null", "undefined", "new", "create",
        "edit", "delete", "me", "my",
    }
)


def _strip_accents(value):
    """`Côte` -> `Cote`.

    A DNS label cannot carry an accent, so every comparison in this
    module happens on the stripped form -- otherwise the accented
    entries in the vendored French wordlist and in ISO country names
    could never match any subdomain at all.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )


def _normalize(value):
    """The one spelling every rule compares on.

    Lowercase, accent-free, alphanumerics only. `Côte d'Ivoire`,
    `cote-divoire` and `cotedivoire` all collapse onto one key, which
    is what lets a hyphenated name be compared against a list written
    with spaces and punctuation.
    """
    stripped = _strip_accents(value.lower())
    return "".join(char for char in stripped if char.isalnum())


def _tokens(value):
    """The words a reader would see in a subdomain.

    Hyphens separate words and so do digit runs: `acme2fuck` reads as
    two words even though it is a single DNS label, and splitting on
    digits is what stops that spelling walking past a word check.
    """
    tokens = []
    current = ""
    for char in _strip_accents(value.lower()):
        if char.isalpha():
            current += char
        elif current:
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)
    return tokens


def host_collision_reason(value):
    """Would a workspace at this name shadow a host we need?

    Compared as whole hosts rather than as labels, so it stays correct
    whatever EMBED_HOST is set to, and inert when either setting is
    empty -- which is how the test suite and any single-host
    deployment run.
    """
    if value.lower() == admin_subdomain():
        return HOST_RESERVED_MESSAGE
    embed = embed_hostname()
    if embed and settings.BASE_DOMAIN:
        candidate = "{0}.{1}".format(value, settings.BASE_DOMAIN)
        if candidate.lower() == embed:
            return HOST_RESERVED_MESSAGE
    return None


def self_service_reason(value):
    """Why may a self-service registrant not have this name?

    Called from `RegisterSerializer` and nowhere else. The console
    deliberately does not call it -- see the module docstring.
    """
    normalized = _normalize(value)
    if normalized in RESERVED_TERMS:
        return RESERVED_MESSAGE
    return None
