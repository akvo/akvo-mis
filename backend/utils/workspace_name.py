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
