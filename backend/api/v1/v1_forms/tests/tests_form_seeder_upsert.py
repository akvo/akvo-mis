import json
import os
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    import_form_definition,
    normalize_form_definition,
)
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser


def minimal_form(form_id, name, question_id):
    """Smallest definition normalize_form_definition() accepts.

    Legacy seeder shape: form/question_groups/questions. Types are strings
    here because the normalizer maps them to QuestionTypes constants.
    """
    return {
        "id": form_id,
        "form": name,
        "version": 1,
        "type": 1,
        "question_groups": [
            {
                "id": form_id * 100,
                "order": 1,
                "name": "group_01",
                "label": "Group 01",
                "questions": [
                    {
                        "id": question_id,
                        "order": 1,
                        "name": "full_name",
                        "label": "Full Name",
                        "short_label": "Name",
                        "meta": True,
                        "type": "text",
                        "required": True,
                    }
                ],
            }
        ],
    }


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormSeederFileSelectionTestCase(TestCase):
    def setUp(self):
        self.source = tempfile.mkdtemp(prefix="form_seeder_select_")
        self.addCleanup(shutil.rmtree, self.source, ignore_errors=True)
        self.write("example-alpha.json", minimal_form(801, "Alpha", 80101))
        self.write("client-beta.json", minimal_form(802, "Beta", 80201))

    def write(self, filename, payload):
        path = os.path.join(self.source, filename)
        with open(path, "w") as handle:
            json.dump(payload, handle)

    def seed(self, *args):
        out = StringIO()
        call_command(
            "form_seeder",
            *args,
            source=self.source,
            stdout=out,
            stderr=StringIO(),
        )
        return out.getvalue()

    def test_plain_run_loads_every_json(self):
        """No flag: every *.json in the folder is seeded, whatever it
        is named. This is the point of the change — real deployments
        drop their own definitions here."""
        self.seed()
        self.assertTrue(Forms.objects.filter(pk=801).exists())
        self.assertTrue(Forms.objects.filter(pk=802).exists())

    def test_test_flag_narrows_to_examples(self):
        """--test still selects only the bundled example fixtures, so
        the 110 existing call sites keep their current meaning."""
        self.seed("--test", 1)
        self.assertTrue(Forms.objects.filter(pk=801).exists())
        self.assertFalse(Forms.objects.filter(pk=802).exists())


@override_settings(USE_TZ=False, TEST_ENV=True)
class ImportNeverDeleteTestCase(TestCase):
    def build_form(self):
        """Seed form 810 with two questions via the import writer."""
        payload = minimal_form(810, "Never Delete", 81001)
        group = payload["question_groups"][0]
        group["questions"].append({
            "id": 81002,
            "order": 2,
            "name": "age",
            "label": "Age",
            "short_label": "Age",
            "meta": False,
            "type": "number",
            "required": False,
        })
        norm = normalize_form_definition(payload)
        Forms.objects.create(id=810, name="Never Delete", version=1)
        import_form_definition(
            norm, None, mode="create_or_update", require_parent=False
        )

    def shrunk_norm(self):
        """Same form with question 81002 dropped from the definition."""
        return normalize_form_definition(
            minimal_form(810, "Never Delete", 81001)
        )

    def test_never_delete_keeps_absent_question(self):
        """With never_delete=True a question missing from the payload
        survives when it has answers, so the submissions that answered
        it stay intact. An unanswered question has nothing to protect —
        see test_never_delete_still_prunes_unanswered_question."""
        self.build_form()
        level = Levels.objects.create(name="country", level=1)
        administration = Administration.objects.create(
            id=1, name="Indonesia", parent=None, level=level
        )
        user = SystemUser.objects.create_superuser(
            email="never-delete@test.com",
            password="Test105*",
            first_name="Never",
            last_name="Delete",
        )
        data = FormData.objects.create(
            name="Submission",
            form=Forms.objects.get(pk=810),
            administration=administration,
            created_by=user,
        )
        Answers.objects.create(
            data=data,
            question=Questions.objects.get(pk=81002),
            name="kept",
            created_by=user,
        )

        import_form_definition(
            self.shrunk_norm(), None, mode="create_or_update",
            require_parent=False, never_delete=True,
        )
        question = Questions.objects_with_deleted.get(pk=81002)
        self.assertIsNone(question.deleted_at)

    def test_never_delete_still_prunes_unanswered_question(self):
        """never_delete protects submission data, not structure. An
        unanswered question is still pruned — that is what frees the
        (form, name) slot a cross-form move needs."""
        self.build_form()
        import_form_definition(
            self.shrunk_norm(), None, mode="create_or_update",
            require_parent=False, never_delete=True,
        )
        question = Questions.objects_with_deleted.get(pk=81002)
        self.assertIsNotNone(question.deleted_at)

    def test_default_still_deletes_absent_question(self):
        """Without the flag the writer behaves exactly as before. This
        pins the form-import job path (v1_forms/tasks.py), the only
        other caller of import_form_definition."""
        self.build_form()
        import_form_definition(
            self.shrunk_norm(), None, mode="create_or_update",
            require_parent=False,
        )
        question = Questions.objects_with_deleted.get(pk=81002)
        self.assertIsNotNone(question.deleted_at)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormSeederNoDataLossTestCase(TestCase):
    def setUp(self):
        self.source = tempfile.mkdtemp(prefix="form_seeder_upsert_")
        self.addCleanup(shutil.rmtree, self.source, ignore_errors=True)
        level = Levels.objects.create(name="country", level=1)
        self.administration = Administration.objects.create(
            id=1, name="Indonesia", parent=None, level=level
        )
        self.user = SystemUser.objects.create_superuser(
            email="upsert@test.com",
            password="Test105*",
            first_name="Up",
            last_name="Sert",
        )

    def write_form(self, question_ids):
        """Write form 820 to the source folder with the given questions."""
        payload = minimal_form(820, "Upsert Form", question_ids[0])
        group = payload["question_groups"][0]
        for order, q_id in enumerate(question_ids[1:], start=2):
            group["questions"].append({
                "id": q_id,
                "order": order,
                "name": "extra_{0}".format(q_id),
                "label": "Extra {0}".format(q_id),
                "short_label": None,
                "meta": False,
                "type": "text",
                "required": False,
            })
        path = os.path.join(self.source, "client-upsert.json")
        with open(path, "w") as handle:
            json.dump(payload, handle)

    def seed(self):
        call_command(
            "form_seeder",
            source=self.source,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    def test_reseed_keeps_dropped_question_and_its_answers(self):
        """The whole point: a question the file stops declaring keeps
        its row, so submissions that answered it stay intact."""
        self.write_form([82001, 82002])
        self.seed()

        data = FormData.objects.create(
            name="Submission",
            form=Forms.objects.get(pk=820),
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=data,
            question=Questions.objects.get(pk=82002),
            name="kept",
            created_by=self.user,
        )

        self.write_form([82001])
        self.seed()

        question = Questions.objects_with_deleted.get(pk=82002)
        self.assertIsNone(question.deleted_at)
        self.assertTrue(
            Answers.objects.filter(question_id=82002, data=data).exists()
        )
