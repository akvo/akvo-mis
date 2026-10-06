from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from utils.workspace_name import (
    COUNTRY_MESSAGE,
    HOST_RESERVED_MESSAGE,
    RESERVED_MESSAGE,
    _build_country_names,
    _normalize,
    _tokens,
    host_collision_reason,
    self_service_reason,
)


class WordlistAndDependenciesTestCase(SimpleTestCase):
    """The vendored data and the two pins are actually present.

    A separate test from the rules themselves because the usual way
    this fails is a container running a pre-requirements image, which
    surfaces as ModuleNotFoundError in unrelated tests.
    """

    def test_the_vendored_wordlist_is_present_and_attributed(self):
        path = (
            Path(__file__).resolve().parents[4]
            / "utils"
            / "wordlists"
            / "profanity.txt"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("CC BY 4.0", text)
        self.assertIn("commit:", text)
        # One entry from each language file, so a truncated download
        # cannot pass.
        self.assertIn("\nfuck\n", text)
        self.assertIn("\nputain\n", text)

    def test_better_profanity_is_installed(self):
        from better_profanity import Profanity

        instance = Profanity(words=["fuck"])
        self.assertTrue(instance.contains_profanity("fuck"))
        self.assertFalse(instance.contains_profanity("acme"))

    def test_pycountry_is_installed_and_has_iso_names(self):
        import pycountry

        names = {country.name for country in pycountry.countries}
        self.assertIn("Indonesia", names)
        self.assertIn("Senegal", names)


class NormalisationTestCase(SimpleTestCase):
    """One spelling for comparing names, used by every rule."""

    def test_normalize_folds_case_accents_and_punctuation(self):
        self.assertEqual(_normalize("Côte d'Ivoire"), "cotedivoire")
        self.assertEqual(_normalize("south-sudan"), "southsudan")
        self.assertEqual(_normalize("ACME-2"), "acme2")

    def test_tokens_split_on_hyphens_and_digits(self):
        self.assertEqual(_tokens("acme-water"), ["acme", "water"])
        # A digit run separates words even inside one label.
        self.assertEqual(_tokens("acme2water"), ["acme", "water"])
        self.assertEqual(_tokens("acme"), ["acme"])


@override_settings(BASE_DOMAIN="app.com", ADMIN_SUBDOMAIN="admin")
class HostCollisionTestCase(SimpleTestCase):
    """Names that would shadow a host this deployment needs.

    Applies to every path that sets a subdomain, not just sign-up:
    a workspace on the console host would shadow the only address
    from which the deployment can be administered, and one on the
    embed host would share an origin with author-pasted markup and
    could read the non-HttpOnly AUTH_TOKEN cookie.
    """

    def test_the_console_host_is_refused(self):
        self.assertEqual(
            host_collision_reason("admin"), HOST_RESERVED_MESSAGE
        )

    @override_settings(EMBED_HOST="https://embed.app.com")
    def test_the_embed_host_is_refused(self):
        self.assertEqual(
            host_collision_reason("embed"), HOST_RESERVED_MESSAGE
        )

    def test_an_ordinary_name_is_allowed(self):
        self.assertIsNone(host_collision_reason("acme"))


class ReservedTermsTestCase(SimpleTestCase):
    """Names that read as the platform's own infrastructure."""

    def test_platform_hosts_are_refused(self):
        for name in ("admin", "platform", "api", "www", "console"):
            self.assertEqual(
                self_service_reason(name), RESERVED_MESSAGE, name
            )

    def test_domain_control_addresses_are_refused(self):
        """RFC 2142 names a CA will mail to validate domain control.

        A workspace owning one of these hosts is a workspace that can
        potentially be issued a certificate for it, which is why this
        group is in the list at all.
        """
        for name in ("postmaster", "webmaster", "abuse", "security"):
            self.assertEqual(
                self_service_reason(name), RESERVED_MESSAGE, name
            )

    def test_environment_and_brand_names_are_refused(self):
        for name in ("staging", "demo", "akvo", "mis", "default"):
            self.assertEqual(
                self_service_reason(name), RESERVED_MESSAGE, name
            )

    def test_hyphen_spellings_collapse_onto_the_same_term(self):
        # `no-reply` normalises to `noreply`, so the list needs only
        # one spelling of each.
        self.assertEqual(
            self_service_reason("no-reply"), RESERVED_MESSAGE
        )

    def test_a_reserved_term_as_a_prefix_is_allowed(self):
        """Exact match only -- the bare term is what reads as ours."""
        for name in ("akvo-indonesia", "mohhs-mis", "api-kenya"):
            self.assertIsNone(self_service_reason(name), name)

    def test_an_ordinary_name_is_allowed(self):
        self.assertIsNone(self_service_reason("acme"))

    def test_the_public_surface_never_raises(self):
        """Review Focus 5.

        DRF's `required` and `min_length` stop these at the field, so
        these inputs never reach here through the API today. They are
        still the module's public surface.
        """
        self.assertIsNone(self_service_reason(""))
        self.assertIsNone(self_service_reason("a" * 63))


class CountryNamesTestCase(SimpleTestCase):
    """Country names are withheld from sign-up, not forbidden.

    A country name carries an implicit claim to represent that
    country, so it should belong to a programme we set up
    deliberately rather than to whoever typed it into a form first.
    An operator can still grant one with a rename.
    """

    def test_country_names_are_refused(self):
        for name in ("indonesia", "senegal", "south-sudan", "kenya"):
            self.assertEqual(
                self_service_reason(name), COUNTRY_MESSAGE, name
            )

    def test_punctuation_and_accents_do_not_help(self):
        # `Côte d'Ivoire` normalises to the same key as either
        # spelling a registrant could type.
        for name in ("cotedivoire", "cote-divoire"):
            self.assertEqual(
                self_service_reason(name), COUNTRY_MESSAGE, name
            )

    def test_french_country_names_are_refused(self):
        """The form offers French, so the French names count too.

        If this fails on the gettext domain rather than on the
        assertion, confirm the name pycountry 24.6.1 ships with:
          ./dc.sh exec backend python -c \
            "import os, pycountry; print(os.listdir(
              os.path.join(pycountry.LOCALES_DIR, 'fr',
                           'LC_MESSAGES')))"
        """
        for name in ("allemagne", "espagne"):
            self.assertEqual(
                self_service_reason(name), COUNTRY_MESSAGE, name
            )

    def test_colloquial_names_iso_does_not_carry_are_refused(self):
        for name in ("usa", "uk", "swaziland", "holland"):
            self.assertEqual(
                self_service_reason(name), COUNTRY_MESSAGE, name
            )

    def test_a_country_prefix_is_allowed(self):
        """The point of exact matching.

        `indonesia` is a claim on the country. `indonesia-wash-
        monitoring` is an organisation saying where it works, and
        refusing it would block the legitimate majority to stop the
        rare minority.
        """
        for name in (
            "indonesia-wash-monitoring",
            "senegal-rural-water",
            "kenya-moh",
        ):
            self.assertIsNone(self_service_reason(name), name)

    def test_three_letter_iso_codes_are_not_refused(self):
        """Codes are not blocked as a class -- only names are.

        Blocking `can`, `ind` and `cub` would cost more in refused
        legitimate names than it buys.
        """
        for name in ("can", "ind", "cub"):
            self.assertIsNone(self_service_reason(name), name)

    def test_the_set_is_built_once_and_reused(self):
        self.assertIs(_build_country_names(), _build_country_names())

    def test_a_missing_french_catalogue_degrades_to_english(self):
        """Review Focus 3.

        pycountry's gettext domain has been renamed across releases
        and the catalogue is packaging, not code. A packaging change
        must not stop people registering, so the fallback is
        English-only rather than an exception.
        """
        import utils.workspace_name as module

        # The cache is shared with every other test in this process,
        # so clear it on the way in and again on the way out: a
        # degraded, English-only set left cached here would silently
        # change what every sibling test sees.
        module._build_country_names.cache_clear()
        self.addCleanup(module._build_country_names.cache_clear)
        with mock.patch.object(
            module.pycountry, "LOCALES_DIR", "/nonexistent"
        ):
            names = module._build_country_names()
        self.assertIn("indonesia", names)
        self.assertIn("usa", names)
