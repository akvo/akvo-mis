import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import FormPublishedVersion, Forms
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
class ManageFormPublishTestCase(TestCase):
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

    def _create_form(self, payload=None):
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload or FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        return res.json()["id"]

    def _publish_form(self, form_id):
        return self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )

    # ─────────────────────────────────────────────
    # POST /api/v1/manage/forms/{id}/publish
    # ─────────────────────────────────────────────

    def test_publish_form(self):
        """Publish sets status=published, records published_at, and creates
        a FormPublishedVersion snapshot."""
        form_id = self._create_form()
        res = self._publish_form(form_id)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "published")
        self.assertIsNotNone(data["published_at"])
        self.assertEqual(data["version"], 1)
        self.assertIsNotNone(data.get("active_version_id"))

    def test_publish_not_found(self):
        """Publish on non-existent form returns 404."""
        res = self.client.post(
            "/api/v1/manage/forms/99999/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    def test_publish_creates_snapshot(self):
        """POST publish creates a FormPublishedVersion and sets active_version.
        """
        form_id = self._create_form()
        res = self._publish_form(form_id)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 1
        )
        pv = FormPublishedVersion.objects.get(form_id=form_id)
        self.assertEqual(pv.version, 1)
        self.assertIn("question_group", pv.schema)
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.active_version_id, pv.id)

    def test_publish_snapshot_excludes_soft_deleted(self):
        """Snapshot captures only active questions (deleted_at is null)."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None, "order": 2, "label": "To Delete",
            "short_label": None, "name": "to_delete", "type": "input",
            "meta": False, "required": False, "rule": None,
            "dependency": None, "dependency_rule": "AND",
            "api": None, "extra": None, "tooltip": None,
            "fn": None, "pre": None, "display_only": False, "option": [],
        })
        form_id = self._create_form(payload)
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        q2 = group.question_group_question.get(name="to_delete")
        q2.soft_delete()

        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id)
        snapshot_q_names = [
            q["name"]
            for g in pv.schema["question_group"]
            for q in g["question"]
        ]
        self.assertIn("head_of_household", snapshot_q_names)
        self.assertNotIn("to_delete", snapshot_q_names)

    def test_publish_activates_pending_snapshot_not_creates_new(self):
        """PUT on a published form stores a snapshot (v2); explicit publish
        activates v2 — no new snapshot is created."""
        form_id = self._create_form()
        self._publish_form(form_id)         # v1 (active=v1)
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "Edited After Publish"}),
            content_type="application/json",
            **self.header,
        )                                   # store_version_snapshot → v2
        res = self._publish_form(form_id)   # activate v2 (no new snapshot)
        self.assertEqual(res.status_code, 200)
        # Only 2 snapshots: v1 (first publish) + v2 (PUT)
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 2
        )
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.active_version.version, 2)

    # ─────────────────────────────────────────────
    # POST /api/v1/manage/forms/{id}/duplicate
    # ─────────────────────────────────────────────

    def test_duplicate_form(self):
        """Duplicate creates a deep-copy draft."""
        form_id = self._create_form()
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/duplicate",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertNotEqual(data["id"], form_id)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["version"], 1)
        self.assertIn("(Copy)", data["name"])
        self.assertTrue(Forms.objects.filter(pk=form_id).exists())

    # ─────────────────────────────────────────────
    # GET /api/v1/manage/forms/{id}/versions
    # ─────────────────────────────────────────────

    def test_versions_empty_for_draft(self):
        """GET versions on a draft form returns an empty list."""
        form_id = self._create_form()
        res = self.client.get(
            f"/api/v1/manage/forms/{form_id}/versions", **self.header
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_versions_returns_published_versions(self):
        """GET versions returns FormPublishedVersion list with is_active."""
        form_id = self._create_form()
        self._publish_form(form_id)
        res = self.client.get(
            f"/api/v1/manage/forms/{form_id}/versions", **self.header
        )
        versions = res.json()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["version"], 1)
        self.assertTrue(versions[0]["is_active"])
        self.assertIn("published_at", versions[0])

    # ─────────────────────────────────────────────
    # POST /api/v1/manage/forms/{id}/activate/{version_id}
    # ─────────────────────────────────────────────

    def test_activate_changes_active_version(self):
        """POST activate/{version_id} rolls back active_version."""
        form_id = self._create_form()
        self._publish_form(form_id)          # v1 (active=v1)
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "v2 edit"}),
            content_type="application/json",
            **self.header,
        )                                    # store_version_snapshot → v2
        self._publish_form(form_id)          # activates v2 (no new snapshot)
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.active_version.version, 2)

        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        form.refresh_from_db()
        self.assertEqual(form.active_version_id, v1.id)
        self.assertEqual(res.json().get("active_version_id"), v1.id)

    def test_activate_restores_soft_deleted_questions(self):
        """Rolling back to v1 restores questions that were soft-deleted after
        v1 was published."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None, "order": 2, "label": "Age",
            "short_label": None, "name": "age", "type": "number",
            "meta": False, "required": False, "rule": None,
            "dependency": None, "dependency_rule": "AND",
            "api": None, "extra": None, "tooltip": None,
            "fn": None, "pre": None, "display_only": False, "option": [],
        })
        form_id = self._create_form(payload)
        self._publish_form(form_id)   # v1: head_of_household + age
        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)

        # Remove "age" via PUT with allow_delete=true → auto-creates v2
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        grp = detail["question_group"][0]
        q1 = next(
            q for q in grp["question"]
            if q["name"] == "head_of_household"
        )
        self.client.put(
            f"/api/v1/manage/forms/{form_id}?allow_delete=true",
            json.dumps({
                "question_group": [{
                    "id": grp["id"],
                    "name": grp["name"],
                    "label": grp["label"],
                    "order": grp["order"],
                    "repeatable": grp["repeatable"],
                    "repeat_text": grp["repeat_text"],
                    "question": [{**q1, "option": []}],
                }],
            }),
            content_type="application/json",
            **self.header,
        )
        # Activate v2 (age removed) so GET reflects the new active state.
        self._publish_form(form_id)
        # Verify "age" is gone in current active state
        current = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        self.assertEqual(
            len(current["question_group"][0]["question"]), 1
        )

        # Rollback to v1
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        questions = res.json()["question_group"][0]["question"]
        self.assertEqual(len(questions), 2)
        q_names = {q["name"] for q in questions}
        self.assertIn("head_of_household", q_names)
        self.assertIn("age", q_names)

    def test_activate_soft_deletes_questions_added_after_version(self):
        """Rolling back to v1 soft-deletes questions that were added after
        v1 was published."""
        form_id = self._create_form()
        self._publish_form(form_id)   # v1: head_of_household only
        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)

        # Add a new question via PUT → auto-creates v2
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        grp = detail["question_group"][0]
        q1 = grp["question"][0]
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({
                "question_group": [{
                    "id": grp["id"],
                    "name": grp["name"],
                    "label": grp["label"],
                    "order": grp["order"],
                    "repeatable": grp["repeatable"],
                    "repeat_text": grp["repeat_text"],
                    "question": [
                        {**q1, "option": []},
                        {
                            "id": None, "order": 2, "label": "New Field",
                            "short_label": None, "name": "new_field",
                            "type": "input", "meta": False, "required": False,
                            "rule": None, "dependency": None,
                            "dependency_rule": "AND", "api": None,
                            "extra": None, "tooltip": None,
                            "fn": None, "pre": None, "display_only": False,
                            "option": [],
                        },
                    ],
                }],
            }),
            content_type="application/json",
            **self.header,
        )
        # Activate v2 (new_field added) so GET reflects the new active state.
        self._publish_form(form_id)
        # Verify "new_field" is present in current active state
        current = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        self.assertEqual(
            len(current["question_group"][0]["question"]), 2
        )

        # Rollback to v1
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        questions = res.json()["question_group"][0]["question"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["name"], "head_of_household")

    def test_activate_restores_form_name(self):
        """Rolling back to v1 restores the form name that was captured in the
        v1 snapshot, even if the form was renamed after that."""
        form_id = self._create_form()         # name = "CRUD Test Form"
        self._publish_form(form_id)           # v1 snapshot captures this name
        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)

        # Rename via PUT → creates v2 snapshot, then publish to activate it.
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "Renamed Form"}),
            content_type="application/json",
            **self.header,
        )
        self._publish_form(form_id)   # activate v2 (name="Renamed Form")
        current = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        self.assertEqual(current["name"], "Renamed Form")

        # Activate v1 — should restore name to "CRUD Test Form"
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "CRUD Test Form")

    def test_snapshot_captures_form_metadata(self):
        """Schema includes name and approval_instructions."""
        form_id = self._create_form()
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id, version=1)
        self.assertEqual(pv.schema.get("name"), "CRUD Test Form")
        self.assertIn("approval_instructions", pv.schema)
        self.assertIn("question_group", pv.schema)

    def test_retrieve_returns_active_version_not_latest(self):
        """
        GET /manage/forms/{id} serves active_version snapshot, not latest.
        """
        form_id = self._create_form()
        self._publish_form(form_id)   # v1 active
        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)

        # Create v2 and v3 via PUT + publish
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "Version 2 Name"}),
            content_type="application/json",
            **self.header,
        )
        self._publish_form(form_id)   # activates v2
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "Version 3 Name"}),
            content_type="application/json",
            **self.header,
        )
        self._publish_form(form_id)   # activates v3

        # Roll back to v1
        self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.active_version_id, v1.id)

        # GET must return the v1 snapshot (name = "CRUD Test Form"),
        # not the v3 snapshot (name = "Version 3 Name")
        res = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "CRUD Test Form")
        self.assertEqual(res.json()["active_version_id"], v1.id)

    def test_activate_wrong_form_returns_404(self):
        """POST activate with a version from a different form returns 404."""
        form1_id = self._create_form()
        form2_id = self._create_form()
        self._publish_form(form1_id)
        self._publish_form(form2_id)
        v_form1 = FormPublishedVersion.objects.get(form_id=form1_id, version=1)

        res = self.client.post(
            f"/api/v1/manage/forms/{form2_id}/activate/{v_form1.id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    def test_snapshot_includes_translation_fields(self):
        """Publish captures languages, default_language, translations in schema
        at form, group, and question levels."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload.update({
            "languages": ["en", "id"],
            "default_language": "en",
            "translations": [{"language": "id", "name": "Formulir CRUD"}],
        })
        payload["question_group"][0]["translations"] = [
            {"language": "id", "name": "Info Rumah Tangga"}
        ]
        payload["question_group"][0]["question"][0]["translations"] = [
            {"language": "id", "name": "Kepala Keluarga"}
        ]
        form_id = self._create_form(payload)
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id, version=1)
        schema = pv.schema
        self.assertEqual(schema.get("languages"), ["en", "id"])
        self.assertEqual(schema.get("default_language"), "en")
        self.assertEqual(
            schema.get("translations"),
            [{"language": "id", "name": "Formulir CRUD"}],
        )
        grp = schema["question_group"][0]
        self.assertEqual(
            grp.get("translations"),
            [{"language": "id", "name": "Info Rumah Tangga"}],
        )
        self.assertEqual(
            grp["question"][0].get("translations"),
            [{"language": "id", "name": "Kepala Keluarga"}],
        )

    def test_duplicate_preserves_translation_fields(self):
        """Duplicate deep-copies languages, default_language, and translations
        at form, group, and question levels."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload.update({
            "languages": ["en", "id"],
            "default_language": "en",
            "translations": [{"language": "id", "name": "Formulir CRUD"}],
        })
        payload["question_group"][0]["translations"] = [
            {"language": "id", "name": "Info Rumah Tangga"}
        ]
        payload["question_group"][0]["question"][0]["translations"] = [
            {"language": "id", "name": "Kepala Keluarga"}
        ]
        form_id = self._create_form(payload)
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/duplicate",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        dup = res.json()
        self.assertNotEqual(dup["id"], form_id)
        self.assertEqual(dup["languages"], ["en", "id"])
        self.assertEqual(dup["defaultLanguage"], "en")
        self.assertEqual(
            dup["translations"],
            [{"language": "id", "name": "Formulir CRUD"}],
        )
        grp = dup["question_group"][0]
        self.assertEqual(
            grp["translations"],
            [{"language": "id", "name": "Info Rumah Tangga"}],
        )
        self.assertEqual(
            grp["question"][0]["translations"],
            [{"language": "id", "name": "Kepala Keluarga"}],
        )

    def test_duplicate_sets_created_by(self):
        """
        Duplicate sets created_by to calling user; updated_by/updated null.
        """
        form_id = self._create_form()
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/duplicate",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        dup = Forms.objects.get(pk=res.json()["id"])
        self.assertEqual(dup.created_by, self.admin)
        self.assertIsNone(dup.updated_by)
        self.assertIsNone(dup.updated)
        self.assertIsNotNone(dup.created)
