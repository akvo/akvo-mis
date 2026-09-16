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
        self.assertEqual(
            QuestionGroup.objects.filter(form=form).count(), 3
        )
        self.assertEqual(Questions.objects.filter(form=form).count(), 9)
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
