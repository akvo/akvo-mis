import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_users.models import SystemUser


FORM_PAYLOAD = {
    "name": "CRUD Test Form",
    "type": "registration",
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
class FormCRUDTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        # Reset PK sequences after seeder inserts rows with explicit IDs.
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
    # POST /api/v1/forms — Create
    # ─────────────────────────────────────────────

    def test_create_draft_form(self):
        """POST /api/v1/forms returns 201 and status=draft."""
        res = self.client.post(
            "/api/v1/forms",
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
        """POST /api/v1/forms returns 401 without auth."""
        res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
        )
        self.assertIn(res.status_code, [401, 403])

    def test_create_invalid_question_type(self):
        """POST /api/v1/forms returns 400 for unknown question type."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0]["type"] = "photo"
        res = self.client.post(
            "/api/v1/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_create_with_image_type(self):
        """POST /api/v1/forms accepts 'image' as canonical photo type."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0]["type"] = "image"
        res = self.client.post(
            "/api/v1/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form_id = res.json()["id"]
        q = Questions.objects.filter(form_id=form_id).first()
        self.assertEqual(q.type, QuestionTypes.image)

    def test_create_with_option_question(self):
        """POST /api/v1/forms with option question creates options."""
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
            "/api/v1/forms",
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
            "/api/v1/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        form_id = res.json()["id"]
        q = Questions.objects.filter(form_id=form_id).first()
        self.assertIsNotNone(q.name)
        self.assertNotEqual(q.name, "")

    # ─────────────────────────────────────────────
    # GET /api/v1/forms/{id}
    # ─────────────────────────────────────────────

    def test_get_form_includes_status(self):
        """GET /api/v1/forms/{id} includes status, version, published_at."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.get(f"/api/v1/forms/{form_id}", **self.header)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("version", data)
        self.assertIn("published_at", data)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["version"], 1)

    def test_get_form_not_found(self):
        """GET /api/v1/forms/{id} returns 404 for non-existent form."""
        res = self.client.get("/api/v1/forms/99999", **self.header)
        self.assertEqual(res.status_code, 404)

    def test_get_form_disable_delete_in_response(self):
        """Questions with no answers return disable_delete=null."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.get(f"/api/v1/forms/{form_id}", **self.header)
        q = res.json()["question_group"][0]["question"][0]
        self.assertIsNone(q.get("disable_delete"))

    # ─────────────────────────────────────────────
    # GET /api/v1/forms — List
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

    # ─────────────────────────────────────────────
    # PUT /api/v1/forms/{id} — Update draft
    # ─────────────────────────────────────────────

    def test_update_draft_form_returns_200(self):
        """PUT /api/v1/forms/{id} on a draft returns 200, updates in-place."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        updated = json.loads(json.dumps(FORM_PAYLOAD))
        updated["name"] = "Updated Name"
        res = self.client.put(
            f"/api/v1/forms/{form_id}",
            json.dumps(updated),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], form_id)
        self.assertEqual(data["name"], "Updated Name")
        self.assertEqual(data["version"], 1)
        self.assertEqual(Forms.objects.filter(name="Updated Name").count(), 1)

    def test_update_published_creates_new_version(self):
        """PUT on PUBLISHED returns 201 with new ID and version+1."""
        # Create + publish
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        self.client.post(
            f"/api/v1/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        # Now edit the published form
        updated = json.loads(json.dumps(FORM_PAYLOAD))
        updated["name"] = "Version 2"
        res = self.client.put(
            f"/api/v1/forms/{form_id}",
            json.dumps(updated),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertNotEqual(data["id"], form_id)
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["name"], "Version 2")
        # Original form must be unchanged
        original = Forms.objects.get(pk=form_id)
        self.assertEqual(original.version, 1)
        self.assertEqual(original.name, FORM_PAYLOAD["name"])

    def test_version_chain_correct(self):
        """GET /api/v1/forms/{id}/versions returns version chain."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        self.client.post(
            f"/api/v1/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        updated = json.loads(json.dumps(FORM_PAYLOAD))
        updated["name"] = "Version 2"
        v2_res = self.client.put(
            f"/api/v1/forms/{form_id}",
            json.dumps(updated),
            content_type="application/json",
            **self.header,
        )
        v2_id = v2_res.json()["id"]
        res = self.client.get(f"/api/v1/forms/{v2_id}/versions", **self.header)
        self.assertEqual(res.status_code, 200)
        versions = res.json()
        self.assertEqual(len(versions), 2)
        version_nums = [v["version"] for v in versions]
        self.assertIn(1, version_nums)
        self.assertIn(2, version_nums)

    # ─────────────────────────────────────────────
    # POST /api/v1/forms/{id}/publish
    # ─────────────────────────────────────────────

    def test_publish_form(self):
        """publish sets status=published and records published_at."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.post(
            f"/api/v1/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "published")
        self.assertIsNotNone(data["published_at"])
        self.assertEqual(data["version"], 1)

    def test_publish_already_published_returns_400(self):
        """publish on already-published form returns 400."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        self.client.post(
            f"/api/v1/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        res = self.client.post(
            f"/api/v1/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_publish_not_found(self):
        """POST /api/v1/forms/{id}/publish on non-existent form returns 404."""
        res = self.client.post(
            "/api/v1/forms/99999/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    # ─────────────────────────────────────────────
    # POST /api/v1/forms/{id}/duplicate
    # ─────────────────────────────────────────────

    def test_duplicate_form(self):
        """POST /api/v1/forms/{id}/duplicate creates a deep-copy draft."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.post(
            f"/api/v1/forms/{form_id}/duplicate",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertNotEqual(data["id"], form_id)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["version"], 1)
        self.assertIn("(Copy)", data["name"])
        # Original remains
        self.assertTrue(Forms.objects.filter(pk=form_id).exists())

    # ─────────────────────────────────────────────
    # DELETE /api/v1/forms/{id}
    # ─────────────────────────────────────────────

    def test_delete_form_without_submissions(self):
        """DELETE /api/v1/forms/{id} with no submissions returns 204."""
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.delete(
            f"/api/v1/forms/{form_id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Forms.objects.filter(pk=form_id).exists())

    def test_delete_form_not_found(self):
        """DELETE /api/v1/forms/{id} on non-existent form returns 404."""
        res = self.client.delete(
            "/api/v1/forms/99999",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    # ─────────────────────────────────────────────
    # Protection: update cannot delete answered groups/questions
    # ─────────────────────────────────────────────

    def test_update_cannot_delete_group_with_answers(self):
        """PUT removes answered group → 400 Can't delete question group."""
        from api.v1.v1_data.models import FormData, Answers
        from api.v1.v1_profile.models import Administration

        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        question = group.question_group_question.first()

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form,
            name="Test Submission",
            administration=adm,
            created_by=self.admin,
        )
        Answers.objects.create(
            data=fd,
            question=question,
            name="Test Answer",
            created_by=self.admin,
        )

        # PUT payload with the question_group list EMPTY (removes the group)
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"] = []
        res = self.client.put(
            f"/api/v1/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Can't delete", str(res.json()))

    def test_update_cannot_delete_question_with_answers(self):
        """PUT removes an answered question → 400 'Can't delete question'."""
        from api.v1.v1_data.models import FormData, Answers
        from api.v1.v1_profile.models import Administration

        # Create form with 2 questions in one group
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None,
            "order": 2,
            "label": "Age",
            "short_label": None,
            "name": "age",
            "type": "number",
            "meta": False,
            "required": False,
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
        })
        create_res = self.client.post(
            "/api/v1/forms",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        q2 = group.question_group_question.get(name="age")

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form,
            name="Test Submission",
            administration=adm,
            created_by=self.admin,
        )
        Answers.objects.create(
            data=fd,
            question=q2,
            value=25,
            created_by=self.admin,
        )

        # PUT with q2 removed from the payload
        update_payload = json.loads(json.dumps(FORM_PAYLOAD))
        # Only keep q1 (head_of_household), omit age/q2
        update_payload["question_group"][0]["question_group_id"] = group.id
        res = self.client.put(
            f"/api/v1/forms/{form_id}",
            json.dumps(update_payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Can't delete", str(res.json()))
