from pathlib import Path

from django.test import SimpleTestCase


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
