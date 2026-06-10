import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import FormPublishedVersion, Questions
from api.v1.v1_users.models import SystemUser


FORM_PAYLOAD = {
    "name": "Version Detail Test Form",
    "type": 1,
    "approval_instructions": None,
    "parent": None,
    "question_group": [
        {
            "id": None,
            "name": "group_one",
            "label": "Group One",
            "order": 1,
            "repeatable": False,
            "repeat_text": None,
            "question": [
                {
                    "id": None,
                    "order": 1,
                    "label": "Question One",
                    "short_label": None,
                    "name": "question_one",
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
class ManageFormVersionDetailTestCase(TestCase):
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
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        return res.json()

    def _url(self, form_id, version_id):
        return f"/api/v1/manage/forms/{form_id}/versions/{version_id}"

    # ─────────────────────────────────────────────────────────
    # GET /api/v1/manage/forms/{id}/versions/{version_id}
    # ─────────────────────────────────────────────────────────

    def test_version_detail_returns_200_with_all_fields(self):
        """Returns 200 with id, version, published_at, published_by,
        is_active, and schema for a valid published version."""
        form_id = self._create_form()
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id)

        res = self.client.get(self._url(form_id, pv.id), **self.header)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], pv.id)
        self.assertEqual(data["version"], 1)
        self.assertIn("published_at", data)
        self.assertIn("published_by", data)
        self.assertIn("is_active", data)
        self.assertIn("schema", data)

    def test_version_detail_schema_contains_question_group(self):
        """schema is a non-empty dict with a question_group list."""
        form_id = self._create_form()
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id)

        res = self.client.get(self._url(form_id, pv.id), **self.header)

        self.assertEqual(res.status_code, 200)
        schema = res.json()["schema"]
        self.assertIsInstance(schema, dict)
        self.assertIn("question_group", schema)
        self.assertIsInstance(schema["question_group"], list)
        self.assertGreater(len(schema["question_group"]), 0)

    def test_version_detail_published_by_is_admin_email(self):
        """published_by contains the email of the publishing user."""
        form_id = self._create_form()
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id)

        res = self.client.get(self._url(form_id, pv.id), **self.header)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["published_by"], self.admin.email)

    def test_version_detail_is_active_true_for_active_version(self):
        """is_active is True when the version is the currently active one."""
        form_id = self._create_form()
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id)

        res = self.client.get(self._url(form_id, pv.id), **self.header)

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["is_active"])

    def test_version_detail_is_active_false_for_pending_snapshot(self):
        """is_active is False for a snapshot created by PUT but not yet
        activated via publish.  The original active version remains True."""
        form_id = self._create_form()
        self._publish_form(form_id)

        # PUT on a published form stores a pending snapshot (v2).
        updated_payload = {**FORM_PAYLOAD, "name": "Updated Form Name"}
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(updated_payload),
            content_type="application/json",
            **self.header,
        )

        pvs = FormPublishedVersion.objects.filter(
            form_id=form_id
        ).order_by("version")
        self.assertEqual(pvs.count(), 2)
        pv_v1 = pvs.first()
        pv_v2 = pvs.last()

        # v2 is accessible but not active.
        res_v2 = self.client.get(self._url(form_id, pv_v2.id), **self.header)
        self.assertEqual(res_v2.status_code, 200)
        self.assertEqual(res_v2.json()["version"], 2)
        self.assertFalse(res_v2.json()["is_active"])

        # v1 is still the active version.
        res_v1 = self.client.get(self._url(form_id, pv_v1.id), **self.header)
        self.assertEqual(res_v1.status_code, 200)
        self.assertTrue(res_v1.json()["is_active"])

    def test_version_detail_404_for_nonexistent_form(self):
        """Returns 404 when the form does not exist."""
        res = self.client.get(self._url(99999, 99999), **self.header)

        self.assertEqual(res.status_code, 404)

    def test_version_detail_404_for_nonexistent_version(self):
        """Returns 404 when version_id does not exist for the form."""
        form_id = self._create_form()
        self._publish_form(form_id)

        res = self.client.get(self._url(form_id, 99999), **self.header)

        self.assertEqual(res.status_code, 404)

    def test_version_detail_404_version_from_different_form(self):
        """Returns 404 when version_id belongs to a different form,
        even if it exists in the database."""
        form_a_id = self._create_form()
        form_b_id = self._create_form()
        self._publish_form(form_a_id)
        self._publish_form(form_b_id)

        pv_b = FormPublishedVersion.objects.get(form_id=form_b_id)

        # Access form_a/versions/{pv_b.id} — version belongs to form_b.
        res = self.client.get(self._url(form_a_id, pv_b.id), **self.header)

        self.assertEqual(res.status_code, 404)

    def test_version_detail_requires_authentication(self):
        """Returns 401 when no Authorization header is provided."""
        form_id = self._create_form()
        self._publish_form(form_id)
        pv = FormPublishedVersion.objects.get(form_id=form_id)

        res = self.client.get(self._url(form_id, pv.id))

        self.assertEqual(res.status_code, 401)

    def test_version_detail_any_version_retrievable_by_id(self):
        """Both v1 and v2 are independently retrievable with correct version
        numbers after two full publish cycles."""
        form_id = self._create_form()
        self._publish_form(form_id)

        # Create v2: PUT (pending snapshot) then publish (activates it).
        updated_payload = {**FORM_PAYLOAD, "name": "Updated Form for v2"}
        self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(updated_payload),
            content_type="application/json",
            **self.header,
        )
        self._publish_form(form_id)

        pvs = list(
            FormPublishedVersion.objects.filter(
                form_id=form_id
            ).order_by("version")
        )
        self.assertEqual(len(pvs), 2)

        res_v1 = self.client.get(
            self._url(form_id, pvs[0].id), **self.header
        )
        self.assertEqual(res_v1.status_code, 200)
        self.assertEqual(res_v1.json()["version"], 1)

        res_v2 = self.client.get(
            self._url(form_id, pvs[1].id), **self.header
        )
        self.assertEqual(res_v2.status_code, 200)
        self.assertEqual(res_v2.json()["version"], 2)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ActivateSequenceSyncTestCase(TestCase):
    """Tests for the PK-sequence sync guard in restore_from_snapshot.

    The form editor saves questions with JS timestamp IDs directly into
    the question table, leaving the PostgreSQL sequence far behind.
    When a snapshot contains a question ID that is absent from the DB,
    restore_from_snapshot must INSERT a fresh row.  Without the sequence
    sync the auto-generated PK collides with an existing small-integer
    row from seeded data.
    """

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
        res = self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.header = {
            "HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"
        }

    def _create_and_publish(self):
        form_res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(form_res.status_code, 201)
        form_id = form_res.json()["id"]
        pub_res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(pub_res.status_code, 200)
        return form_id

    def test_activate_succeeds_when_snapshot_has_editor_generated_id(self):
        """activate returns 200 when a snapshot question ID is an editor-
        generated timestamp not present in the DB and the PK sequence
        is wound back to a value that would collide without the guard."""
        form_id = self._create_and_publish()
        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)

        # Replace the real question PK in the snapshot with a JS-timestamp
        # style ID that does not exist in the question table — this is what
        # happens in production when the editor generates its own IDs.
        fake_editor_id = 1780000000000
        schema = v1.schema
        schema["question_group"][0]["question"][0]["id"] = fake_editor_id
        FormPublishedVersion.objects.filter(id=v1.id).update(schema=schema)

        # Wind the sequence back to (real_q_id - 1) so its next value
        # equals an existing PK — guaranteed IntegrityError without the fix.
        real_q_id = Questions.objects.filter(form_id=form_id).first().id
        with connection.cursor() as cur:
            cur.execute(
                "SELECT setval("
                "pg_get_serial_sequence('question', 'id'), %s)",
                [real_q_id - 1],
            )

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )

        self.assertEqual(res.status_code, 200)
        q_names = {
            q["name"]
            for g in res.json()["question_group"]
            for q in g["question"]
        }
        self.assertIn("question_one", q_names)

    def test_activate_new_question_id_does_not_collide_after_sync(self):
        """The fresh row created for an absent snapshot question gets a PK
        strictly above all existing rows (sequence was synced to MAX)."""
        form_id = self._create_and_publish()
        v1 = FormPublishedVersion.objects.get(form_id=form_id, version=1)

        fake_editor_id = 1780000000001
        schema = v1.schema
        schema["question_group"][0]["question"][0]["id"] = fake_editor_id
        FormPublishedVersion.objects.filter(id=v1.id).update(schema=schema)

        # Use objects_with_deleted to capture the true max PK including
        # any soft-deleted rows, so the baseline is the absolute ceiling.
        max_id_before = Questions.objects_with_deleted.order_by(
            "-id"
        ).values_list("id", flat=True).first()

        real_q_id = Questions.objects.filter(form_id=form_id).first().id
        with connection.cursor() as cur:
            cur.execute(
                "SELECT setval("
                "pg_get_serial_sequence('question', 'id'), %s)",
                [real_q_id - 1],
            )

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/activate/{v1.id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)

        new_q = Questions.objects.filter(
            form_id=form_id, name="question_one"
        ).first()
        self.assertIsNotNone(new_q)
        self.assertGreater(new_q.id, max_id_before)
