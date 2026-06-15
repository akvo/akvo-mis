from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    normalize_form_definition,
    validate_form_definition,
)


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
class ValidateFormDefinitionTestCase(TestCase):
    """Unit tests for validate_form_definition."""

    def test_valid_payload_returns_no_errors(self):
        norm = normalize_form_definition(_make_export_payload())
        issues = validate_form_definition(norm, check_entities=False)
        errors = [i for i in issues if i["level"] == "error"]
        self.assertEqual(errors, [])

    def test_missing_name_is_error(self):
        norm = normalize_form_definition(_make_export_payload())
        norm["name"] = None
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("missing_name", codes)

    def test_invalid_type_is_error(self):
        norm = normalize_form_definition(_make_export_payload())
        norm["type"] = 99
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("invalid_type", codes)

    def test_duplicate_question_id_is_error(self):
        raw = _make_export_payload()
        raw["question_group"][0]["question"][1]["id"] = 999200
        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("duplicate_question_id", codes)

    def test_dangling_dependency_id_is_error(self):
        raw = _make_export_payload()
        raw["question_group"][0]["question"][1]["dependency"] = [
            {"id": 99999, "options": ["yes"]}
        ]
        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("dangling_dependency_id", codes)

    def test_invalid_question_type_is_error(self):
        raw = _make_export_payload()
        raw["question_group"][0]["question"][0]["type"] = "nonexistent_type"
        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("invalid_question_type", codes)

    def test_unsupported_format_version_is_error(self):
        raw = _make_export_payload()
        raw["metadata"]["format_version"] = 999
        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("unsupported_format_version", codes)

    def test_foreign_api_endpoint_is_warning(self):
        raw = _make_export_payload()
        raw["question_group"][0]["question"][0]["api"] = {
            "endpoint": "https://staging.mis.akvo.org/api/v1/cascade/"
        }
        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "warning"]
        self.assertIn("foreign_api_endpoint", codes)

    def test_valid_intra_file_dependency_passes(self):
        norm = normalize_form_definition(_make_export_payload())
        issues = validate_form_definition(norm, check_entities=False)
        error_codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertNotIn("dangling_dependency_id", error_codes)


@override_settings(USE_TZ=False, TEST_ENV=True)
class CascadeApiValidationTestCase(TestCase):
    """Unit tests for cascade api config validation (FB-007).

    akvo-react-form CascadeApiField requires api.list and api.initial;
    max_level is optional.
    Missing fields emit an incomplete_cascade_api warning.
    """

    def _norm_with_cascade(self, api_config):
        return {
            "_meta": None,
            "form_id": 888001,
            "name": "Cascade Test",
            "type": 1,
            "question_group": [
                {
                    "id": 888100,
                    "name": "g1",
                    "order": 1,
                    "question": [
                        {
                            "id": 888200,
                            "name": "location",
                            "label": "Location",
                            "type": "cascade",
                            "order": 1,
                            "api": api_config,
                            "option": [],
                        }
                    ],
                }
            ],
        }

    def _issue_codes(self, norm, level):
        return [
            i["code"]
            for i in validate_form_definition(norm, check_entities=False)
            if i["level"] == level
        ]

    def test_complete_api_config_no_error(self):
        """Complete cascade api (endpoint + list + initial) → no error."""
        norm = self._norm_with_cascade({
            "endpoint": "/api/v1/public/administrations",
            "list": "children",
            "initial": 1,
        })
        self.assertNotIn(
            "incomplete_cascade_api", self._issue_codes(norm, "error")
        )

    def test_complete_api_with_optional_max_level_no_error(self):
        """max_level is optional; its presence is fine."""
        norm = self._norm_with_cascade({
            "endpoint": "/api/v1/public/administrations",
            "list": "children",
            "initial": 1,
            "max_level": 3,
        })
        self.assertNotIn(
            "incomplete_cascade_api", self._issue_codes(norm, "error")
        )

    def test_missing_initial_is_error(self):
        """Cascade api without 'initial' → blocking error."""
        norm = self._norm_with_cascade({
            "endpoint": "/api/v1/public/administrations",
            "list": "children",
        })
        self.assertIn(
            "incomplete_cascade_api", self._issue_codes(norm, "error")
        )

    def test_missing_list_is_error(self):
        """Cascade api without 'list' → blocking error."""
        norm = self._norm_with_cascade({
            "endpoint": "/api/v1/public/administrations",
            "initial": 1,
        })
        self.assertIn(
            "incomplete_cascade_api", self._issue_codes(norm, "error")
        )

    def test_error_message_names_missing_fields(self):
        """Error message explicitly names both missing required fields."""
        norm = self._norm_with_cascade({
            "endpoint": "/api/v1/public/administrations",
        })
        issues = validate_form_definition(norm, check_entities=False)
        err = next(
            (i for i in issues if i["code"] == "incomplete_cascade_api"), None
        )
        self.assertIsNotNone(err)
        self.assertEqual(err["level"], "error")
        self.assertIn("initial", err["message"])
        self.assertIn("list", err["message"])

    def test_entity_cascade_with_api_no_error(self):
        """
        Entity cascade (extra.type='entity') is exempt — uses its own path.
        """
        norm = {
            "_meta": None,
            "form_id": 888002,
            "name": "Entity Test",
            "type": 1,
            "question_group": [
                {
                    "id": 888110,
                    "name": "g1",
                    "order": 1,
                    "question": [
                        {
                            "id": 888210,
                            "name": "school",
                            "type": "cascade",
                            "order": 1,
                            "api": {
                                "endpoint": "/api/v1/entity-data/1/list/"
                            },
                            "extra": {"type": "entity", "name": "School"},
                            "option": [],
                        }
                    ],
                }
            ],
        }
        self.assertNotIn(
            "incomplete_cascade_api", self._issue_codes(norm, "error")
        )

    def test_cascade_without_api_no_error(self):
        """Cascade question with no api at all → no error."""
        norm = self._norm_with_cascade(None)
        self.assertNotIn(
            "incomplete_cascade_api", self._issue_codes(norm, "error")
        )

    def test_normalize_preserves_list_and_initial(self):
        """Normalizer must NOT convert api.list → api.result."""
        raw = {
            "id": 888001,
            "name": "T",
            "type": 1,
            "question_group": [
                {
                    "id": 888100,
                    "name": "g",
                    "order": 1,
                    "question": [
                        {
                            "id": 888200,
                            "name": "location",
                            "type": "cascade",
                            "order": 1,
                            "api": {
                                "endpoint": "/api/v1/public/administrations",
                                "list": "children",
                                "initial": 1,
                                "max_level": 1,
                            },
                        }
                    ],
                }
            ],
        }
        norm = normalize_form_definition(raw)
        api = norm["question_group"][0]["question"][0]["api"]
        self.assertEqual(api["list"], "children")
        self.assertEqual(api["initial"], 1)
        self.assertNotIn("result", api)
