from pathlib import Path

from django.test import SimpleTestCase, override_settings

from utils.workspace_name import (
    HOST_RESERVED_MESSAGE,
    RESERVED_MESSAGE,
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
