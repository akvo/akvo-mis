"""The form a fresh install starts from, and the drop-box it sits in.

`source/forms/` is an operator drop-box. A plain run seeds every
*.prod.json in it (SEED-004 D-7), so a 0-byte or half-saved definition is
a question of when, not if. The empty `example.prod.json` that started
this raised a bare JSONDecodeError naming neither the file nor the folder,
and it slipped past both of the filters that existed then -- `--test`
kept names containing "example", the PROD gate kept names containing
"prod", and it matched both.

The seeded form itself must work on a database with nothing else in it.
`seeder.sh` has no entities step, so an `entity` cascade would render a
required question with no options.
"""
import json
import os
import shutil
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormTypes, FormStatus
from api.v1.v1_forms.functions import (
    normalize_form_definition,
    validate_form_definition,
)
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.models import Entity

INITIAL_FORM_ID = 1789516800000
FORMS_DIR = "./source/forms"
INITIAL_FORM_FILE = os.path.join(
    FORMS_DIR, f"{INITIAL_FORM_ID}.prod.json"
)


def read_initial_form():
    with open(INITIAL_FORM_FILE, "r") as handle:
        return json.load(handle)


def declared_counts(raw):
    """(groups, questions) the committed file declares.

    Derived rather than written out. These forms exist to be edited --
    that is the whole point of shipping one -- and a hardcoded count
    turns an intended edit into a failing test that says nothing about
    whether the edit was correct. `tests_form_seeder.py` learned the
    same lesson twice.
    """
    groups = raw["question_groups"]
    return len(groups), sum(len(g["questions"]) for g in groups)


@override_settings(USE_TZ=False, TEST_ENV=True)
class InitialFormDefinitionTest(TestCase):
    """Assertions about the committed file, no database needed."""

    def setUp(self):
        self.raw = read_initial_form()
        self.norm = normalize_form_definition(self.raw)

    def test_filename_matches_the_id_inside(self):
        """job.sh and `form_seeder -f` both parse the id off the filename.

        `example.prod.json` yielded form_id "example", which is not a form
        id, and `generate_excel_data example` is what the export cron
        would have run.
        """
        stem = os.path.basename(INITIAL_FORM_FILE).replace(".prod.json", "")
        self.assertEqual(int(stem), self.raw["id"])

    def test_definition_passes_the_shared_parser_and_validator(self):
        validate_form_definition(self.norm)

    def test_is_a_published_registration_form_with_no_parent(self):
        self.assertEqual(self.norm["type"], FormTypes.registration)
        self.assertIsNone(self.norm.get("parent_hint"))

    def test_carries_no_entity_question(self):
        """The constraint the whole form selection rests on.

        Asserted rather than left to code review: an entity cascade needs
        an Entity type that a fresh install has no step to create.
        """
        extras = [
            (q.get("extra") or {}).get("type")
            for g in self.norm["question_group"]
            for q in g["question"]
        ]
        self.assertNotIn("entity", extras)
        self.assertIn("administration", extras)

    def test_ids_are_above_the_autoincrement_sequences(self):
        """form/question_group/question sequences count up from 1.

        A low explicit id is one the sequence eventually reaches. These
        are derived from the form id for that reason.
        """
        self.assertGreater(self.raw["id"], 10**12)
        for group in self.raw["question_groups"]:
            self.assertGreater(group["id"], 10**12)
            for question in group["questions"]:
                self.assertGreater(question["id"], 10**12)

    def test_question_ids_are_unique(self):
        ids = [
            q["id"]
            for g in self.raw["question_groups"]
            for q in g["questions"]
        ]
        self.assertEqual(len(ids), len(set(ids)))


