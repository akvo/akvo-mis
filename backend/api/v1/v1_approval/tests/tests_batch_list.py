from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class DataBatchListTestCase(TestCase, ProfileTestHelperMixin):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)
        self.call_command(repeat=2, approved=False)

        self.data = FormData.objects.filter(is_pending=True).first()
        self.submitter = self.data.created_by
        self.submitter.set_password("test")
        self.submitter.save()

        self.token = self.get_auth_token(self.submitter.email, "test")

        payload = {
            "name": "Test Batch",
            "comment": "This is a test batch",
            "data": [self.data.id],
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201)

    def test_success_get_batch_list(self):
        response = self.client.get(
            "/api/v1/batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("current", response_json)
        self.assertIn("total", response_json)
        self.assertIn("total_page", response_json)
        self.assertIn("data", response_json)
        self.assertIsInstance(response_json["data"], list)
        self.assertGreater(response_json["total"], 0)
        self.assertEqual(
            list(response_json["data"][0]),
            [
                "id",
                "name",
                "form",
                "administration",
                "file",
                "total_data",
                "created",
                "updated",
                "status",
                "approvers",
            ]
        )

    def test_get_batch_list_by_form(self):
        response = self.client.get(
            f"/api/v1/batch?form={self.data.form.id}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response_json)
        self.assertGreater(len(response_json["data"]), 0)

    def test_get_batch_list_by_approved_status(self):
        response = self.client.get(
            "/api/v1/batch?approved=true",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response_json)
        self.assertEqual(response_json["total"], 0)

    def test_get_batch_list_without_auth(self):
        response = self.client.get(
            "/api/v1/batch",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertEqual(
            response_json["detail"],
            "Authentication credentials were not provided."
        )
