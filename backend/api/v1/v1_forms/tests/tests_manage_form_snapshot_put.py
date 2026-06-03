import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import FormPublishedVersion, Forms, Questions
from api.v1.v1_users.models import SystemUser


FORM_PAYLOAD = {
    "name": "Snapshot Test Form",
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
class SnapshotOnlyPutTestCase(TestCase):
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

    def _publish(self, form_id):
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        return res.json()

    def _unpublish(self, form_id):
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/unpublish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        return res.json()

    def _put(self, form_id, payload):
        return self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )

    def _get(self, form_id):
        return self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        )

    # ─────────────────────────────────────────────
    # PUT on published form — snapshot-only path
    # ─────────────────────────────────────────────

    def test_update_published_does_not_touch_live_rows(self):
        """PUT on a published form must NOT modify live QuestionGroup or
        Questions rows. It only creates a FormPublishedVersion snapshot."""
        form_id = self._create_form()
        detail = self._get(form_id).json()
        q_id = detail["question_group"][0]["question"][0]["id"]

        self._publish(form_id)

        q_before = Questions.objects.get(pk=q_id)
        self.assertEqual(q_before.label, "Head of Household")

        group = detail["question_group"][0]
        q = group["question"][0]
        self._put(form_id, {
            "name": "New Name",
            "question_group": [{
                **group,
                "question": [{**q, "label": "Updated Label", "option": []}],
            }],
        })

        # Live question row must be unchanged
        q_after = Questions.objects.get(pk=q_id)
        self.assertEqual(
            q_after.label,
            "Head of Household",
            "PUT on published must not modify live question rows",
        )
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 2
        )

    def test_update_published_retrieve_returns_snapshot_data(self):
        """GET on a published form must return data from the latest snapshot,
        not from stale live rows."""
        form_id = self._create_form()
        detail = self._get(form_id).json()
        self._publish(form_id)

        group = detail["question_group"][0]
        q = group["question"][0]
        self._put(form_id, {
            "name": "Snapshot Name",
            "question_group": [{
                **group,
                "question": [{**q, "label": "Snapshot Label", "option": []}],
            }],
        })

        data = self._get(form_id).json()
        self.assertEqual(data["name"], "Snapshot Name")
        self.assertEqual(
            data["question_group"][0]["question"][0]["label"],
            "Snapshot Label",
        )

    def test_update_published_name_only_inherits_question_group(self):
        """PUT with only a name change (no question_group key) inherits
        question_group from the active version's snapshot."""
        form_id = self._create_form()
        self._publish(form_id)

        self._put(form_id, {"name": "Renamed Only"})

        data = self._get(form_id).json()
        self.assertEqual(data["name"], "Renamed Only")
        self.assertEqual(len(data["question_group"]), 1)
        self.assertEqual(
            data["question_group"][0]["question"][0]["name"],
            "head_of_household",
        )

    def test_update_published_response_has_correct_versions(self):
        """PUT response: version=1 (active unchanged), latest_version=2."""
        form_id = self._create_form()
        self._publish(form_id)

        res = self._put(form_id, {"name": "Updated"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["latest_version"], 2)
        self.assertEqual(data["status"], "published")
        self.assertEqual(data["name"], "Updated")

    # ─────────────────────────────────────────────
    # publish on already-published form
    # ─────────────────────────────────────────────

    def test_publish_already_published_activates_latest_not_creates_new(self):
        """Explicit publish on an already-published form activates the latest
        existing snapshot — no new snapshot is created."""
        form_id = self._create_form()
        self._publish(form_id)                          # v1 (active=v1)
        self._put(form_id, {"name": "Pending Edit"})   # v2 snapshot
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 2
        )

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 2,
            "Publish on already-published must not create new snapshot",
        )
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.active_version.version, 2)

    def test_publish_already_active_is_noop(self):
        """Publish when latest IS already active: count unchanged, v1 stays."""
        form_id = self._create_form()
        self._publish(form_id)   # v1, active=v1, no pending PUTs

        self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )

        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 1
        )
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.active_version.version, 1)

    # ─────────────────────────────────────────────
    # published_at guard
    # ─────────────────────────────────────────────

    def test_republish_after_unpublish_does_not_overwrite_published_at(self):
        """Re-publishing after unpublish must not overwrite published_at.
        create_published_version guards on form.published_at is None."""
        form_id = self._create_form()
        self._publish(form_id)
        original_published_at = Forms.objects.get(pk=form_id).published_at
        self.assertIsNotNone(original_published_at)

        self._unpublish(form_id)
        self._publish(form_id)   # re-publish (draft → published)

        form_after = Forms.objects.get(pk=form_id)
        self.assertEqual(
            form_after.published_at,
            original_published_at,
            "published_at must not be overwritten on re-publish",
        )

    # ─────────────────────────────────────────────
    # Unpublish action
    # ─────────────────────────────────────────────

    def test_unpublish_sets_draft(self):
        """POST .../unpublish on a published form sets status=draft."""
        form_id = self._create_form()
        self._publish(form_id)

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/unpublish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "draft")
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.status, 1)   # FormStatus.draft

    def test_unpublish_already_draft_returns_400(self):
        """POST .../unpublish on a draft form returns 400."""
        form_id = self._create_form()

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/unpublish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)

    def test_unpublish_auto_activates_latest_snapshot(self):
        """When unpublishing, if latest snapshot != active_version,
        auto-activates the latest before setting status=draft.
        After unpublish, live rows reflect the latest snapshot's state."""
        form_id = self._create_form()
        self._publish(form_id)            # v1 (active=v1)

        detail = self._get(form_id).json()
        group = detail["question_group"][0]
        q = group["question"][0]
        self._put(form_id, {
            "name": "V2 Name",
            "question_group": [{
                **group,
                "question": [{**q, "label": "V2 Label", "option": []}],
            }],
        })
        # Still v1 active
        self.assertEqual(
            Forms.objects.get(pk=form_id).active_version.version, 1
        )

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/unpublish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)

        form = Forms.objects.get(pk=form_id)
        self.assertEqual(
            form.active_version.version, 2,
            "unpublish must auto-activate latest snapshot",
        )
        self.assertEqual(form.status, 1)  # draft

        # GET uses live rows after unpublish (form is draft); they must
        # reflect v2 content (restored by auto-activate).
        data = self._get(form_id).json()
        self.assertEqual(data["status"], "draft")
        self.assertEqual(
            data["question_group"][0]["question"][0]["label"], "V2 Label"
        )

    def test_unpublish_preserves_published_at(self):
        """Unpublish must not clear published_at."""
        form_id = self._create_form()
        self._publish(form_id)
        pub_at = Forms.objects.get(pk=form_id).published_at

        self._unpublish(form_id)

        self.assertEqual(Forms.objects.get(pk=form_id).published_at, pub_at)

    # ─────────────────────────────────────────────
    # Re-publish (publish after unpublish)
    # ─────────────────────────────────────────────

    def test_publish_after_unpublish_sets_published_creates_snapshot(self):
        """POST .../publish on an unpublished form (draft + published_at set)
        creates a new snapshot from live rows and sets status=published.
        This ensures GET returns consistent data after re-publish."""
        form_id = self._create_form()
        self._publish(form_id)
        self._unpublish(form_id)
        count_before = FormPublishedVersion.objects.filter(
            form_id=form_id
        ).count()

        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "published")
        self.assertGreater(
            FormPublishedVersion.objects.filter(form_id=form_id).count(),
            count_before,
            "Re-publish after unpublish must create a new snapshot",
        )

    def test_publish_never_published_draft_creates_snapshot(self):
        """POST .../publish on a fresh draft form creates a snapshot and sets
        status=published (first-ever publish)."""
        form_id = self._create_form()

        res = self._publish(form_id)

        self.assertEqual(res["status"], "published")
        self.assertIsNotNone(res.get("active_version_id"))
        self.assertEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 1
        )

    # ─────────────────────────────────────────────
    # Full lifecycle: publish → unpublish → edit → re-publish
    # ─────────────────────────────────────────────

    def test_unpublish_edit_republish_full_lifecycle(self):
        """publish → unpublish → draft PUT (live rows change) → re-publish
        creates a new snapshot from corrected live rows."""
        form_id = self._create_form()
        self._publish(form_id)   # v1

        self._unpublish(form_id)
        self.assertEqual(Forms.objects.get(pk=form_id).status, 1)  # draft

        detail = self._get(form_id).json()
        group = detail["question_group"][0]
        q = group["question"][0]
        self._put(form_id, {
            "name": "Corrected Form",
            "question_group": [{
                **group,
                "question": [
                    {**q, "label": "Corrected Question", "option": []}
                ],
            }],
        })

        res = self._publish(form_id)   # re-publish: new snapshot
        self.assertEqual(res["status"], "published")
        self.assertEqual(res["name"], "Corrected Form")

        form = Forms.objects.get(pk=form_id)
        self.assertEqual(form.status, 2)  # published
        self.assertGreaterEqual(
            FormPublishedVersion.objects.filter(form_id=form_id).count(), 2
        )
