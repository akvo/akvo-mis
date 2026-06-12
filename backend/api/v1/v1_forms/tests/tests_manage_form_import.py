import io
import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.functions import (
    export_form_definition,
    normalize_form_definition,
    validate_form_definition,
    import_form_definition,
)
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_users.models import SystemUser


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


def _make_export_payload(name="Import Test Form", form_id=999001, type_=1):
    """Return a minimal valid FB-007 export dict."""
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
        # displayOnly -> display_only
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
        raw["question_group"][0]["question"][1]["id"] = 999200  # same as [0]
        norm = normalize_form_definition(raw)
        issues = validate_form_definition(norm, check_entities=False)
        codes = [i["code"] for i in issues if i["level"] == "error"]
        self.assertIn("duplicate_question_id", codes)

    def test_dangling_dependency_id_is_error(self):
        raw = _make_export_payload()
        # dependency references id 99999 which doesn't exist in the file
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
class ImportFormDefinitionCreateTestCase(TestCase):
    """Tests for import_form_definition — create path."""

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
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    def test_create_path_produces_draft_form(self):
        raw = _make_export_payload(form_id=888001)
        norm = normalize_form_definition(raw)
        form, action = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(action, "created")
        self.assertEqual(form.status, FormStatus.draft)

    def test_create_path_preserves_form_id_when_free(self):
        raw = _make_export_payload(form_id=888002)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.id, 888002)

    def test_create_path_preserves_question_ids_when_free(self):
        raw = _make_export_payload(form_id=888003)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        q_ids = list(
            Questions.objects.filter(form=form).values_list("id", flat=True)
        )
        self.assertIn(999200, q_ids)
        self.assertIn(999201, q_ids)

    def test_create_path_creates_question_groups(self):
        raw = _make_export_payload(form_id=888004)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(
            QuestionGroup.objects.filter(form=form).count(), 1
        )

    def test_create_path_creates_options(self):
        raw = _make_export_payload(form_id=888005)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        gender_q = Questions.objects.get(form=form, name="gender")
        self.assertEqual(gender_q.options.count(), 2)

    def test_create_copy_mode_assigns_new_form_id(self):
        raw = _make_export_payload(form_id=888006)
        norm = normalize_form_definition(raw)
        form, action = import_form_definition(
            norm, self.user, mode="create_copy"
        )
        self.assertEqual(action, "copied")
        self.assertNotEqual(form.id, 888006)

    def test_create_copy_mode_remaps_dependency_refs(self):
        raw = _make_export_payload(form_id=888007)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_copy"
        )
        gender_q = Questions.objects.get(form=form, name="gender")
        full_name_q = Questions.objects.get(form=form, name="full_name")
        deps = gender_q.dependency or []
        dep_ids = [d["id"] for d in deps]
        self.assertIn(full_name_q.id, dep_ids)
        # Original file id should NOT appear (it was remapped)
        self.assertNotIn(999200, dep_ids)

    def test_import_sets_created_by(self):
        raw = _make_export_payload(form_id=888008)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.created_by, self.user)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ImportFormDefinitionUpdateTestCase(TestCase):
    """Tests for import_form_definition — update path."""

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
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()
        # Pre-create a form so it can be matched by id
        raw = _make_export_payload(form_id=777001)
        norm = normalize_form_definition(raw)
        self.existing_form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )

    def test_update_path_returns_updated_action(self):
        raw = _make_export_payload(
            form_id=self.existing_form.id, name="Updated Form"
        )
        norm = normalize_form_definition(raw)
        _, action = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(action, "updated")

    def test_update_path_syncs_form_name(self):
        raw = _make_export_payload(
            form_id=self.existing_form.id, name="New Name"
        )
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.name, "New Name")
        self.assertEqual(form.id, self.existing_form.id)

    def test_update_path_does_not_change_status(self):
        original_status = self.existing_form.status
        raw = _make_export_payload(form_id=self.existing_form.id)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.status, original_status)

    def test_update_path_soft_deletes_absent_question(self):
        raw = _make_export_payload(form_id=self.existing_form.id)
        # Remove one question from the update payload
        raw["question_group"][0]["question"] = [
            raw["question_group"][0]["question"][0]
        ]
        norm = normalize_form_definition(raw)
        import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        deleted_q = Questions.objects_deleted.filter(
            form=self.existing_form, name="gender"
        ).first()
        self.assertIsNotNone(deleted_q)
        self.assertIsNotNone(deleted_q.deleted_at)

    def test_update_path_does_not_duplicate_form(self):
        count_before = Forms.objects.filter(
            id=self.existing_form.id
        ).count()
        raw = _make_export_payload(form_id=self.existing_form.id)
        norm = normalize_form_definition(raw)
        import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        count_after = Forms.objects.filter(
            id=self.existing_form.id
        ).count()
        self.assertEqual(count_before, count_after)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ImportPreflightAPITestCase(TestCase):
    """Tests for POST /api/v1/manage/forms/import/preflight."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        self.header = _login(self.client)

    def _post_preflight(self, payload, header=None):
        content = json.dumps(payload).encode()
        f = io.BytesIO(content)
        f.name = "form.json"
        return self.client.post(
            "/api/v1/manage/forms/import/preflight",
            {"file": f},
            **(header or self.header),
        )

    def test_valid_file_returns_200_valid_true(self):
        res = self._post_preflight(_make_export_payload(form_id=8880001))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["valid"])

    def test_missing_file_returns_400(self):
        res = self.client.post(
            "/api/v1/manage/forms/import/preflight",
            {},
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_invalid_json_returns_400(self):
        f = io.BytesIO(b"not json at all {}")
        f.name = "bad.json"
        res = self.client.post(
            "/api/v1/manage/forms/import/preflight",
            {"file": f},
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_oversized_file_returns_413(self):
        payload = _make_export_payload(form_id=8880002)
        # Pad the name to push it over the 1-byte cap override
        with self.settings(FORM_IMPORT_MAX_FILE_SIZE=1):
            res = self._post_preflight(payload)
        self.assertEqual(res.status_code, 413)

    def test_duplicate_question_id_returns_valid_false(self):
        raw = _make_export_payload(form_id=8880003)
        raw["question_group"][0]["question"][1]["id"] = 999200
        res = self._post_preflight(raw)
        data = res.json()
        self.assertFalse(data["valid"])
        error_codes = [e["code"] for e in data["errors"]]
        self.assertIn("duplicate_question_id", error_codes)

    def test_match_info_when_form_exists(self):
        # First create the form
        raw = _make_export_payload(form_id=8880004)
        norm = normalize_form_definition(raw)
        user = SystemUser.objects.filter(email="admin@akvo.org").first()
        import_form_definition(norm, user, mode="create_or_update")

        # Then preflight another import with the same id
        raw2 = _make_export_payload(form_id=8880004, name="Different Name")
        res = self._post_preflight(raw2)
        data = res.json()
        self.assertTrue(data["match"]["exists"])
        self.assertTrue(data["match"]["name_mismatch"])

    def test_unauthenticated_returns_401(self):
        f = io.BytesIO(b"{}")
        f.name = "form.json"
        res = self.client.post(
            "/api/v1/manage/forms/import/preflight",
            {"file": f},
        )
        self.assertEqual(res.status_code, 401)


@override_settings(USE_TZ=False, TEST_ENV=True)
class RoundTripTestCase(TestCase):
    """Export -> import reproduces an equivalent form (NFR-4)."""

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
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    def test_export_import_round_trip_preserves_structure(self):
        source_form = Forms.objects.first()
        exported = export_form_definition(source_form)

        # Change form id so it imports as new (avoids collision)
        exported["id"] = 666001
        norm = normalize_form_definition(exported)
        imported_form, action = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(action, "created")

        re_exported = export_form_definition(imported_form)

        # Same number of groups and questions
        self.assertEqual(
            len(exported["question_group"]),
            len(re_exported["question_group"]),
        )
        for og, ig in zip(
            exported["question_group"],
            re_exported["question_group"],
        ):
            self.assertEqual(len(og["question"]), len(ig["question"]))
            for oq, iq in zip(og["question"], ig["question"]):
                self.assertEqual(oq["name"], iq["name"])
                self.assertEqual(oq["type"], iq["type"])
