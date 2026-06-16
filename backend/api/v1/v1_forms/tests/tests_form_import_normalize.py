from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.functions import normalize_form_definition


def _make_export_payload(name="Import Test Form", form_id=999001, type_=1):
    return {
        "metadata": {
            "format_version": 1,
            "exported_at": "2026-06-12T00:00:00Z",
            "source": "staging.mis.akvo.org",
        },
        "id": form_id,
        "name": name,
        "type": type_,
        "question_group": [
            {
                "id": 999100,
                "name": "main_group",
                "label": "Main",
                "order": 1,
                "question": [
                    {
                        "id": 999200,
                        "name": "full_name",
                        "label": "Full Name",
                        "type": "input",
                        "order": 1,
                        "questionGroupId": 999100,
                        "required": True,
                        "meta": True,
                        "dependency": None,
                        "displayOnly": False,
                        "option": [],
                    },
                    {
                        "id": 999201,
                        "name": "gender",
                        "label": "Gender",
                        "type": "option",
                        "order": 2,
                        "questionGroupId": 999100,
                        "required": True,
                        "dependency": [{"id": 999200, "options": ["yes"]}],
                        "displayOnly": False,
                        "option": [
                            {"label": "Male", "value": "male", "order": 1},
                            {"label": "Female", "value": "female", "order": 2},
                        ],
                    },
                ],
            }
        ],
    }


@override_settings(USE_TZ=False, TEST_ENV=True)
class NormalizeFormDefinitionTestCase(TestCase):
    """Unit tests for normalize_form_definition."""

    def test_fb007_envelope_accepted(self):
        raw = _make_export_payload()
        norm = normalize_form_definition(raw)
        self.assertEqual(norm["form_id"], 999001)
        self.assertEqual(norm["name"], "Import Test Form")
        self.assertEqual(norm["type"], FormTypes.registration)

    def test_metadata_preserved(self):
        raw = _make_export_payload()
        norm = normalize_form_definition(raw)
        self.assertIsNotNone(norm["_meta"])
        self.assertEqual(norm["_meta"]["format_version"], 1)

    def test_legacy_format_accepted(self):
        """Legacy seeder format: 'form' key, 'question_groups', 'questions'."""
        raw = {
            "form": "Legacy Survey",
            "type": 1,
            "question_groups": [
                {
                    "name": "grp1",
                    "questions": [
                        {"id": 1, "name": "q1", "label": "Q1", "type": "input",
                         "order": 1}
                    ],
                }
            ],
        }
        norm = normalize_form_definition(raw)
        self.assertEqual(norm["name"], "Legacy Survey")
        groups = norm["question_group"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["question"]), 1)

    def test_camel_keys_normalized_to_snake(self):
        raw = _make_export_payload()
        norm = normalize_form_definition(raw)
        q = norm["question_group"][0]["question"][0]
        self.assertIn("display_only", q)
        self.assertNotIn("displayOnly", q)

    def test_questionGroupId_renamed(self):
        raw = _make_export_payload()
        norm = normalize_form_definition(raw)
        q = norm["question_group"][0]["question"][0]
        self.assertIn("question_group_id", q)
        self.assertNotIn("questionGroupId", q)

    def test_type_string_registration(self):
        raw = _make_export_payload()
        raw["type"] = "registration"
        norm = normalize_form_definition(raw)
        self.assertEqual(norm["type"], FormTypes.registration)

    def test_type_string_monitoring(self):
        raw = _make_export_payload()
        raw["type"] = "monitoring"
        norm = normalize_form_definition(raw)
        self.assertEqual(norm["type"], FormTypes.monitoring)

    def test_parent_hint_preserved(self):
        raw = _make_export_payload(type_=2)
        raw["parent"] = {"id": 5, "name": "Reg Form"}
        norm = normalize_form_definition(raw)
        self.assertEqual(norm["parent_hint"]["id"], 5)

    def test_question_type_lowercased(self):
        raw = _make_export_payload()
        raw["question_group"][0]["question"][0]["type"] = "Input"
        norm = normalize_form_definition(raw)
        q = norm["question_group"][0]["question"][0]
        self.assertEqual(q["type"], "input")
