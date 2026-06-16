import io
import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    export_form_definition,
    normalize_form_definition,
    import_form_definition,
)
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser


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


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


def _reset_pk_sequences():
    with connection.cursor() as cur:
        for tbl in ["form", "question_group", "question", "option"]:
            cur.execute(
                f"SELECT setval("
                f"pg_get_serial_sequence('{tbl}', 'id'),"
                f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
                f"false)"
            )


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
        raw = _make_export_payload(form_id=8880004)
        norm = normalize_form_definition(raw)
        user = SystemUser.objects.filter(email="admin@akvo.org").first()
        import_form_definition(norm, user, mode="create_or_update")

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
    """Export → import reproduces an equivalent form (NFR-4)."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        _reset_pk_sequences()
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    def test_export_import_round_trip_preserves_structure(self):
        source_form = Forms.objects.first()
        exported = export_form_definition(source_form)

        exported["id"] = 666001
        norm = normalize_form_definition(exported)
        imported_form, action = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(action, "created")

        re_exported = export_form_definition(imported_form)

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
