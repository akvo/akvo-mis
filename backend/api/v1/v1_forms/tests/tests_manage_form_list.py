import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser


FORM_PAYLOAD = {
    "name": "CRUD Test Form",
    "type": 1,
    "approval_instructions": None,
    "parent": None,
    "question_group": [
        {
            "id": None,
            "name": "household_info",
            "label": "Household Information",
            "order": 1,
            "repeatable": False,
            "repeat_text": None,
            "question": [
                {
                    "id": None,
                    "order": 1,
                    "label": "Head of Household",
                    "short_label": None,
                    "name": "head_of_household",
                    "type": "input",
                    "meta": True,
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
                    "option": [],
                }
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


@override_settings(USE_TZ=False, TEST_ENV=True)
class ManageFormListTestCase(TestCase):
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
        self.admin = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    # ─────────────────────────────────────────────
    # GET /api/v1/forms — Flat list (backward compat)
    # ─────────────────────────────────────────────

    def test_list_forms_includes_status(self):
        """GET /api/v1/forms items include status and version."""
        res = self.client.get("/api/v1/forms", **self.header)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        if data:
            self.assertIn("status", data[0])
            self.assertIn("version", data[0])

    def test_list_forms_no_auth_allowed(self):
        """GET /api/v1/forms is accessible without authentication."""
        res = self.client.get("/api/v1/forms")
        self.assertEqual(res.status_code, 200)

    # ─────────────────────────────────────────────
    # GET /api/v1/manage/forms — Paginated list
    # ─────────────────────────────────────────────

    def test_manage_list_requires_auth(self):
        """GET /api/v1/manage/forms returns 401/403 without auth."""
        res = self.client.get("/api/v1/manage/forms")
        self.assertIn(res.status_code, [401, 403])

    def test_manage_list_returns_paginated(self):
        """GET /api/v1/manage/forms returns paginated envelope."""
        res = self.client.get("/api/v1/manage/forms", **self.header)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        self.assertIn("total", data)
        self.assertIsInstance(data["data"], list)

    # ─────────────────────────────────────────────
    # GET /api/v1/manage/forms/{id} — Retrieve
    # ─────────────────────────────────────────────

    def test_get_form_includes_status(self):
        """
        GET /api/v1/manage/forms/{id} includes status, version, published_at.
        """
        create_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.get(f"/api/v1/manage/forms/{form_id}", **self.header)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("version", data)
        self.assertIn("published_at", data)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["version"], 1)

    def test_get_form_not_found(self):
        """GET /api/v1/manage/forms/{id} returns 404 for non-existent form."""
        res = self.client.get("/api/v1/manage/forms/99999", **self.header)
        self.assertEqual(res.status_code, 404)

    def test_get_form_disable_delete_in_response(self):
        """Questions with no answers return disable_delete=null."""
        create_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.get(f"/api/v1/manage/forms/{form_id}", **self.header)
        q = res.json()["question_group"][0]["question"][0]
        self.assertIsNone(q.get("disable_delete"))
