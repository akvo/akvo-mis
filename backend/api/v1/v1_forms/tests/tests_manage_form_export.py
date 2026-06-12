import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.functions import export_form_definition
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormDefinitionExportTestCase(TestCase):
    """Tests for GET /api/v1/manage/forms/{id}/export (FB-007)."""

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
        self.form = Forms.objects.first()
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    def test_export_returns_200(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)

    def test_export_content_type_is_json(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        self.assertIn("application/json", res["Content-Type"])

    def test_export_content_disposition_header(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        disposition = res.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn(".json", disposition)

    def test_export_body_has_metadata_envelope(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        data = json.loads(res.content)
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["format_version"], 1)
        self.assertIn("exported_at", data["metadata"])

    def test_export_body_has_form_id(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        data = json.loads(res.content)
        self.assertEqual(data["id"], self.form.id)

    def test_export_body_has_question_groups(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        data = json.loads(res.content)
        self.assertIn("question_group", data)
        self.assertIsInstance(data["question_group"], list)

    def test_export_questions_use_editor_keys(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        data = json.loads(res.content)
        for g in data.get("question_group", []):
            for q in g.get("question", []):
                # Editor keys present, snake_case keys absent
                self.assertIn("questionGroupId", q)
                self.assertNotIn("display_only", q)
                self.assertIn("displayOnly", q)

    def test_export_question_type_is_lowercase_string(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export",
            **self.header,
        )
        data = json.loads(res.content)
        for g in data.get("question_group", []):
            for q in g.get("question", []):
                self.assertIsInstance(q["type"], str)
                self.assertEqual(q["type"], q["type"].lower())

    def test_export_unauthenticated_returns_401(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export"
        )
        self.assertEqual(res.status_code, 401)

    def test_export_nonexistent_form_returns_404(self):
        res = self.client.get(
            "/api/v1/manage/forms/999999/export",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    def test_export_form_definition_function(self):
        payload = export_form_definition(self.form)
        self.assertEqual(payload["id"], self.form.id)
        self.assertEqual(payload["metadata"]["format_version"], 1)
        self.assertEqual(payload["type"], self.form.type)
        groups = payload.get("question_group", [])
        self.assertIsInstance(groups, list)
        for g in groups:
            for q in g.get("question", []):
                self.assertIn("questionGroupId", q)
                self.assertEqual(
                    q["questionGroupId"], g["id"]
                )

    def test_export_monitoring_form_has_parent_hint(self):
        """Monitoring forms include parent.{id, name} in the export."""
        reg_form = Forms.objects.filter(
            type=FormTypes.registration
        ).first()
        if reg_form is None:
            self.skipTest("No registration form available")

        mon_form = Forms.objects.create(
            name="Child Monitor",
            type=FormTypes.monitoring,
            parent=reg_form,
            created_by=self.user,
            updated_by=self.user,
        )
        payload = export_form_definition(mon_form)
        self.assertIsNotNone(payload["parent"])
        self.assertEqual(payload["parent"]["id"], reg_form.id)
        self.assertEqual(payload["parent"]["name"], reg_form.name)
