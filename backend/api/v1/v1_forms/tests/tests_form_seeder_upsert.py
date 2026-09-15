import json
import os
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    _build_schema_snapshot,
    import_form_definition,
    normalize_form_definition,
)
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
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

    def test_invalid_definition_fails_the_command(self):
        """An unloadable file must not be a silent skip. seeder.sh runs
        the command bare and treats exit 0 as success, so a client form
        that never loaded would otherwise look like a clean install."""
        broken = minimal_form(803, "Broken", 80301)
        broken["type"] = 9
        self.write("client-broken.json", broken)

        with self.assertRaises(CommandError) as caught:
            self.seed()
        self.assertIn("client-broken.json", str(caught.exception))
        # Rolled back as a whole rather than committed half-applied.
        self.assertFalse(Forms.objects.filter(pk=801).exists())


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
class ImportNeverDeleteGroupTestCase(TestCase):
    """The group half of the never_delete guard.

    A group is worth protecting only for the submission data it still
    holds. Both cases below start from form 840 with two groups, an
    answer on the question in the second group, and a second file that
    stops declaring that second group. What differs is where the
    answered question ends up.
    """

    def setUp(self):
        level = Levels.objects.create(name="country", level=1)
        self.administration = Administration.objects.create(
            id=1, name="Indonesia", parent=None, level=level
        )
        self.user = SystemUser.objects.create_superuser(
            email="group-guard@test.com",
            password="Test105*",
            first_name="Group",
            last_name="Guard",
        )

    def age_question(self, order=1):
        return {
            "id": 84102,
            "order": order,
            "name": "age",
            "label": "Age",
            "short_label": "Age",
            "meta": False,
            "type": "number",
            "required": False,
        }

    def build_form(self):
        """Group 84001 holds `full_name`, group 84002 holds `age`."""
        payload = minimal_form(840, "Group Guard", 84101)
        payload["question_groups"][0]["id"] = 84001
        payload["question_groups"].append({
            "id": 84002,
            "order": 2,
            "name": "group_02",
            "label": "Group 02",
            "questions": [self.age_question()],
        })
        Forms.objects.create(id=840, name="Group Guard", version=1)
        self.reseed(payload)

    def answer_age(self):
        """Put a submission behind question 84102."""
        data = FormData.objects.create(
            name="Submission",
            form=Forms.objects.get(pk=840),
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=data,
            question=Questions.objects.get(pk=84102),
            name="kept",
            created_by=self.user,
        )

    def reseed(self, payload, **kwargs):
        import_form_definition(
            normalize_form_definition(payload),
            None,
            mode="create_or_update",
            require_parent=False,
            claim_foreign_questions=True,
            **kwargs
        )

    def test_group_survives_while_it_holds_an_answered_question(self):
        """Group 84002 is dropped from the file, but its question is
        answered and is dropped too, so both must stay: soft-deleting
        the group would hide a group that real submissions still
        reference."""
        self.build_form()
        self.answer_age()

        # Second file: only group 84001, `age` gone entirely.
        self.reseed(
            minimal_form(840, "Group Guard", 84101), never_delete=True
        )

        self.assertIsNone(
            Questions.objects_with_deleted.get(pk=84102).deleted_at
        )
        self.assertIsNone(
            QuestionGroup.objects_with_deleted.get(pk=84002).deleted_at
        )

    def test_group_is_pruned_when_its_answered_question_moved_away(self):
        """Regression for the phantom-group bug.

        Same dropped group, but this time the file still declares the
        answered question — relocated into group 84001. Pass 2 moves the
        question out, so group 84002 ends up empty. It must be pruned:
        an answered question may only protect the group it is actually
        left in, and this one is not.
        """
        self.build_form()
        self.answer_age()

        # Second file: group 84001 only, now holding `age` as well.
        payload = minimal_form(840, "Group Guard", 84101)
        payload["question_groups"][0]["id"] = 84001
        payload["question_groups"][0]["questions"].append(
            self.age_question(order=2)
        )
        self.reseed(payload, never_delete=True)

        moved = Questions.objects_with_deleted.get(pk=84102)
        self.assertIsNone(moved.deleted_at)
        self.assertEqual(moved.question_group_id, 84001)
        self.assertIsNotNone(
            QuestionGroup.objects_with_deleted.get(pk=84002).deleted_at
        )
        # The symptom the soft-delete prevents: an empty group served to
        # the webform, the mobile SQLite export and every schema snapshot.
        snapshot = _build_schema_snapshot(Forms.objects.get(pk=840))
        self.assertEqual(
            [g["id"] for g in snapshot["question_group"]], [84001]
        )


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


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormSeederVersionTestCase(TestCase):
    def setUp(self):
        self.source = tempfile.mkdtemp(prefix="form_seeder_version_")
        self.addCleanup(shutil.rmtree, self.source, ignore_errors=True)

    def write_form(self, label="Full Name", form_type=1):
        payload = minimal_form(830, "Version Form", 83001)
        payload["type"] = form_type
        payload["question_groups"][0]["questions"][0]["label"] = label
        path = os.path.join(self.source, "client-version.json")
        with open(path, "w") as handle:
            json.dump(payload, handle)

    def seed(self):
        call_command(
            "form_seeder",
            source=self.source,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    def test_unchanged_reseed_keeps_version(self):
        """Re-seeding an untouched file must not move the version. The
        form cache is keyed form-{id}-v{version} and mobile devices
        compare versions to decide whether to re-download, so a
        gratuitous bump makes every device in the field re-sync."""
        self.write_form()
        self.seed()
        first = Forms.objects.get(pk=830).version

        self.seed()
        self.assertEqual(Forms.objects.get(pk=830).version, first)

    def test_changed_definition_bumps_version_once(self):
        """A real edit must still reach devices."""
        self.write_form()
        self.seed()
        first = Forms.objects.get(pk=830).version

        self.write_form(label="Full Legal Name")
        self.seed()
        self.assertEqual(Forms.objects.get(pk=830).version, first + 1)

    def test_type_change_bumps_version(self):
        """Retyping a form is a change devices must see. It is invisible
        to _build_schema_snapshot, which describes only the structure
        below the form row, so the fingerprint has to add it back."""
        self.write_form()
        self.seed()
        first = Forms.objects.get(pk=830).version

        self.write_form(form_type=2)
        self.seed()
        self.assertEqual(Forms.objects.get(pk=830).type, 2)
        self.assertEqual(Forms.objects.get(pk=830).version, first + 1)
