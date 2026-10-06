import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from utils.workspace_name import (
    COUNTRY_MESSAGE,
    DOMAIN_SAFE_WORDS,
    HOST_RESERVED_MESSAGE,
    PROFANITY_MESSAGE,
    RESERVED_MESSAGE,
    _build_country_names,
    _load_profanity_words,
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
        """The names ISO spells differently, or not at all.

        `russia` and `palestine` are the two carrying the clearest
        claim to represent a country, which is the reason this rule
        exists -- and both were claimable, because ISO says `Russian
        Federation` and `Palestine, State of`.
        """
        for name in (
            "usa", "uk", "swaziland", "holland", "turkey",
            "russia", "palestine", "bosnia", "macedonia",
            "capeverde", "brunei", "easttimor", "vatican",
            "drcongo", "saudi",
            # `coteivoire` with one `r`, as often typed as the `d'`
            # spelling ISO carries.
            "coteivoire",
            "britain", "greatbritain",
        ):
            self.assertEqual(
                self_service_reason(name), COUNTRY_MESSAGE, name
            )

    def test_the_french_twin_of_every_extra_is_refused(self):
        """The asymmetry the extras set had.

        The ISO side is bilingual through the gettext catalogue, but
        a hand-written English extras list leaves every entry with a
        claimable French twin. `hollande` was claimable while
        `holland` was not.
        """
        for name in (
            "russie", "bosnie", "macedoine", "grandebretagne",
            "angleterre", "ecosse", "paysdegalles", "irlandedunord",
            "hollande",
        ):
            self.assertEqual(
                self_service_reason(name), COUNTRY_MESSAGE, name
            )

    def test_the_short_form_of_a_qualified_iso_name_is_refused(self):
        """What the comma and the parenthetical used to hide.

        ISO qualifies a good many names -- `Korea, Republic of`,
        `Micronesia, Federated States of`, `Falkland Islands
        (Malvinas)`, `Holy See (Vatican City State)` -- and the
        qualifier normalises *into* the key rather than off it. So the
        long form nobody types was in the set and the short form
        everybody types was not. Derived in `_build_country_names`
        rather than hand-listed, which is why this test names one of
        each shape instead of all 26.
        """
        for name in (
            "korea", "coree", "micronesia", "falklandislands",
            "virginislands", "holysee",
        ):
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


class ProfanityTestCase(SimpleTestCase):
    """Refused for the words it contains, by two mechanisms."""

    def test_a_profane_token_is_refused(self):
        self.assertEqual(
            self_service_reason("fuck-acme"), PROFANITY_MESSAGE
        )

    def test_a_run_together_spelling_is_refused(self):
        """What the token check alone cannot see."""
        self.assertEqual(
            self_service_reason("fuckacme"), PROFANITY_MESSAGE
        )

    def test_a_digit_separated_spelling_is_refused(self):
        # `_tokens` splits on digit runs for exactly this.
        self.assertEqual(
            self_service_reason("acme2fuck"), PROFANITY_MESSAGE
        )

    def test_a_leetspeak_variant_is_refused(self):
        """Generated by the library, not enumerated by us.

        `v` is the substitute better_profanity's own character map
        offers for `u`.
        """
        self.assertEqual(
            self_service_reason("fvck-acme"), PROFANITY_MESSAGE
        )

    def test_a_digit_substituted_spelling_is_refused(self):
        """The library's variants, finally reaching the library.

        better_profanity generates `1` for `i` and `l`, so it answers
        True for `sh1t`, `b1tch` and `n1gga` on its own -- but
        `_tokens` splits on digit runs, so it handed over ['sh', 't']
        and the variant mechanism never saw a word. A racial slur was
        claimable with the machinery that catches it installed and
        switched off by our own tokeniser.

        `n1ggadata` and `sh1tco` are the run-together case, which no
        whole-token check can see: those are caught by folding the
        digits onto the letters they stand in for and scanning
        HARD_BLOCKED over the result.
        """
        for name in (
            "sh1t-acme",
            "b1tch-data",
            "n1gga-data",
            "n1ggadata",
            "sh1tco",
        ):
            self.assertEqual(
                self_service_reason(name), PROFANITY_MESSAGE, name
            )

    def test_the_hyphen_split_evasion_is_a_deliberate_loss(self):
        """Stated as a test because it is a decision, not a gap.

        Matching per token means no hyphen invents a word boundary,
        and giving that up is what stops `wash-items` being refused.
        The trade: `fu-ck-acme` is claimable, which costs one
        subdomain an operator renames, against false positives that
        refuse real customers silently.
        """
        self.assertIsNone(self_service_reason("fu-ck-acme"))

    def test_french_profanity_is_refused(self):
        self.assertEqual(
            self_service_reason("putain-mis"), PROFANITY_MESSAGE
        )
        self.assertEqual(
            self_service_reason("salopemis"), PROFANITY_MESSAGE
        )

    def test_accented_french_entries_match_their_stripped_form(self):
        """Review Focus 1, second half.

        The file's `pédé` can never match a DNS label as written, so
        the loader strips accents. Without that, every accented French
        entry is inert.
        """
        self.assertEqual(
            self_service_reason("pede-data"), PROFANITY_MESSAGE
        )

    def test_the_loader_reads_utf8_and_strips_accents(self):
        """Review Focus 1, first half.

        The file has accented French in it. Reading it without an
        explicit encoding inherits the container locale, and a
        default-ASCII locale would raise UnicodeDecodeError at import
        -- taking registration down on first request rather than in
        CI.
        """
        words = _load_profanity_words()
        self.assertIn("putain", words)
        # Accents are gone, so no accented entry is unmatchable by a
        # DNS label. The one non-ASCII survivor is the file's emoji
        # entry, which has no accent to strip and can never match a
        # single-token subdomain either way, so it is left as is.
        non_ascii = {word for word in words if not word.isascii()}
        self.assertEqual(non_ascii, {"\U0001f595"})
        # `encule` is only here if `enculé` was stripped on load.
        self.assertIn("encule", words)
        # The whitelist is applied to the stripped form, which is the
        # only way `peter` can cancel the file's `péter`.
        self.assertNotIn("peter", words)
        for safe in DOMAIN_SAFE_WORDS:
            self.assertNotIn(safe, words)

    def test_an_empty_wordlist_raises_rather_than_degrading(self):
        """Review Focus 2.

        `Profanity(words=[])` is not "no words" to better_profanity --
        its `custom_words or read_wordlist(default)` treats a falsy
        `[]` the same as `None` and silently loads the library's own
        827-word bundled list instead, which refuses `hiv` and `gay`
        as whole tokens. That is the exact failure this design exists
        to avoid, so a wordlist that reads but yields no words (every
        line a comment or blank, the realistic way this happens) must
        raise rather than let `_PROFANITY` fall back to it quietly.
        """
        import utils.workspace_name as module

        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_wordlist = Path(tmp_dir) / "empty.txt"
            empty_wordlist.write_text(
                "# nothing but comments and blank lines\n\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                module, "_WORDLIST_PATH", empty_wordlist
            ):
                with self.assertRaises(RuntimeError):
                    module._load_profanity_words()


class ProfanityFalsePositiveTestCase(SimpleTestCase):
    """The test that matters most in this change.

    Every name here is one a real customer of a public-health or WASH
    information system could choose, and several are refused outright
    by better_profanity's bundled wordlist. This is the guard on the
    whole approach: refresh the vendored file, widen HARD_BLOCKED, or
    bump the library past a change in its variant generation, and this
    fails and somebody reads the diff.

    A false positive here is invisible in production -- the registrant
    picks a worse name or leaves and we never hear about it. A false
    negative is one bad subdomain an operator can see and rename.
    """

    def test_public_health_and_wash_names_are_accepted(self):
        for name in (
            "hiv-kenya",
            "sexual-health-senegal",
            "menstrual-hygiene-mis",
            "urine-diversion-sanitation",
            "fecal-sludge-management",
            "breastfeeding-monitoring",
            "dog-bite-surveillance",
        ):
            self.assertIsNone(self_service_reason(name), name)

    def test_hyphen_boundaries_do_not_invent_words(self):
        """The worst false-positive class this branch had.

        HARD_BLOCKED was scanned against the hyphen-free spelling, so
        every hyphen became a word boundary the list had never been
        audited against. `wash` + `items` spelled `shit` on a WASH
        platform; `disposal` + `operations` and `handwashing` +
        `habit` spelled `salope` and `bitch`; `relawan` + `kerja`,
        everyday Indonesian for volunteer work, spelled `wanker` --
        the same failure class the design congratulates itself on
        catching with `merdeka`, except the lesson had been applied to
        the list's contents and not to the boundaries the scan
        invented.
        """
        for name in (
            "wash-items",
            "fish-items",
            "sludge-disposal-open-defecation",
            "handwashing-habit-change",
            "habit-change",
            "disposal-operations",
            "proposal-operations",
            "faecal-disposal-operations",
            "relawan-kerja",
            "karyawan-kerja",
        ):
            self.assertIsNone(self_service_reason(name), name)

    def test_digits_in_a_name_are_not_read_as_leetspeak(self):
        """The bound on the digit fold.

        Folding `0134578` onto letters is what catches `n1ggadata`,
        and a target year or an SDG number is the ordinary reason a
        workspace name carries a digit. The fold is fed to
        HARD_BLOCKED only, because that list is collision-free within
        a token; the vendored thousand-word list is not.
        """
        for name in (
            "water4all",
            "wash2030",
            "sdg6-monitoring",
            "acme2water",
            "level3-data",
        ):
            self.assertIsNone(self_service_reason(name), name)

    def test_place_names_are_accepted(self):
        """Checked against where this software runs, not just English.

        `merdeka` is Indonesian for independence and one of the most
        common place names in Indonesia; it contains `merde`, which is
        why `merde` is not in HARD_BLOCKED.
        """
        for name in (
            "merdeka-health",
            "rio-negro-wash",
            "mong-health-laos",
            "assam",
            "cumbria",
            "scunthorpe",
            "titicaca",
        ):
            self.assertIsNone(self_service_reason(name), name)

    def test_agriculture_and_fisheries_names_are_accepted(self):
        for name in ("smut-surveillance", "shrimping-survey"):
            self.assertIsNone(self_service_reason(name), name)

    def test_a_whitelisted_word_is_a_registerable_name(self):
        """Review Focus 4 -- deliberate, and worth seeing.

        Allowing `sexual-health-kenya` necessarily allows the bare
        `sex`, and stripping accents to catch `pédé` necessarily
        allows `peter`. Both are accepted trades; a change to either
        should be a decision, not a surprise.
        """
        self.assertIsNone(self_service_reason("peter-foundation"))
        self.assertIsNone(self_service_reason("sex"))
        self.assertIsNone(self_service_reason("peter"))


class RuleOrderTestCase(SimpleTestCase):
    """Which message a name that breaks two rules gets.

    The order is about the message, not the verdict -- the name is
    refused either way. It matters because several real country and
    place names sit near the profanity wordlist, and telling a
    national programme that its country's name is obscene is a worse
    failure than any it prevents.

    Both cases are constructed by patching, because no name in the
    real lists currently breaks two rules at once. That is luck, not
    design, and the precedence should hold when it stops being true.
    """

    def test_reserved_beats_country(self):
        import utils.workspace_name as module

        with mock.patch.object(
            module, "RESERVED_TERMS", frozenset({"kenya"})
        ):
            self.assertEqual(
                self_service_reason("kenya"), RESERVED_MESSAGE
            )

    def test_country_beats_profanity(self):
        import utils.workspace_name as module

        with mock.patch.object(module, "HARD_BLOCKED", ("kenya",)):
            self.assertEqual(
                self_service_reason("kenya"), COUNTRY_MESSAGE
            )
