import os
import pandas as pd
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from api.v1.v1_data.models import Answers
from api.v1.v1_forms.models import (
    QuestionTypes,
    Questions,
    QuestionOptions,
)
from utils import storage
from mis.settings import STORAGE_PATH

FILE_DIR = "./source/value_changes"
ISSUE_NUMBER = 1


@override_settings(USE_TZ=False)
class MigrateFormOptionsCommand(TestCase):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        call_command("form_seeder", "--test")
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        user = {"email": "admin@akvo.org", "password": "Test105*"}
        user = self.client.post(
            "/api/v1/login", user, content_type="application/json"
        )
        self.call_command("-r", 2)

        # get answer which has options answer
        answer = Answers.objects.filter(
            question__type__in=[
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]
        ).first()
        self.form_id = answer.question.form_id

        # generate value_change file for test
        self.filename = f"{ISSUE_NUMBER}-{self.form_id}.csv"
        current = []
        next = []
        # populate options
        questions = Questions.objects.filter(
            form=self.form_id,
            type__in=[
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ],
        ).values_list("id", flat=True)
        for option in QuestionOptions.objects.filter(
            question__in=questions
        ).all():
            current.append(option.value)
            next.append(f"new_{self.form_id}_{option.value}")
        # EOL populate options
        # generate file
        df = pd.DataFrame({"current": current, "next": next})
        df.to_csv(f"{FILE_DIR}/{self.filename}")
        # eol generate file

    def test_migrate_form_options(self):
        filename = f"{ISSUE_NUMBER}-{self.form_id}.csv"
        filepath = f"{FILE_DIR}/{filename}"
        self.assertTrue(os.path.exists(filepath))

        answers = answer = Answers.objects.filter(
            question__form_id=self.form_id,
            question__type__in=[
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ],
        ).all()
        prev_answers = {}
        for answer in answers:
            prev_answers.update({answer.id: answer.options})

        # migrate normal
        call_command("migrate_form_options", ISSUE_NUMBER)
        answers = answer = Answers.objects.filter(
            question__form_id=self.form_id,
            question__type__in=[
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ],
        ).all()
        uuids = []
        for answer in answers:
            find_prev_answer = prev_answers[answer.id]
            self.assertEqual(len(answer.options), len(find_prev_answer))
            for v in answer.options:
                self.assertIn(f"new_{self.form_id}", v)
            uuids.append(answer.data.uuid)
        uuids = list(set(uuids))
        for uuid in uuids:
            json_filename = f"datapoints/{uuid}.json"
            self.assertTrue(storage.check(json_filename))

    def test_migrate_form_options_reverse(self):
        # migrate reverse
        call_command("migrate_form_options", ISSUE_NUMBER, "--reverse")
        answers = Answers.objects.filter(
            question__form_id=self.form_id,
            question__type__in=[
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ],
        ).all()
        uuids = []
        for answer in answers:
            for v in answer.options:
                self.assertNotIn(f"new_{self.form_id}", v)
            uuids.append(answer.data.uuid)
        uuids = list(set(uuids))
        # create a new json data file
        answer.data.write_file()
        json_filename = f"datapoints/{answer.data.uuid}.json"
        self.assertTrue(storage.check(json_filename))
        # Remove the generated file
        filepath = f"{STORAGE_PATH}/datapoints/{answer.data.uuid}.json"
        if os.path.exists(filepath):
            os.remove(filepath)

    def tearDown(self):
        filepath = f"{FILE_DIR}/{self.filename}"
        os.remove(filepath)
        self.assertFalse(os.path.exists(filepath))
