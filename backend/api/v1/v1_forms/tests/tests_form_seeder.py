import json
import os
from io import StringIO

from django.test.utils import override_settings
from django.core.management import call_command
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_data.models import FormData, Answers, AnswerHistory
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_users.models import SystemUser
from django.test import TestCase
from utils.functions import atomic_write, atomic_write_json


def seed_administration_test():
    level = Levels(name="country", level=1)
    level.save()
    administration = Administration(
        id=1, name="Indonesia", parent=None, level=level
    )
    administration.save()
    administration = Administration(
        id=2, name="Jakarta", parent=administration, level=level
    )
    administration.save()


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormSeederTestCase(TestCase):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "form_seeder",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def get_question_group(self, form, question_group_name):
        return [
            g
            for g in form["question_group"]
            if g["name"] == question_group_name
        ][0]

    def get_user_token(self):
        user = {"email": "admin@akvo.org", "password": "Test105*"}
        user = self.client.post(
            "/api/v1/login", user, content_type="application/json"
        )
        user = user.json()
        return user.get("token")

    def test_call_command(self):

        self.maxDiff = None
        forms = Forms.objects.all().delete()

        # RUN SEED NEW FORM
        output = self.call_command()
        output = list(filter(lambda x: len(x), output.split("\n")))
        forms = Forms.objects.all()
        self.assertEqual(forms.count(), 0)
        # assert output contains expected log messages
        self.assertListEqual(output, [])

    def test_additional_attributes(self):
        seed_administration_test()
        self.call_command("--test")
        token = self.get_user_token()
        form_id = 2

        response = self.client.get(
            f"/api/v1/form/web/{form_id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        data = response.json()
        self.assertIn("approval_instructions", data)
        gender = [
            q
            for q in data["question_group"][0]["question"]
            if q["name"] == "gender"
        ][0]
        self.assertIn("tooltip", gender)
        self.assertIn("color", gender["option"][0])
        autofield = [
            q
            for q in data["question_group"][0]["question"]
            if q["name"] == "autofield"
        ][0]
        self.assertIn("fn", autofield)

    def test_question_pre_field(self):
        seed_administration_test()
        self.call_command("--test")
        token = self.get_user_token()
        form_id = 2

        response = self.client.get(
            f"/api/v1/form/web/{form_id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        data = response.json()
        gender = [
            q
            for q in data["question_group"][0]["question"]
            if q["name"] == "gender"
        ][0]
        self.assertIn("pre", gender)

    def test_display_only_and_monitoring_field(self):
        seed_administration_test()
        self.call_command("--test")
        token = self.get_user_token()
        form_id = 2

        response = self.client.get(
            f"/api/v1/form/web/{form_id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        data = response.json()
        name = [
            q
            for q in data["question_group"][0]["question"]
            if q["name"] == "name"
        ][0]
        self.assertIn("displayOnly", name)
        self.assertTrue(name["displayOnly"])
        phone = [
            q
            for q in data["question_group"][0]["question"]
            if q["name"] == "phone"
        ][0]
        self.assertEqual(phone["short_label"], "Phone Number")

    def test_repeatable_question_group(self):
        seed_administration_test()
        self.call_command("--test")
        token = self.get_user_token()
        form_id = 4

        response = self.client.get(
            f"/api/v1/form/web/{form_id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        data = response.json()
        question_group = [
            qg
            for qg in data["question_group"]
            if qg["name"] == "testimonials"
        ][0]
        self.assertIn("repeatable", question_group)
        self.assertTrue(question_group["repeatable"])
        self.assertIn("repeat_text", question_group)
        self.assertEqual(
            question_group["repeat_text"], "Add more"
        )

    def test_form_seeder_with_children(self):
        seed_administration_test()
        self.call_command("--test")
        form_1 = Forms.objects.get(pk=1)
        form_2 = Forms.objects.get(pk=2)

        self.assertEqual(form_1.name, "Test Form")
        self.assertEqual(form_2.name, "Test Form 2")
        self.assertEqual(form_1.children.count(), 2)
        self.assertEqual(form_2.children.count(), 0)

    def test_answer_migration_on_question_move(self):
        """When a question moves between forms, answers should
        be redistributed to monitoring FormData children."""
        seed_administration_test()

        # Step 1: Seed forms — question 109 belongs to form 1
        self.call_command("--test")

        reg_form = Forms.objects.get(pk=1)
        mon_form = Forms.objects.get(pk=10001)
        question_109 = Questions.objects.get(pk=109)
        self.assertEqual(question_109.form_id, 1)

        # Step 2: Create test data
        admin = Administration.objects.first()
        user = SystemUser.objects.create_superuser(
            email="migration_test@test.com",
            password="Test105*",
            first_name="Test",
            last_name="User",
        )

        reg_data = FormData.objects.create(
            name="Test Registration",
            form=reg_form,
            administration=admin,
            created_by=user,
        )
        Answers.objects.create(
            data=reg_data,
            question=question_109,
            value=3.14,
            created_by=user,
        )
        AnswerHistory.objects.create(
            data=reg_data,
            question=question_109,
            name="history entry",
            value=2.71,
            created_by=user,
        )

        # Create monitoring child
        mon_data = FormData.objects.create(
            name="Test Monitoring",
            form=mon_form,
            administration=admin,
            created_by=user,
            parent=reg_data,
        )

        # Step 3: Modify fixtures to move question 109 to monitoring
        source_folder = "./source/forms/"
        form1_path = os.path.join(source_folder, "example-1.json")
        mon_path = os.path.join(
            source_folder, "example-1.1.monitoring.json"
        )

        with open(form1_path, "r") as f:
            form1_orig = f.read()
        with open(mon_path, "r") as f:
            mon_orig = f.read()

        try:
            form1_json = json.loads(form1_orig)
            mon_json = json.loads(mon_orig)

            # Extract question 109 from registration form
            q109 = next(
                q
                for q in form1_json["question_groups"][0]["questions"]
                if q["id"] == 109
            )
            form1_json["question_groups"][0]["questions"] = [
                q
                for q in form1_json["question_groups"][0]["questions"]
                if q["id"] != 109
            ]
            # Replace question 10109 (same name "decimal") with 109
            mon_json["question_groups"][0]["questions"] = [
                q
                for q in mon_json["question_groups"][0]["questions"]
                if q["id"] != 10109
            ]
            mon_json["question_groups"][0]["questions"].append(q109)

            atomic_write_json(form1_path, form1_json)
            atomic_write_json(mon_path, mon_json)

            # Step 4: Re-run seeder with modified fixtures
            self.call_command("--test")

            # Step 5: Assert question now belongs to monitoring form
            question_109.refresh_from_db()
            self.assertEqual(question_109.form_id, mon_form.id)

            # Step 6: Answer redistributed to monitoring FormData
            mon_answers = Answers.objects.filter(
                data=mon_data, question=question_109
            )
            self.assertTrue(mon_answers.exists())
            self.assertEqual(mon_answers.first().value, 3.14)

            # Step 7: Original answer removed from registration data
            reg_answers = Answers.objects.filter(
                data=reg_data, question=question_109
            )
            self.assertFalse(reg_answers.exists())

            # Step 8: AnswerHistory redistributed to monitoring FormData
            mon_history = AnswerHistory.objects.filter(
                data=mon_data, question=question_109
            )
            self.assertTrue(mon_history.exists())
            self.assertEqual(mon_history.first().value, 2.71)
            self.assertEqual(mon_history.first().name, "history entry")

            # Step 9: Original history removed from registration data
            reg_history = AnswerHistory.objects.filter(
                data=reg_data, question=question_109
            )
            self.assertFalse(reg_history.exists())

        finally:
            # Restore original fixtures
            atomic_write(form1_path, form1_orig)
            atomic_write(mon_path, mon_orig)
