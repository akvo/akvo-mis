import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.models import Administration


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
class ManageFormDeleteTestCase(TestCase):
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

    def _create_form(self):
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        return res.json()["id"]

    # ─────────────────────────────────────────────
    # DELETE /api/v1/manage/forms/{id}
    # ─────────────────────────────────────────────

    def test_delete_form_without_submissions(self):
        """DELETE with no submissions returns 204 and removes the form."""
        form_id = self._create_form()
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Forms.objects.filter(pk=form_id).exists())

    def test_delete_form_not_found(self):
        """DELETE on non-existent form returns 404."""
        res = self.client.delete(
            "/api/v1/manage/forms/99999",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    def test_delete_form_with_submissions_returns_409(self):
        """DELETE on a form with submissions returns 409."""
        form_id = self._create_form()
        form = Forms.objects.get(pk=form_id)
        adm = Administration.objects.filter(level__level=1).first()
        FormData.objects.create(
            form=form,
            name="Test Submission",
            administration=adm,
            created_by=self.admin,
        )
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 409)

    def test_delete_requires_superuser(self):
        """DELETE by a non-superuser returns 403."""

        form_id = self._create_form()
        # Create a regular (non-superuser) user
        user = SystemUser.objects.create_user(
            email="regular@akvo.org",
            password="Test105*",
        )
        non_admin_header = _login(self.client, "regular@akvo.org", "Test105*")
        res = self.client.delete(
            f"/api/v1/manage/forms/{form_id}",
            content_type="application/json",
            **non_admin_header,
        )
        self.assertIn(res.status_code, [403])
        user.delete()
