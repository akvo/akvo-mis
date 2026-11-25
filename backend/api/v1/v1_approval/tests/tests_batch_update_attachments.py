from io import StringIO
from django.test import TestCase, override_settings
# from unittest import mock
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_approval.models import DataBatch


@override_settings(USE_TZ=False, TEST_ENV=True)
class BatchUpdateAttachmentTestCase(TestCase, ProfileTestHelperMixin):
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

    def test_update_batch_attachment(self):
        new_pdf = SimpleUploadedFile(
            name="new_attachment.pdf",
            content="This is a new test PDF file content".encode(),
            content_type="application/pdf"
        )
        data = {
            "file": new_pdf,
            "comment": "Updated attachment with new file",
        }
        old_attachment = self.batch.batch_batch_attachment.first()
        attachment_id = old_attachment.id

        response = self.client.post(
            f"/api/v1/batch/attachment/{attachment_id}/edit",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            f"/api/v1/batch/attachments/{self.batch.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Verify the updated attachment
        updated_attachment = list(filter(
            lambda x: x["id"] == attachment_id,
            response.json(),
        ))[0]
        self.assertNotEqual(
            updated_attachment["file_path"],
            old_attachment.file_path,
        )

    def test_update_attachment_with_same_file(self):
        # Create a new file with the same name and content as the original
        same_file = SimpleUploadedFile(
            name="test_attachment1.pdf",
            content="This is a test PDF file content".encode(),
            content_type="application/pdf"
        )
        # Attempt to update the attachment with the same file
        data = {
            # Using the same file as the existing attachment
            "file": same_file,
            "comment": "Updating with the same file",
        }
        attachment_id = self.batch.batch_batch_attachment.filter(
            name="test_attachment1.pdf"
        ).first().id

        response = self.client.post(
            f"/api/v1/batch/attachment/{attachment_id}/edit",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        # Verify that the attachment was not changed
        response = self.client.get(
            f"/api/v1/batch/attachments/{self.batch.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        attachments = response.json()
        self.assertEqual(len(attachments), 2)

        updated_attachment = next(
            (att for att in attachments if att["id"] == attachment_id), None
        )
        self.assertIsNotNone(updated_attachment)
        self.assertEqual(updated_attachment["name"], same_file.name)

    def test_update_non_existent_attachment(self):
        response = self.client.post(
            "/api/v1/batch/attachment/9999/edit",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Not found.")

    def test_update_attachment_not_owned(self):
        # Create a new user and try to
        # delete an attachment owned by another user
        other_user = self.create_user(
            email="non.owner@test.com",
            role_level=self.IS_ADMIN,
            password="test1234",
            administration=self.administration,
            form=self.form,
        )

        other_token = self.get_auth_token(other_user.email, "test1234")
        attachment_id = self.batch.batch_batch_attachment.first().id
        response = self.client.post(
            f"/api/v1/batch/attachment/{attachment_id}/edit",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )
        self.assertEqual(response.status_code, 403)
