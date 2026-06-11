import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    UserRole,
)


FORM_PAYLOAD = {
    "name": "Archive Test Form",
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
class ManageFormArchiveTestCase(TestCase):
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

    # ── helpers ───────────────────────────────────

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

    def _archive(self, form_id, header=None):
        return self.client.post(
            f"/api/v1/manage/forms/{form_id}/archive",
            content_type="application/json",
            **(header or self.header),
        )

    def _restore(self, form_id, header=None):
        return self.client.post(
            f"/api/v1/manage/forms/{form_id}/restore",
            content_type="application/json",
            **(header or self.header),
        )

    def _add_submission(self, form_id):
        form = Forms.objects_with_deleted.get(pk=form_id)
        adm = Administration.objects.filter(level__level=1).first()
        FormData.objects.create(
            form=form,
            name="Test Submission",
            administration=adm,
            created_by=self.admin,
        )

    def _make_user_with_access(self, email, accesses):
        user = SystemUser.objects.create_user(
            email=email, password="Test105*"
        )
        level = Levels.objects.first()
        role = Role.objects.create(
            name=f"role_{email}", administration_level=level
        )
        for acc in accesses:
            role.role_role_feature_access.create(
                type=FeatureTypes.form_builder, access=acc
            )
        adm = Administration.objects.first()
        UserRole.objects.create(user=user, role=role, administration=adm)
        return user, _login(self.client, email, "Test105*")

    # ── Archive (soft-delete) ─────────────────────

    def test_archive_sets_deleted_at_and_hides_from_default_manager(self):
        """POST /archive soft-deletes: deleted_at set, gone from
        Forms.objects, present in objects_deleted (D-1)."""
        form_id = self._create_form()
        res = self._archive(form_id)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "archived")
        self.assertFalse(Forms.objects.filter(pk=form_id).exists())
        archived = Forms.objects_deleted.filter(pk=form_id).first()
        self.assertIsNotNone(archived)
        self.assertIsNotNone(archived.deleted_at)

    def test_archive_allowed_with_submissions(self):
        """Archive succeeds even when the form has submissions (D-1)."""
        form_id = self._create_form()
        self._add_submission(form_id)
        res = self._archive(form_id)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Forms.objects.filter(pk=form_id).exists())

    def _public_form_ids(self):
        res = self.client.get("/api/v1/forms", **self.header).json()
        data = res["data"] if isinstance(res, dict) else res
        return [f["id"] for f in data]

    def test_archive_published_form_removes_from_public_list(self):
        """An archived published form drops out of the public /forms list
        automatically via the default manager."""
        form_id = self._create_form()
        self._publish(form_id)
        self.assertIn(form_id, self._public_form_ids())
        self._archive(form_id)
        self.assertNotIn(form_id, self._public_form_ids())

    def test_archive_already_archived_returns_400(self):
        """Archiving an already-archived form returns 400."""
        form_id = self._create_form()
        self.assertEqual(self._archive(form_id).status_code, 200)
        self.assertEqual(self._archive(form_id).status_code, 400)

    # ── Restore ───────────────────────────────────

    def test_restore_clears_deleted_at_and_sets_draft(self):
        """Restore clears deleted_at AND forces status=draft (D-7)."""
        form_id = self._create_form()
        self._publish(form_id)
        self._archive(form_id)
        res = self._restore(form_id)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "draft")
        form = Forms.objects.get(pk=form_id)
        self.assertIsNone(form.deleted_at)
        self.assertEqual(form.status, FormStatus.draft)

    def test_restore_non_archived_returns_400(self):
        """Restore on a form that is not archived returns 400."""
        form_id = self._create_form()
        self.assertEqual(self._restore(form_id).status_code, 400)

    # ── DELETE = permanent hard-delete (D-9, D-10) ─

    def test_delete_hard_removes_row_even_with_soft_delete(self):
        """DELETE permanently removes the row — objects_with_deleted is
        empty afterwards (regression guard for D-9)."""
        form_id = self._create_form()
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            Forms.objects_with_deleted.filter(pk=form_id).exists()
        )

    def test_delete_archived_form_without_submissions(self):
        """An archived form with no submissions can be permanently
        deleted (resolves via objects_with_deleted, D-10)."""
        form_id = self._create_form()
        self._archive(form_id)
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            Forms.objects_with_deleted.filter(pk=form_id).exists()
        )

    def test_delete_with_submissions_still_409(self):
        """DELETE on a form with submissions still returns 409."""
        form_id = self._create_form()
        self._add_submission(form_id)
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 409)

    # ── Permissions ───────────────────────────────

    def test_archive_requires_form_publish(self):
        """A user without form_publish cannot archive (403)."""
        form_id = self._create_form()
        _, header = self._make_user_with_access("noperm@akvo.org", [])
        self.assertEqual(self._archive(form_id, header).status_code, 403)

    def test_delete_requires_form_delete(self):
        """A non-superuser without form_delete cannot delete (403)."""
        form_id = self._create_form()
        _, header = self._make_user_with_access(
            "noform_delete@akvo.org", [FeatureAccessTypes.form_publish]
        )
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **header,
        )
        self.assertEqual(res.status_code, 403)

    def test_delete_allowed_for_non_superuser_with_form_delete(self):
        """A non-superuser granted form_delete CAN permanently delete a
        form with no submissions (D-11)."""
        form_id = self._create_form()
        _, header = self._make_user_with_access(
            "candelete@akvo.org", [FeatureAccessTypes.form_delete]
        )
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **header,
        )
        self.assertEqual(res.status_code, 204)
