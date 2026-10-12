import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    normalize_form_definition,
    option_value_from_label,
    option_values,
    validate_form_definition,
)
from api.v1.v1_forms.models import QuestionGroup, QuestionOptions, Questions
from api.v1.v1_forms.services.xlsform_import import validate_preflight
from api.v1.v1_forms.tests.tests_form_import_validate import (
    _make_export_payload,
)

# VIZ-027 D-15 (BE-7): a NEW option value may not contain `:`, `,` or `|`.
# Dashboard filters and widget criteria use them as delimiters. Values that
# are already stored stay untouched: answers and dependency rules use them.


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


def _form_payload(options):
    """A one-question form: "Pump type", with the given options."""
    return {
        "name": "Pump Survey",
        "type": 1,
        "approval_instructions": None,
        "parent": None,
        "question_group": [
            {
                "id": None,
                "name": "pumps",
                "label": "Pumps",
                "order": 1,
                "repeatable": False,
                "repeat_text": None,
                "question": [
                    {
                        "id": None,
                        "order": 1,
                        "label": "Pump type",
                        "short_label": None,
                        "name": "pump_type",
                        "type": "option",
                        "meta": False,
                        "required": True,
                        "rule": None,
                        "dependency": None,
                        "dependency_rule": "AND",
                        "api": None,
                        "extra": None,
                        "tooltip": None,
                        "fn": None,
                        "pre": None,
                        "display_only": False,
                        "option": options,
                    }
                ],
            }
        ],
    }


class OptionValueFromLabelTestCase(TestCase):
    """The value generated when a client sends a label but no value."""

    def test_the_rule(self):
        # Lower-case, remove `:` `,` `|`, then whitespace runs -> `_`.
        self.assertEqual(
            {
                label: option_value_from_label(label)
                for label in [
                    "Type A: hand pump", "Yes, partly", "a | b",
                    "New Option 1",
                ]
            },
            {
                "Type A: hand pump": "type_a_hand_pump",
                "Yes, partly": "yes_partly",
                "a | b": "a_b",
                "New Option 1": "new_option_1",
            },
        )


class OptionValuesTestCase(TestCase):
    """The codes of one question's options: removing the delimiters must
    not leave a code empty (global_criteria cannot carry one) or equal to
    a sibling's (the (question, value) unique constraint)."""

    def test_a_label_of_only_delimiters_gets_a_code(self):
        self.assertEqual(option_values([{"label": ":"}]), ["option"])

    def test_generated_codes_never_collide(self):
        self.assertEqual(
            option_values([
                {"label": "AB"}, {"label": "A:B"}, {"label": ":"},
                {"label": "|"},
            ]),
            ["ab", "ab_1", "option", "option_1"],
        )

    def test_a_given_code_is_kept_and_a_generated_one_avoids_it(self):
        self.assertEqual(
            option_values([{"label": "A:B"}, {"label": "X", "value": "ab"}]),
            ["ab_1", "ab"],
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class BuilderOptionValueTestCase(TestCase):
    """The form builder's create and update (validate_form_payload)."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        with connection.cursor() as cur:
            for tbl in ["form", "question_group", "question", "option"]:
                cur.execute(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{tbl}', 'id'),"
                    f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
                    f"false)"
                )
        self.header = _login(self.client)

    def create(self, options):
        return self.client.post(
            "/api/v1/manage/forms",
            json.dumps(_form_payload(options)),
            content_type="application/json",
            **self.header,
        )

    def test_a_code_with_a_delimiter_is_refused(self):
        # The editor proposes `type_a:_hand_pump` for "Type A: hand pump";
        # the author must edit the code before the form saves.
        results = {}
        for code in ["type_a:_hand_pump", "yes,_partly", "a|b"]:
            res = self.create([{"label": "Option", "value": code}])
            results[code] = res.status_code
        self.assertEqual(results, dict.fromkeys(results, 400))

    def test_the_error_names_the_option_the_question_and_the_code(self):
        res = self.create([
            {"label": "Type A: hand pump", "value": "type_a:_hand_pump"},
        ])
        self.assertEqual(res.status_code, 400)
        message = res.json()["message"]
        for part in ["Type A: hand pump", "Pump type", "type_a:_hand_pump"]:
            self.assertIn(part, message)

    def test_a_clean_code_saves(self):
        res = self.create([
            {"label": "Type A: hand pump", "value": "type_a_hand_pump"},
        ])
        self.assertEqual(res.status_code, 201, res.content)

    def test_a_label_without_a_code_gets_a_clean_generated_code(self):
        res = self.create([{"label": "Type A: hand pump", "value": ""}])
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(
            list(
                QuestionOptions.objects.filter(
                    question__form_id=res.json()["id"],
                ).values_list("value", flat=True)
            ),
            ["type_a_hand_pump"],
        )

    def test_labels_that_clean_to_the_same_code_still_save(self):
        res = self.create([
            {"label": "AB", "value": ""},
            {"label": "A:B", "value": ""},
            {"label": ":", "value": ""},
        ])
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(
            sorted(
                QuestionOptions.objects.filter(
                    question__form_id=res.json()["id"],
                ).values_list("value", flat=True)
            ),
            ["ab", "ab_1", "option"],
        )

    def test_an_existing_code_with_a_delimiter_can_still_be_saved(self):
        # An older form already stores `a:b`; editing anything else on it
        # must keep working.
        res = self.create([{"label": "A or B", "value": "a_b"}])
        self.assertEqual(res.status_code, 201, res.content)
        form_id = res.json()["id"]
        question = Questions.objects.get(form_id=form_id, name="pump_type")
        QuestionOptions.objects.filter(question=question).update(value="a:b")

        payload = _form_payload([{"label": "A or B", "value": "a:b"}])
        payload["question_group"][0]["id"] = QuestionGroup.objects.get(
            form_id=form_id,
        ).id
        payload["question_group"][0]["question"][0]["id"] = question.id
        payload["name"] = "Pump Survey, renamed"
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200, res.content)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ImportOptionValueTestCase(TestCase):
    """JSON import (validate_form_definition) and XLSForm import
    (validate_preflight) refuse the same codes."""

    def test_json_import_refuses_a_code_with_a_delimiter(self):
        raw = _make_export_payload()
        raw["question_group"][0]["question"][1]["option"][0]["value"] = (
            "male:adult"
        )
        issues = validate_form_definition(
            normalize_form_definition(raw), check_entities=False,
        )
        self.assertIn(
            "invalid_option_value",
            [i["code"] for i in issues if i["level"] == "error"],
        )

    def test_xlsform_import_refuses_a_code_with_a_delimiter(self):
        parsed = {
            "total_questions": 1,
            "question_groups": [{
                "question": [{
                    "id": 1,
                    "label": "Pump type",
                    "option": [
                        {"label": "Type A: hand pump",
                         "value": "type_a:_hand_pump"},
                    ],
                }],
            }],
        }
        errors, _ = validate_preflight(parsed)
        self.assertTrue(
            any("type_a:_hand_pump" in e["message"] for e in errors),
            errors,
        )
