from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class DataBatchDetailsTestCase(TestCase, ProfileTestHelperMixin):
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

        self.data = FormData.objects.filter(
            is_pending=True,
            form__pk=2,
        ).first()
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

        self.data.refresh_from_db()
        self.batch = self.data.data_batch_list.batch

    def test_success_get_batch_comments(self):
        response = self.client.get(
            f"/api/v1/batch/comment/{self.batch.id}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertGreater(len(response_json), 0)
        self.assertIn("user", response_json[0])
        self.assertIn("comment", response_json[0])
        self.assertIn("created", response_json[0])
        self.assertIn("file_path", response_json[0])

        self.assertEqual(
            list(response_json[0]["user"]),
            [
                "name",
                "email",
            ]
        )

    def test_success_get_batch_summary(self):
        response = self.client.get(
            f"/api/v1/batch/summary/{self.batch.id}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertGreater(len(response_json), 0)
        self.assertEqual(
            list(response_json[0]),
            [
                "id",
                "form",
                "form_name",
                "question",
                "type",
                "value",
            ]
        )
        self.assertEqual(
            list(response_json[0]["value"][0]),
            [
                "type",
                "total",
            ]
        )

    def test_success_get_batch_details(self):
        response = self.client.get(
            f"/api/v1/form-pending-data-batch/{self.batch.id}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertGreater(len(response_json), 0)
        self.assertEqual(
            response_json[0]["uuid"],
            self.data.uuid
        )
        self.assertEqual(
            list(response_json[0]),
            [
                "id",
                "uuid",
                "name",
                "form",
                "administration",
                "geo",
                "submitter",
                "duration",
                "created_by",
                "created",
                "answer_history",
                "parent",
            ]
        )