@override_settings(USE_TZ=False, TEST_ENV=True)
class InitialFormSeedTest(TestCase):
    def test_seeds_into_an_empty_database(self):
        call_command("form_seeder", "--file", str(INITIAL_FORM_ID))

        form = Forms.objects.get(pk=INITIAL_FORM_ID)
        self.assertEqual(form.type, FormTypes.registration)
        self.assertEqual(form.status, FormStatus.published)
        groups, questions = declared_counts(read_initial_form())
        self.assertEqual(
            QuestionGroup.objects.filter(form=form).count(), groups
        )
        self.assertEqual(
            Questions.objects.filter(form=form).count(), questions
        )
        # The end the entity-free constraint is a means to: seeder.sh has
        # no entities step, so the form must need no Entity type to be
        # usable. Nothing created one, and nothing has to.
        self.assertEqual(Entity.objects.count(), 0)

    def test_meta_questions_exist_for_datapoint_naming(self):
        call_command("form_seeder", "--file", str(INITIAL_FORM_ID))

        names = set(
            Questions.objects.filter(
                form_id=INITIAL_FORM_ID, meta=True
            ).values_list("name", flat=True)
        )
        self.assertEqual(names, {"administration", "name", "geolocation"})

    def test_reseeding_is_idempotent(self):
        call_command("form_seeder", "--file", str(INITIAL_FORM_ID))
        call_command("form_seeder", "--file", str(INITIAL_FORM_ID))

        self.assertEqual(
            Forms.objects_with_deleted.filter(pk=INITIAL_FORM_ID).count(), 1
        )
        self.assertEqual(
            Questions.objects.filter(form_id=INITIAL_FORM_ID).count(), 9
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormSeederBadSourceTest(TestCase):
    """--source points at a temp copy; never mutate the shared fixtures."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        shutil.copy(INITIAL_FORM_FILE, self.directory)

    def write(self, name, content):
        path = os.path.join(self.directory, name)
        with open(path, "w") as handle:
            handle.write(content)
        return path

    def test_empty_file_names_itself(self):
        self.write("broken.prod.json", "")

        with self.assertRaises(CommandError) as ctx:
            call_command("form_seeder", "--source", self.directory)

        self.assertIn("broken.prod.json", str(ctx.exception))
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_truncated_file_names_itself(self):
        self.write("half.prod.json", '{"id": 1, "form": "Half"')

        with self.assertRaises(CommandError) as ctx:
            call_command("form_seeder", "--source", self.directory)

        self.assertIn("half.prod.json", str(ctx.exception))

    def test_non_prod_json_is_not_seeded(self):
        """A stray .json beside the definitions is ignored, not parsed.

        The empty example.prod.json that started this would have been
        skipped outright had it not carried the suffix.
        """
        self.write("scratch.json", "")

        call_command("form_seeder", "--source", self.directory)

        self.assertTrue(Forms.objects.filter(pk=INITIAL_FORM_ID).exists())

    def test_a_clean_folder_still_seeds(self):
        call_command("form_seeder", "--source", self.directory)

        self.assertTrue(Forms.objects.filter(pk=INITIAL_FORM_ID).exists())


MONITORING_FORM_ID = 1789516900000
MONITORING_FORM_FILE = os.path.join(
    FORMS_DIR, f"{MONITORING_FORM_ID}.monitoring.prod.json"
)


def read_monitoring_form():
    with open(MONITORING_FORM_FILE, "r") as handle:
        return json.load(handle)


@override_settings(USE_TZ=False, TEST_ENV=True)
class InitialMonitoringFormDefinitionTest(TestCase):
    def setUp(self):
        self.raw = read_monitoring_form()
        self.norm = normalize_form_definition(self.raw)

    def test_definition_passes_the_shared_parser_and_validator(self):
        validate_form_definition(self.norm)

    def test_is_a_monitoring_form_hanging_off_the_registration_form(self):
        self.assertEqual(self.norm["type"], FormTypes.monitoring)
        self.assertEqual(
            self.norm["parent_hint"]["id"], INITIAL_FORM_ID
        )

    def test_carries_no_entity_question(self):
        extras = [
            (q.get("extra") or {}).get("type")
            for g in self.norm["question_group"]
            for q in g["question"]
        ]
        self.assertNotIn("entity", extras)

    def test_ids_are_unique_and_above_the_sequences(self):
        ids = [self.raw["id"]]
        for group in self.raw["question_groups"]:
            ids.append(group["id"])
            for question in group["questions"]:
                ids.append(question["id"])
                ids += [o["id"] for o in question.get("options") or []]
        self.assertEqual(len(ids), len(set(ids)))
        for value in ids:
            self.assertGreater(value, 10**12)

    def test_ids_do_not_overlap_the_registration_form(self):
        """Both id blocks are derived from their own form id."""
        def block(raw):
            out = {raw["id"]}
            for group in raw["question_groups"]:
                out.add(group["id"])
                for question in group["questions"]:
                    out.add(question["id"])
                    out |= {o["id"] for o in question.get("options") or []}
            return out

        self.assertEqual(
            block(self.raw) & block(read_initial_form()), set()
        )

    def test_supplies_a_question_for_every_dashboard_widget(self):
        """The reason this form exists.

        A dashboard must be buildable from seeded data alone. The
        inspector only offers number/option/multiple_option/date
        (v1_visualization.constants.SUPPORTED_QUESTION_TYPES), and each
        widget needs a particular shape: a date for the line chart's
        axis, two numbers for a scatter's X and Y, an option set for
        bar/pie/map-category, and a second option set to stack by.
        """
        by_type = {}
        for group in self.norm["question_group"]:
            for question in group["question"]:
                by_type.setdefault(question["type"], []).append(
                    question["name"]
                )

        self.assertGreaterEqual(len(by_type.get("date", [])), 1)
        self.assertGreaterEqual(len(by_type.get("number", [])), 2)
        self.assertGreaterEqual(len(by_type.get("option", [])), 2)
        self.assertGreaterEqual(len(by_type.get("multiple_option", [])), 1)

    def test_repeat_aggregations_need_a_repeatable_group_to_demonstrate(self):
        """KPI `repeat_agg` is the one widget option this form cannot show.

        average/sum/max/min/last aggregate a question's *indexed*
        answers, which only a repeatable group produces. This form has
        none, so those five options have nothing to act on in seeded
        data -- a gap in the demonstration, not a defect.

        Asserted rather than left as a comment so that adding a
        repeatable group later flips this test and prompts whoever does
        it to widen the coverage claim in SEED-004 D-9.
        """
        repeatable = [
            g for g in self.norm["question_group"] if g.get("repeatable")
        ]
        self.assertEqual(
            repeatable,
            [],
            "a repeatable group was added: `repeat_agg` is now "
            "demonstrable, so update the widget-coverage table",
        )

    def test_status_options_match_the_registration_form(self):
        """A cross-form chart lines the two up by option value."""
        def values(norm, name):
            for group in norm["question_group"]:
                for question in group["question"]:
                    if question["name"] == name:
                        return [o["value"] for o in question["option"]]
            return None

        registration = normalize_form_definition(read_initial_form())
        self.assertEqual(
            values(self.norm, "functional_status"),
            values(registration, "status"),
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class InitialMonitoringFormSeedTest(TestCase):
    def test_a_plain_run_seeds_both_forms_and_links_them(self):
        """Parent before child: the seeder sorts on `parent_hint`."""
        call_command("form_seeder")

        monitoring = Forms.objects.get(pk=MONITORING_FORM_ID)
        self.assertEqual(monitoring.type, FormTypes.monitoring)
        self.assertEqual(monitoring.status, FormStatus.published)
        self.assertEqual(monitoring.parent_id, INITIAL_FORM_ID)
        _, questions = declared_counts(read_monitoring_form())
        self.assertEqual(
            Questions.objects.filter(form=monitoring).count(), questions
        )
        self.assertEqual(Entity.objects.count(), 0)

    def test_the_registration_form_reports_the_monitoring_child(self):
        call_command("form_seeder")

        registration = Forms.objects.get(pk=INITIAL_FORM_ID)
        self.assertEqual(
            list(registration.children.values_list("id", flat=True)),
            [MONITORING_FORM_ID],
        )
