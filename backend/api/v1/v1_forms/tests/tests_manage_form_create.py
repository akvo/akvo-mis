import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_forms.constants import QuestionTypes, FormTypes
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
class ManageFormCreateTestCase(TestCase):
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
    # POST /api/v1/manage/forms — Create
    # ─────────────────────────────────────────────

    def test_create_draft_form(self):
        """POST /api/v1/manage/forms returns 201 and status=draft."""
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["name"], "CRUD Test Form")
        self.assertIsNone(data["published_at"])
        self.assertIn("question_group", data)
        self.assertEqual(len(data["question_group"]), 1)

    def test_create_requires_auth(self):
        """POST /api/v1/manage/forms returns 401/403 without auth."""
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
        )
        self.assertIn(res.status_code, [401, 403])

    def test_create_missing_name_returns_400(self):
        """POST /api/v1/manage/forms without name returns 400."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        del payload["name"]
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_create_invalid_question_type(self):
        """POST /api/v1/manage/forms returns 400 for unknown question type."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0]["type"] = "unknown_type"
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_create_with_image_type(self):
        """
        POST /api/v1/manage/forms accepts 'image' as canonical photo type.
        """
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0]["type"] = "image"
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form_id = res.json()["id"]
        q = Questions.objects.filter(form_id=form_id).first()
        self.assertEqual(q.type, QuestionTypes.image)

    def test_create_with_option_question(self):
        """POST /api/v1/manage/forms with option question creates options."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0].update({
            "type": "option",
            "option": [
                {
                    "order": 1, "label": "Yes", "value": "yes",
                    "other": False, "color": None,
                },
                {
                    "order": 2, "label": "No", "value": "no",
                    "other": False, "color": None,
                },
            ],
        })
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form_id = res.json()["id"]
        q = Questions.objects.filter(form_id=form_id).first()
        self.assertEqual(q.options.count(), 2)

    def test_create_name_autogenerated_if_missing(self):
        """Question without 'name' gets a slugified name from label."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0]["name"] = None
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form_id = res.json()["id"]
        q = Questions.objects.filter(form_id=form_id).first()
        self.assertIsNotNone(q.name)
        self.assertNotEqual(q.name, "")

    def test_create_type_as_integer(self):
        """POST /api/v1/manage/forms accepts type as integer."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["type"] = 1
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form = Forms.objects.get(pk=res.json()["id"])
        self.assertEqual(form.type, FormTypes.registration)

    def test_create_type_defaults_to_registration_without_parent(self):
        """POST without type and without parent → registration."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        del payload["type"]
        payload["parent"] = None
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form = Forms.objects.get(pk=res.json()["id"])
        self.assertEqual(form.type, FormTypes.registration)

    def test_create_type_inferred_as_monitoring_with_parent(self):
        """POST without type but with a parent → monitoring."""
        # Create and publish a registration form to use as parent
        reg_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        reg_id = reg_res.json()["id"]
        self.client.post(
            f"/api/v1/manage/forms/{reg_id}/publish",
            content_type="application/json",
            **self.header,
        )

        payload = json.loads(json.dumps(FORM_PAYLOAD))
        del payload["type"]
        payload["parent"] = reg_id
        payload["name"] = "Monitoring Form"
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form = Forms.objects.get(pk=res.json()["id"])
        self.assertEqual(form.type, FormTypes.monitoring)
