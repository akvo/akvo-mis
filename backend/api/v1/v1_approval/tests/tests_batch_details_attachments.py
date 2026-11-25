from io import StringIO
from django.test import TestCase, override_settings
# from unittest import mock
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_approval.models import DataBatch


@override_settings(USE_TZ=False, TEST_ENV=True)
class BatchAttachmentDetailsTestCase(TestCase, ProfileTestHelperMixin):
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

        self.administration = self.data.administration
        self.form = self.data.form

        self.token = self.get_auth_token(self.submitter.email, "test")

        # Create a SimpleUploadedFile for testing file uploads
        self.pdf1 = SimpleUploadedFile(
            name="test_attachment1.pdf",
            content="This is a test PDF file content".encode(),
            content_type="application/pdf"
        )
        self.pdf2 = SimpleUploadedFile(
            name="test_attachment2.pdf",
            content="This is another test PDF file content".encode(),
            content_type="application/pdf"
        )

        data = {
            "name": "Test Batch with Attachments",
            "comment": "This is a test batch with attachments",
            "data": [self.data.id],
            "files": [self.pdf1, self.pdf2],
        }

        response = self.client.post(
            "/api/v1/batch",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 201)

        self.batch = DataBatch.objects.filter(
            user=self.submitter,
            approved=False,
        ).first()

    def test_get_batch_attachments(self):
        response = self.client.get(
            f"/api/v1/batch/attachments/{self.batch.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            list(response.data[0]),
            [
                "id",
                "name",
                "file_path",
                "created",
            ]
        )

        # Verify the first attachment
        attachment = response.json()[0]
        self.assertIn(
            "batch-attachments",
            attachment["file_path"].split("/"),
        )
