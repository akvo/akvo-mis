from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_data.serializers import (
    SubmitPendingFormSerializer,
    _dependency_met,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmitPendingValidationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        level = Levels.objects.create(name="National", level=1)
        self.administration = Administration.objects.create(
            name="Admin 1", level=level
        )
        self.user = SystemUser.objects.create_user(
            email="testuser@test.com", password="password123"
        )
        self.form = Forms.objects.create(name="Validation Test Form")
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group 1", order=1
        )
        self.repeat_group = QuestionGroup.objects.create(
            form=self.form, name="Repeat Group", order=2, repeatable=True
        )

        # Q1: Text required
        self.q1 = Questions.objects.create(
            form=self.form,
            question_group=self.group,
            name="q_name",
            label="Name",
            type=QuestionTypes.text,
            required=True,
        )

        # Q2: Option (radio/dropdown) required
        self.q2 = Questions.objects.create(
            form=self.form,
            question_group=self.group,
            name="q_gender",
            label="Gender",
            type=QuestionTypes.option,
            required=True,
        )

        # Q3: Dependent question (required if Q2 == 'female') with AND rule
        self.q3 = Questions.objects.create(
            form=self.form,
            question_group=self.group,
            name="q_pregnant",
            label="Pregnant?",
            type=QuestionTypes.option,
            required=True,
            dependency=[{"id": self.q2.id, "options": ["female"]}],
            dependency_rule="AND",
        )

        # Q4: Display only question (required=True, but display_only=True)
        self.q4 = Questions.objects.create(
            form=self.form,
            question_group=self.group,
            name="q_display",
            label="Display Only Notice",
            type=QuestionTypes.text,
            required=True,
            display_only=True,
        )

        # Q5: Disabled question (required=True in DB, but disabled=True)
        self.q5 = Questions.objects.create(
            form=self.form,
            question_group=self.group,
            name="q_disabled",
            label="Disabled Question",
            type=QuestionTypes.text,
            required=True,
            disabled=True,
        )

        # Q6: Repeat group question (required)
        self.q6 = Questions.objects.create(
            form=self.form,
            question_group=self.repeat_group,
            name="q_child_name",
            label="Child Name",
            type=QuestionTypes.text,
            required=True,
        )

    def test_dependency_met_options_and_numbers(self):
        dep_opt = {"id": 1, "options": ["yes", "maybe"]}
        self.assertTrue(_dependency_met(dep_opt, "yes"))
        self.assertTrue(_dependency_met(dep_opt, ["maybe", "no"]))
        self.assertFalse(_dependency_met(dep_opt, "no"))
        self.assertFalse(_dependency_met(dep_opt, None))
        self.assertFalse(_dependency_met(dep_opt, ""))

        dep_range = {"id": 2, "min": 10, "max": 20}
        self.assertTrue(_dependency_met(dep_range, 15))
        self.assertTrue(_dependency_met(dep_range, "10"))
        self.assertTrue(_dependency_met(dep_range, "20"))
        self.assertFalse(_dependency_met(dep_range, 5))
        self.assertFalse(_dependency_met(dep_range, 25))
        self.assertFalse(_dependency_met(dep_range, "invalid"))

    def test_missing_required_answers_raises_validation_error(self):
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": self.administration.id,
            },
            "answer": [
                {"question": self.q1.id, "value": "Alice"},
                # Q2 missing
                # Q6 missing
            ],
        }
        serializer = SubmitPendingFormSerializer(
            data=payload, context={"user": self.user, "form": self.form}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("answer", serializer.errors)
        errors_str = str(serializer.errors["answer"])
        self.assertIn("q_gender", errors_str)
        self.assertIn("q_child_name", errors_str)

    def test_dependent_question_skipped_when_dependency_not_met(self):
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": self.administration.id,
            },
            "answer": [
                {"question": self.q1.id, "value": "Bob"},
                {"question": self.q2.id, "value": ["male"]},
                {"question": self.q6.id, "value": "Child 1", "index": 0},
            ],
        }
        serializer = SubmitPendingFormSerializer(
            data=payload, context={"user": self.user, "form": self.form}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_dependent_question_required_when_dependency_met(self):
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": self.administration.id,
            },
            "answer": [
                {"question": self.q1.id, "value": "Carol"},
                {"question": self.q2.id, "value": ["female"]},
                {"question": self.q6.id, "value": "Child 1", "index": 0},
                # Q3 missing
            ],
        }
        serializer = SubmitPendingFormSerializer(
            data=payload, context={"user": self.user, "form": self.form}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("q_pregnant", str(serializer.errors.get("answer", "")))

    def test_repeat_group_missing_required_at_higher_index(self):
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": self.administration.id,
            },
            "answer": [
                {"question": self.q1.id, "value": "Dan"},
                {"question": self.q2.id, "value": ["male"]},
                {"question": self.q6.id, "value": "Child 1", "index": 0},
                {"question": self.q1.id, "value": "Dan 2", "index": 1},
            ],
        }
        q7 = Questions.objects.create(
            form=self.form,
            question_group=self.repeat_group,
            name="q_child_age",
            label="Child Age",
            type=QuestionTypes.number,
            required=False,
        )
        payload["answer"].append({"question": q7.id, "value": 5, "index": 1})

        serializer = SubmitPendingFormSerializer(
            data=payload, context={"user": self.user, "form": self.form}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("q_child_name", str(serializer.errors.get("answer", "")))
