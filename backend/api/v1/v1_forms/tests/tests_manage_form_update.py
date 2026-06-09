import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
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
class ManageFormUpdateTestCase(TestCase):
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
        self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )

    # ─────────────────────────────────────────────
    # PUT /api/v1/manage/forms/{id} — Update draft
    # ─────────────────────────────────────────────

    def test_update_draft_form_returns_200(self):
        """PUT on a draft returns 200 and updates in-place."""
        form_id = self._create_form()
        updated = json.loads(json.dumps(FORM_PAYLOAD))
        updated["name"] = "Updated Name"
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
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

    def test_update_partial_payload_keeps_existing_fields(self):
        """PUT with only question_group preserves name and type."""
        form_id = self._create_form()
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"question_group": FORM_PAYLOAD["question_group"]}),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], FORM_PAYLOAD["name"])

    # ─────────────────────────────────────────────
    # Question add / edit / delete (identified by id)
    # ─────────────────────────────────────────────

    def test_update_add_question(self):
        """id=null in payload creates a new question in the group."""
        form_id = self._create_form()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        existing_q = group["question"][0]

        payload = {
            "question_group": [{
                "id": group["id"],
                "name": group["name"],
                "label": group["label"],
                "order": group["order"],
                "repeatable": group["repeatable"],
                "repeat_text": group["repeat_text"],
                "question": [
                    {**existing_q, "option": []},
                    {
                        "id": None, "order": 2, "label": "Age",
                        "short_label": None, "name": "age",
                        "type": "number", "meta": False, "required": False,
                        "rule": None, "dependency": None,
                        "dependency_rule": "AND", "api": None,
                        "extra": None, "tooltip": None, "fn": None,
                        "pre": None, "display_only": False, "option": [],
                    },
                ],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        questions = res.json()["question_group"][0]["question"]
        self.assertEqual(len(questions), 2)
        self.assertIn("Age", {q["label"] for q in questions})

    def test_update_edit_question(self):
        """Existing question id in payload updates its fields in-place."""
        form_id = self._create_form()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        existing_q = group["question"][0]

        payload = {
            "question_group": [{
                "id": group["id"],
                "name": group["name"],
                "label": group["label"],
                "order": group["order"],
                "repeatable": group["repeatable"],
                "repeat_text": group["repeat_text"],
                "question": [
                    {**existing_q, "label": "Full Name", "option": []}
                ],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        q = res.json()["question_group"][0]["question"][0]
        self.assertEqual(q["id"], existing_q["id"])
        self.assertEqual(q["label"], "Full Name")

    def test_update_delete_question_without_answers(self):
        """Question absent from payload (no answers) is deleted."""
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
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        self.assertEqual(len(group["question"]), 2)
        q1 = group["question"][0]

        # PUT with only q1 — q2 absent → deleted
        update = {
            "question_group": [{
                "id": group["id"],
                "name": group["name"],
                "label": group["label"],
                "order": group["order"],
                "repeatable": group["repeatable"],
                "repeat_text": group["repeat_text"],
                "question": [{**q1, "option": []}],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(update),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        questions = res.json()["question_group"][0]["question"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["id"], q1["id"])

    # ─────────────────────────────────────────────
    # Option add / edit / delete (full replace per question)
    #
    # Options are wiped and recreated on every PUT — the entire
    # `option` array in the payload replaces whatever was stored.
    # ─────────────────────────────────────────────

    def _create_form_with_option_question(self):
        """Helper: create a form whose first question has two options."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"][0].update({
            "type": "option",
            "option": [
                {"order": 1, "label": "Yes", "value": "yes",
                 "other": False, "color": None},
                {"order": 2, "label": "No", "value": "no",
                 "other": False, "color": None},
            ],
        })
        return self._create_form(payload)

    def test_update_add_option(self):
        """Adding an option: PUT with an extra item in the option array."""
        form_id = self._create_form_with_option_question()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        q = group["question"][0]

        payload = {
            "question_group": [{
                **group,
                "question": [{
                    **q,
                    "option": [
                        {"order": 1, "label": "Yes", "value": "yes",
                         "other": False, "color": None},
                        {"order": 2, "label": "No", "value": "no",
                         "other": False, "color": None},
                        {"order": 3, "label": "Maybe", "value": "maybe",
                         "other": False, "color": None},
                    ],
                }],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        options = res.json()["question_group"][0]["question"][0]["option"]
        self.assertEqual(len(options), 3)
        self.assertIn("Maybe", {o["label"] for o in options})

    def test_update_edit_option(self):
        """Editing an option: PUT with the same values but changed label."""
        form_id = self._create_form_with_option_question()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        q = group["question"][0]

        payload = {
            "question_group": [{
                **group,
                "question": [{
                    **q,
                    "option": [
                        {"order": 1, "label": "Agree", "value": "yes",
                         "other": False, "color": None},
                        {"order": 2, "label": "Disagree", "value": "no",
                         "other": False, "color": None},
                    ],
                }],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        options = res.json()["question_group"][0]["question"][0]["option"]
        labels = {o["label"] for o in options}
        self.assertIn("Agree", labels)
        self.assertNotIn("Yes", labels)

    def test_update_delete_option(self):
        """Removing an option: PUT with a shorter option array."""
        form_id = self._create_form_with_option_question()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        q = group["question"][0]

        # Keep only one option
        payload = {
            "question_group": [{
                **group,
                "question": [{
                    **q,
                    "option": [
                        {"order": 1, "label": "Yes", "value": "yes",
                         "other": False, "color": None},
                    ],
                }],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        options = res.json()["question_group"][0]["question"][0]["option"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["label"], "Yes")

    def test_update_with_nonexistent_ids_creates_new(self):
        """PUT with group/question IDs that don't exist in the DB (e.g.
        editor-generated timestamp IDs) must not 500 — they are treated as
        new rows."""
        form_id = self._create_form()
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({
                "question_group": [{
                    "id": 9999999999001,
                    "name": "new_group",
                    "label": "New Group",
                    "order": 1,
                    "repeatable": False,
                    "repeat_text": None,
                    "question": [{
                        "id": 9999999999002,
                        "order": 1,
                        "label": "New Question",
                        "short_label": None,
                        "name": "new_question",
                        "type": "input",
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
                    }],
                }],
            }),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        groups = res.json()["question_group"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["question"][0]["label"], "New Question")

    def test_update_published_auto_creates_version(self):
        """PUT on PUBLISHED form creates a snapshot (latest_version advances)
        but active version stays at 1 until explicitly activated."""
        form_id = self._create_form()
        self._publish_form(form_id)
        updated = json.loads(json.dumps(FORM_PAYLOAD))
        updated["name"] = "Updated Published Form"
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(updated),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], form_id)
        self.assertEqual(data["name"], "Updated Published Form")
        self.assertEqual(data["version"], 1)        # active stays at v1
        self.assertEqual(data["latest_version"], 2)  # snapshot created
        self.assertEqual(data["status"], "published")

    def test_update_published_does_not_change_active_version(self):
        """PUT must not overwrite an explicitly activated version."""
        from api.v1.v1_forms.models import FormPublishedVersion
        form_id = self._create_form()
        self._publish_form(form_id)  # v1, active=v1
        # PUT twice — creates v2, v3
        for i in range(2):
            self.client.put(
                f"/api/v1/manage/forms/{form_id}",
                json.dumps({"name": f"edit {i}"}),
                content_type="application/json",
                **self.header,
            )
        from api.v1.v1_forms.models import Forms
        form = Forms.objects.get(pk=form_id)
        # active must still be v1
        self.assertEqual(form.active_version.version, 1)
        self.assertEqual(form.version, 1)
        # but three snapshots exist
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 3
        )

    def test_update_draft_keeps_version(self):
        """PUT on DRAFT form keeps version at 1."""
        form_id = self._create_form()
        updated = json.loads(json.dumps(FORM_PAYLOAD))
        updated["name"] = "Updated Draft Form"
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(updated),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], form_id)
        self.assertEqual(data["version"], 1)

    def test_update_published_in_place_real_ids(self):
        """PUT on PUBLISHED with real GET response IDs updates in-place."""
        form_id = self._create_form()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        self._publish_form(form_id)
        group = detail["question_group"][0]
        question = group["question"][0]
        payload = {
            "name": "Updated with real IDs",
            "question_group": [{
                "id": group["id"],
                "name": group["name"],
                "label": group["label"],
                "order": group["order"],
                "repeatable": group["repeatable"],
                "repeat_text": group["repeat_text"],
                "question": [{
                    **question,
                    "label": "Updated Label",
                    "option": [],
                }],
            }],
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], form_id)
        self.assertEqual(data["version"], 1)        # active stays at v1
        self.assertEqual(data["latest_version"], 2)  # new snapshot created
        q = data["question_group"][0]["question"][0]
        self.assertEqual(q["label"], "Updated Label")

    def test_update_form_level_translation_fields(self):
        """PUT updates languages, default_language, translations on form."""
        form_id = self._create_form()
        payload = {
            "languages": ["en", "fr"],
            "default_language": "en",
            "translations": [{"language": "fr", "name": "Formulaire CRUD"}],
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["languages"], ["en", "fr"])
        self.assertEqual(data["defaultLanguage"], "en")
        self.assertEqual(
            data["translations"],
            [{"language": "fr", "name": "Formulaire CRUD"}],
        )
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.languages, ["en", "fr"])
        self.assertEqual(form.default_language, "en")

    def test_update_group_and_question_translations(self):
        """PUT stores translations on group and question."""
        form_id = self._create_form()
        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        group = detail["question_group"][0]
        q = group["question"][0]

        payload = {
            "question_group": [{
                "id": group["id"],
                "name": group["name"],
                "label": group["label"],
                "order": group["order"],
                "repeatable": group["repeatable"],
                "repeat_text": group["repeat_text"],
                "translations": [{"language": "id", "name": "Grup Info"}],
                "question": [{
                    **q,
                    "translations": [{"language": "id", "name": "Kepala KK"}],
                    "option": [],
                }],
            }]
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        grp = res.json()["question_group"][0]
        self.assertEqual(
            grp["translations"], [{"language": "id", "name": "Grup Info"}]
        )
        self.assertEqual(
            grp["question"][0]["translations"],
            [{"language": "id", "name": "Kepala KK"}],
        )

    # ─────────────────────────────────────────────
    # Audit fields
    # ─────────────────────────────────────────────

    def test_draft_put_sets_updated_by(self):
        """PUT on draft sets updated_by and updated on the form."""
        create_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        form = Forms.objects.get(pk=form_id)
        self.assertIsNone(form.updated_by)
        self.assertIsNone(form.updated)

        put_res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "Updated Name"}),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(put_res.status_code, 200)
        form.refresh_from_db()
        self.assertEqual(form.updated_by, self.admin)
        self.assertIsNotNone(form.updated)

    def test_draft_put_response_includes_audit_fields(self):
        """PUT response includes all four audit fields."""
        create_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "Updated Name"}),
            content_type="application/json",
            **self.header,
        )
        data = res.json()
        self.assertIn("created_by", data)
        self.assertIn("updated_by", data)
        self.assertIn("created", data)
        self.assertIn("updated", data)
        self.assertEqual(data["updated_by"], self.admin.email)
        self.assertIsNotNone(data["updated"])

    def test_published_put_sets_updated_by(self):
        """
        PUT on published form (snapshot path) also sets updated_by/updated.
        """
        create_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        form_id = create_res.json()["id"]
        self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        form = Forms.objects.get(pk=form_id)
        initial_updated = form.updated

        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({"name": "New Snapshot Name"}),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        form.refresh_from_db()
        self.assertEqual(form.updated_by, self.admin)
        self.assertIsNotNone(form.updated)
        # updated timestamp must have changed
        self.assertNotEqual(form.updated, initial_updated)
