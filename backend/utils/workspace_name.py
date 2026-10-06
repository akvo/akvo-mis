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
import re
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
    return re.findall(r"[a-z]+", _strip_accents(value.lower()))


COUNTRY_MESSAGE = (
    "Country-level workspaces aren't available on self-service "
    "sign-up. Please contact us to request one, or choose a "
    "different name."
)

# What ISO 3166 does not carry *in any form a derivation can reach*,
# but people type. Deliberately not ISO alpha-2 or alpha-3 codes:
# blocking `can`, `ind` and `cub` as a class would cost more in refused
# legitimate names than it buys, and the requirement is about names.
#
# Entries are listed with their French twin, because the ISO side of
# the set is bilingual through the gettext catalogue and a one-language
# extras list leaves every entry with a claimable twin. Two French
# twins are deliberately absent: `eau` for the UAE is French for
# *water*, which on a WASH platform is the worst false positive this
# module could invent, and `arabie` for Saudi Arabia is a region
# rather than a country.
EXTRA_COUNTRY_NAMES = frozenset(
    {
        # Abbreviations and colloquial English names.
        "usa", "uk", "uae", "drc", "drcongo", "rdc", "ivorycoast",
        "burma", "swaziland", "turkey", "saudi",
        # Names the standard spells differently enough that
        # normalisation cannot bridge the gap: ISO has `Russian
        # Federation`, `Cabo Verde`, `Brunei Darussalam`, `Bosnia and
        # Herzegovina`, `North Macedonia`, `Timor-Leste` and `Holy See
        # (Vatican City State)`. `russia` and `palestine` are the two
        # that carry the clearest claim to represent a country, which
        # is the reason this rule exists at all.
        "russia", "capeverde", "brunei", "bosnia", "macedonia",
        "easttimor", "vatican", "vaticancity",
        # `coteivoire` with one `r`, which is how the name is as often
        # typed as the `d'` spelling ISO carries.
        "coteivoire",
        # The United Kingdom's constituent countries and the island,
        # none of which ISO 3166-1 carries, plus the French forms the
        # catalogue cannot supply because the English entries are ours.
        "england", "scotland", "wales", "northernireland",
        "britain", "greatbritain",
        "angleterre", "ecosse", "paysdegalles", "irlandedunord",
        "grandebretagne",
        # French twins of the entries above.
        "hollande", "holland", "bosnie", "macedoine",
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
    """Every spelling of every country, normalised, in two languages.

    ISO qualifies a good many names with a comma or a parenthetical --
    `Korea, Republic of`, `Palestine, State of`, `Micronesia,
    Federated States of`, `Falkland Islands (Malvinas)`, `Holy See
    (Vatican City State)` -- and those qualifiers normalise into the
    key rather than off it, so the short form a person actually types
    was absent from the set while the long form nobody types was in
    it. Taking the part before the first comma and the form with the
    parenthetical removed is what closes that gap for 26 names at
    once, which is why it is derived here rather than hand-listed in
    `EXTRA_COUNTRY_NAMES`: a hand-written entry per country is a list
    that drifts out of step with the next pycountry bump.
    """
    names = set(EXTRA_COUNTRY_NAMES)
    translate = _french_translator()
    for country in pycountry.countries:
        for attribute in ("name", "official_name", "common_name"):
            value = getattr(country, attribute, None)
            if not value:
                continue
            for spelling in (value, translate(value)):
                names.add(_normalize(spelling))
                names.add(_normalize(spelling.split(",")[0]))
                names.add(
                    _normalize(re.sub(r"\(.*?\)", " ", spelling))
                )
    # `_normalize("")` is the empty string, and an empty candidate
    # must not match anything -- `self_service_reason("")` is part of
    # the public surface and has a test.
    names.discard("")
    return frozenset(names)


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
    # An empty result is caught here, not at the `_PROFANITY`
    # construction site, because `Profanity(words=[])` fails silently:
    # the library's `custom_words or read_wordlist(default)` treats a
    # falsy `[]` the same as `None` and loads its own 827-word bundled
    # list instead -- the exact failure this design exists to avoid,
    # and with no exception or log line to notice it by.
    if not words:
        raise RuntimeError(
            "No profanity words loaded from {0}. An empty list "
            "would make better_profanity silently fall back to its "
            "bundled wordlist, which refuses `hiv`, `menstruation` "
            "and `urine` as whole tokens.".format(_WORDLIST_PATH)
        )
    return sorted(words)


# A private instance, and the words passed at construction. The
# module-level `profanity` singleton would be shared state, and
# `Profanity()` with no arguments -- or with an empty list, which the
# library reads as "use the default" -- eagerly loads the bundled
# 827-word list this design exists to avoid.
_PROFANITY = Profanity(words=_load_profanity_words())


# What a digit stands in for when it is standing in for a letter.
# Applied to the HARD_BLOCKED scan only -- see `_profanity_reason`.
_LEET_FOLD = str.maketrans("0134578", "oieasst")


def _profanity_reason(value):
    """Why this name reads as profane, or None.

    Both halves of the match run **per token**, and that is the whole
    point of this function. Scanning `HARD_BLOCKED` against
    `_normalize(value)` -- the hyphen-free spelling -- turned every
    hyphen into a word boundary the list was never audited against,
    and the result was `wash-items` refused on a WASH platform
    (`wash` + `items` -> `shit`), along with
    `sludge-disposal-open-defecation` and `disposal-operations`
    (-> `salope`), `handwashing-habit-change` (-> `bitch`) and
    `relawan-kerja`, everyday Indonesian for volunteer work
    (-> `wanker`). Those are the names this product's customers
    actually have.

    Three forms of each token are compared, because the two
    tokenisers fail in opposite directions:

    1. `_tokens(value)` splits on every non-letter, which is what
       catches `acme2fuck`, and keeps working for the other callers
       and tests that rely on it.
    2. A punctuation-only split *preserves digits*, so the library
       sees `sh1t` as one token and can match it against the
       spelling variants it generates. `_tokens` shredded exactly
       those: `sh1t-acme` became ['sh', 't', 'acme'] and `n1gga-data`
       became ['n', 'gga', 'data'], so a racial slur was claimable
       with the mechanism that catches it installed and switched off
       by our own tokeniser.
    3. The same token with digits folded onto the letters they stand
       in for, which is what catches the run-together `n1ggadata`
       that neither of the first two forms can see. The fold is fed
       to the `HARD_BLOCKED` scan **only**: that list is
       collision-free within a token, which bounds the false
       positives the fold can invent, while the vendored thousand-word
       list is not, so folding into it would be reckless. `water4all`
       and `sdg6-monitoring` are the test that this stayed bounded.

    Two trades are deliberate and worth stating, because both are
    invisible from the code:

    - **The hyphen-split evasion is given up.** `fu-ck-acme` was
      refused before this change and is claimable after it, because
      no token of it is profane. That is the price of not inventing
      word boundaries, and it is the right price: a false positive
      refuses a real customer *silently* -- they pick a worse name or
      leave, and we never hear about it -- while a false negative is
      one subdomain an operator renames from the console.
    - **The leet fold has a ceiling.** A run-together leet spelling
      whose base word is not in `HARD_BLOCKED` still gets through,
      because the library half is whole-token and the fold does not
      reach it. Widening the fold to the full wordlist is not the
      upgrade path; adding the word to `HARD_BLOCKED` is, and only
      if it is collision-free there.
    """
    stripped = _strip_accents(value.lower())
    tokens = _tokens(value) + [
        token for token in re.split(r"[^a-z0-9]+", stripped) if token
    ]
    for token in tokens:
        for term in HARD_BLOCKED:
            if term in token or term in token.translate(_LEET_FOLD):
                return PROFANITY_MESSAGE
        # The library sees only the unfolded token, so `sh1t` is
        # answered by its own variant generation, not our fold.
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
