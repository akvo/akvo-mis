from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_users.models import SystemUser


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormXLSFormExportEndpointTestCase(TestCase):
    """
    Tests for GET /api/v1/manage/forms/{id}/export-xlsform (FB-014 / T-004).
    """

    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        with connection.cursor() as cur:
            for tbl in ["form", "question_group", "question", "option"]:
                cur.execute(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{tbl}', 'id'),"
                    f'(SELECT COALESCE(MAX(id), 0) FROM "{tbl}") + 1,'
                    f"false)"
                )
        self.header = _login(self.client)
        self.form = Forms.objects.first()
        self.user = SystemUser.objects.filter(email="admin@akvo.org").first()

    def test_export_xlsform_returns_200_and_xlsx_content_type(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export-xlsform",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # noqa
        )

    def test_export_xlsform_content_disposition(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export-xlsform",
            **self.header,
        )
        disposition = res.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn(".xlsx", disposition)

    def test_export_xlsform_unauthenticated_401(self):
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export-xlsform"
        )
        self.assertEqual(res.status_code, 401)

    def test_export_xlsform_non_existent_404(self):
        res = self.client.get(
            "/api/v1/manage/forms/999999/export-xlsform",
            **self.header,
        )
        self.assertEqual(res.status_code, 404)

    def test_export_xlsform_skipped_header_present_if_skipped(self):
        g = QuestionGroup.objects.create(
            form=self.form, name="grp_skipped", order=99
        )
        Questions.objects.create(
            form=self.form,
            question_group=g,
            name="unsupported_tree",
            type=QuestionTypes.tree,
            order=1,
        )
        res = self.client.get(
            f"/api/v1/manage/forms/{self.form.id}/export-xlsform",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("X-XLSForm-Skipped", res)
        self.assertIn("unsupported_tree", res["X-XLSForm-Skipped"])
