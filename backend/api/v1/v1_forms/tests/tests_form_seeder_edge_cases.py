import json
import os
import shutil
import tempfile
from io import StringIO

from django.test.utils import override_settings
from django.core.management import call_command
from django.test import TestCase

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_data.models import FormData, Answers, AnswerHistory
from api.v1.v1_forms.models import (
    Forms, Questions, QuestionGroup as QG,
)
from api.v1.v1_forms.management.commands.form_seeder import (
    migrate_question_answers,
)
from api.v1.v1_users.models import SystemUser
from utils.functions import atomic_write_json


def seed_administration_test():
    level = Levels(name="country", level=1)
    level.save()
    administration = Administration(
        id=1, name="Indonesia", parent=None, level=level
    )
    administration.save()


@override_settings(USE_TZ=False)
class MigrateQuestionAnswersEdgeCaseTests(TestCase):
    """Edge-case tests for migrate_question_answers."""

    def setUp(self):
        seed_administration_test()
        call_command(
            "form_seeder", "--test",
            stdout=StringIO(), stderr=StringIO()
        )

        self.admin = Administration.objects.first()
        self.user = SystemUser.objects.create_superuser(
            email="edge_test@test.com",
            password="Test105*",
            first_name="Edge",
            last_name="Tester",
        )
        self.reg_form = Forms.objects.get(pk=1)
        self.mon_form = Forms.objects.get(pk=10001)
        self.question = Questions.objects.get(pk=109)

        self.reg_data = FormData.objects.create(
            name="Edge Registration",
            form=self.reg_form,
            administration=self.admin,
            created_by=self.user,
        )

    def test_no_children_answer_stays_on_source(self):
        """When registration data has no children,
        the answer must remain on the source data."""
        Answers.objects.create(
            data=self.reg_data,
            question=self.question,
            value=42.0,
            created_by=self.user,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        self.assertTrue(
            Answers.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )

    def test_pending_and_draft_children_are_skipped(self):
        """Pending and draft children should NOT receive migrated answers;
        the answer stays on the source data."""
        FormData.objects.create(
            name="Pending Child",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
            is_pending=True,
        )
        FormData.objects.create(
            name="Draft Child",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
            is_draft=True,
        )
        Answers.objects.create(
            data=self.reg_data,
            question=self.question,
            value=7.0,
            created_by=self.user,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        # Answer remains on source because no valid child exists
        self.assertTrue(
            Answers.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )
        # No answer copied to the pending/draft children
        self.assertEqual(
            Answers.objects.filter(question=self.question).exclude(
                data=self.reg_data
            ).count(),
            0,
        )

    def test_multiple_children_each_get_copy(self):
        """When a registration datapoint has multiple valid monitoring
        children, each child should receive a copy of the answer."""
        child_1 = FormData.objects.create(
            name="Mon Child 1",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
        )
        child_2 = FormData.objects.create(
            name="Mon Child 2",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
        )
        Answers.objects.create(
            data=self.reg_data,
            question=self.question,
            value=99.0,
            created_by=self.user,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        self.assertFalse(
            Answers.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )
        self.assertTrue(
            Answers.objects.filter(
                data=child_1, question=self.question, value=99.0
            ).exists()
        )
        self.assertTrue(
            Answers.objects.filter(
                data=child_2, question=self.question, value=99.0
            ).exists()
        )

    def test_answer_fields_are_fully_copied(self):
        """All answer fields (name, value, options, index) should be
        faithfully copied to the child answer."""
        child = FormData.objects.create(
            name="Mon Child",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
        )
        Answers.objects.create(
            data=self.reg_data,
            question=self.question,
            name="some text",
            value=1.5,
            options=["opt_a", "opt_b"],
            created_by=self.user,
            index=3,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        copied = Answers.objects.get(data=child, question=self.question)
        self.assertEqual(copied.name, "some text")
        self.assertEqual(copied.value, 1.5)
        self.assertEqual(copied.options, ["opt_a", "opt_b"])
        self.assertEqual(copied.index, 3)
        self.assertEqual(copied.created_by, self.user)

    def test_answer_history_migrated_to_children(self):
        """AnswerHistory records should also be redistributed
        to monitoring children."""
        child = FormData.objects.create(
            name="Mon Child",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
        )
        AnswerHistory.objects.create(
            data=self.reg_data,
            question=self.question,
            name="old text",
            value=10.0,
            options=["x"],
            created_by=self.user,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        self.assertFalse(
            AnswerHistory.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )
        hist = AnswerHistory.objects.get(
            data=child, question=self.question
        )
        self.assertEqual(hist.name, "old text")
        self.assertEqual(hist.value, 10.0)
        self.assertEqual(hist.options, ["x"])

    def test_answer_history_no_children_stays(self):
        """AnswerHistory should stay on source when there are
        no matching monitoring children."""
        AnswerHistory.objects.create(
            data=self.reg_data,
            question=self.question,
            name="hist",
            value=5.0,
            created_by=self.user,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        self.assertTrue(
            AnswerHistory.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )

    def test_nonexistent_target_form_is_noop(self):
        """When target_form_id doesn't exist, nothing should happen."""
        Answers.objects.create(
            data=self.reg_data,
            question=self.question,
            value=1.0,
            created_by=self.user,
        )

        migrate_question_answers(self.question, target_form_id=999999)

        self.assertTrue(
            Answers.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )

    def test_multiple_registration_datapoints_independent(self):
        """Each registration datapoint should be handled independently:
        one with children migrates, one without children keeps."""
        child = FormData.objects.create(
            name="Mon Child",
            form=self.mon_form,
            administration=self.admin,
            created_by=self.user,
            parent=self.reg_data,
        )
        Answers.objects.create(
            data=self.reg_data,
            question=self.question,
            value=11.0,
            created_by=self.user,
        )

        reg_data_2 = FormData.objects.create(
            name="Edge Registration 2",
            form=self.reg_form,
            administration=self.admin,
            created_by=self.user,
        )
        Answers.objects.create(
            data=reg_data_2,
            question=self.question,
            value=22.0,
            created_by=self.user,
        )

        migrate_question_answers(self.question, self.mon_form.id)

        # First datapoint: migrated to child, removed from parent
        self.assertFalse(
            Answers.objects.filter(
                data=self.reg_data, question=self.question
            ).exists()
        )
        self.assertTrue(
            Answers.objects.filter(
                data=child, question=self.question, value=11.0
            ).exists()
        )
        # Second datapoint: no children, stays on source
        self.assertTrue(
            Answers.objects.filter(
                data=reg_data_2, question=self.question, value=22.0
            ).exists()
        )

    def test_question_truly_removed_is_deleted(self):
        """When a question is removed from all forms (not just moved),
        the question itself should be deleted by the seeder."""
        # Isolated copy so we never mutate the shared repo fixtures
        # (races with other fixture-mutating tests under --parallel).
        tmp_source = tempfile.mkdtemp(prefix="form_seeder_removed_")
        shutil.copytree("./source/forms/", tmp_source, dirs_exist_ok=True)
        form1_path = os.path.join(tmp_source, "example-1.json")

        try:
            with open(form1_path, "r") as f:
                form1_json = json.load(f)
            # Remove question 111 (autofield: multiple_of_two)
            form1_json["question_groups"][0]["questions"] = [
                q
                for q in form1_json["question_groups"][0]["questions"]
                if q["id"] != 111
            ]
            atomic_write_json(form1_path, form1_json)

            call_command(
                "form_seeder", "--test", source=tmp_source,
                stdout=StringIO(), stderr=StringIO()
            )
            self.assertFalse(Questions.objects.filter(pk=111).exists())
        finally:
            shutil.rmtree(tmp_source, ignore_errors=True)

    def test_empty_question_group_cleaned_after_cross_form_move(self):
        """When all questions in a group move to another form,
        the now-empty group should be deleted in the same seeder run."""
        # Isolated copy so we never mutate the shared repo fixtures
        # (races with other fixture-mutating tests under --parallel).
        tmp_source = tempfile.mkdtemp(prefix="form_seeder_emptyqg_")
        shutil.copytree("./source/forms/", tmp_source, dirs_exist_ok=True)
        form1_path = os.path.join(tmp_source, "example-1.json")
        mon_path = os.path.join(tmp_source, "example-1.1.monitoring.json")

        try:
            with open(form1_path, "r") as f:
                form1_json = json.load(f)
            with open(mon_path, "r") as f:
                mon_orig = f.read()
            # Add a second question group (id=12) with one question
            # (id=112) to form 1
            form1_json["question_groups"].append({
                "id": 12,
                "order": 2,
                "name": "temp_group",
                "label": "Temporary Group",
                "questions": [{
                    "id": 112,
                    "order": 1,
                    "name": "temp_q",
                    "label": "Temp Question",
                    "type": "input",
                    "meta": False,
                    "required": False,
                }],
            })
            atomic_write_json(form1_path, form1_json)

            # Seed so QG 12 with question 112 exists in DB
            call_command(
                "form_seeder", "--test", source=tmp_source,
                stdout=StringIO(), stderr=StringIO()
            )
            self.assertTrue(QG.objects.filter(pk=12).exists())
            self.assertTrue(Questions.objects.filter(pk=112).exists())

            # Now move question 112 to monitoring form and remove QG 12
            form1_json["question_groups"] = [
                qg for qg in form1_json["question_groups"]
                if qg["id"] != 12
            ]
            mon_json = json.loads(mon_orig)
            q112 = {
                "id": 112,
                "order": 99,
                "name": "temp_q",
                "label": "Temp Question",
                "type": "input",
                "meta": False,
                "required": False,
            }
            mon_json["question_groups"][0]["questions"].append(q112)

            atomic_write_json(form1_path, form1_json)
            atomic_write_json(mon_path, mon_json)

            # Re-seed: question moves, group should be cleaned up
            call_command(
                "form_seeder", "--test", source=tmp_source,
                stdout=StringIO(), stderr=StringIO()
            )

            # Question 112 now belongs to monitoring form
            q = Questions.objects.get(pk=112)
            self.assertEqual(q.form_id, self.mon_form.id)

            # QG 12 should be deleted (empty after cross-form move)
            self.assertFalse(QG.objects.filter(pk=12).exists())

        finally:
            shutil.rmtree(tmp_source, ignore_errors=True)
