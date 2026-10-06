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
import gettext
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from better_profanity import Profanity
import pycountry

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


COUNTRY_MESSAGE = (
    "Country-level workspaces aren't available on self-service "
    "sign-up. Please contact us to request one, or choose a "
    "different name."
)

# What ISO 3166 does not carry but people type. Deliberately not ISO
# alpha-2 or alpha-3 codes: blocking `can`, `ind` and `cub` as a class
# would cost more in refused legitimate names than it buys, and the
# requirement is about names.
EXTRA_COUNTRY_NAMES = frozenset(
    {
        "usa", "uk", "uae", "drc", "ivorycoast", "burma",
        "swaziland", "holland", "england", "scotland", "wales",
        "northernireland", "turkey",
    }
)


def _french_translator():
    """Country names in French, or identity if unavailable.

    The catalogue is packaging rather than code, and its gettext
    domain has been renamed across pycountry releases -- so a missing
    or differently named one degrades to English instead of taking
    registration down. `pycountry` is pinned, and 24.6.1 ships
    `iso3166-1`.
    """
    try:
        catalogue = gettext.translation(
            "iso3166-1", pycountry.LOCALES_DIR, languages=["fr"]
        )
    except (OSError, AttributeError):
        return lambda value: value
    return catalogue.gettext


# Built on first use rather than at import, so the cost lands on
# the first registration instead of on every management command,
# and cached so it lands once.
@lru_cache(maxsize=1)
def _build_country_names():
    names = set(EXTRA_COUNTRY_NAMES)
    translate = _french_translator()
    for country in pycountry.countries:
        for attribute in ("name", "official_name", "common_name"):
            value = getattr(country, attribute, None)
            if not value:
                continue
            names.add(_normalize(value))
            names.add(_normalize(translate(value)))
    return frozenset(names)


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


PROFANITY_MESSAGE = (
    "This name isn't available. Please choose a different one."
)

# Words the vendored list carries that a real workspace could
# plausibly be named after. Every entry needs its reason, because an
# entry without one is an entry nobody can audit later.
DOMAIN_SAFE_WORDS = frozenset(
    {
        "fecal",       # faecal sludge management; the `unicef-fsm`
                       # tenant is named after it
        "sex",         # sexual and reproductive health
        "sexual",      # ditto
        "sexuality",   # ditto
        "sexually",    # ditto
        "rape",        # oilseed rape, a crop -- and GBV programming
        "smut",        # a cereal plant disease
        "shrimping",   # aquaculture and fisheries
        "mong",        # the Mong (Hmong) people
        "negro",       # Rio Negro; Negros Occidental
        "bite",        # dog-bite and snakebite surveillance
        "con",         # three letters, too ambiguous to be a signal
        "peter",       # a common name, and only here because our own
                       # accent-stripping turns `péter` into it
    }
)

# Substring-scanned, to catch the run-together spellings the token
# check cannot see. Curated to be collision-free *by construction*,
# which is why it is short and hand-written rather than taken from the
# file: `ass` (assam), `cum` (cumbria), `tit` (titicaca) and `cunt`
# (scunthorpe, penistone) are all excluded and left to the token
# check, and so is `merde`, which is a substring of `merdeka` --
# Indonesian for independence, and a very common place name where
# this software runs.
HARD_BLOCKED = (
    "fuck",
    "shit",
    "bitch",
    "bastard",
    "wanker",
    "nigger",
    "nigga",
    "faggot",
    "motherfuck",
    "arsehole",
    "asshole",
    "dickhead",
    "bollocks",
    "pedophile",
    "paedophile",
    "putain",
    "salope",
    "connard",
    "encule",
)

_WORDLIST_PATH = (
    Path(__file__).resolve().parent / "wordlists" / "profanity.txt"
)


def _load_profanity_words():
    """The vendored list, normalised and whitelisted.

    `encoding` is explicit and ours rather than inherited from the
    container locale: the file has accented French in it, and a
    default-ASCII locale would make this a UnicodeDecodeError at
    import.

    Accents are stripped because a DNS label cannot carry one, so
    `pédé` would otherwise be inert -- and the whitelist is applied to
    the stripped form, which is the only way `peter` can cancel the
    file's `péter`.
    """
    words = set()
    with _WORDLIST_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            entry = _strip_accents(line.strip().lower())
            if not entry or entry.startswith("#"):
                continue
            if entry in DOMAIN_SAFE_WORDS:
                continue
            words.add(entry)
    return sorted(words)


# A private instance, and the words passed at construction. The
# module-level `profanity` singleton would be shared state, and
# `Profanity()` with no arguments -- or with an empty list, which the
# library reads as "use the default" -- eagerly loads the bundled
# 827-word list this design exists to avoid.
_PROFANITY = Profanity(words=_load_profanity_words())


def _profanity_reason(value):
    normalized = _normalize(value)
    for term in HARD_BLOCKED:
        if term in normalized:
            return PROFANITY_MESSAGE
    for token in _tokens(value):
        if _PROFANITY.contains_profanity(token):
            return PROFANITY_MESSAGE
    return None


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
    # Reserved before country so that a name which is both gets the
    # infrastructure message; country before profanity so that a
    # country name near the profanity wordlist gets the polite
    # "contact us" message rather than a profanity accusation.
    if normalized in _build_country_names():
        return COUNTRY_MESSAGE
    return _profanity_reason(value)
