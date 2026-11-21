from io import StringIO
from django.test import TestCase, override_settings
# from unittest import mock
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_approval.models import DataBatch


@override_settings(USE_TZ=False, TEST_ENV=True)
class BatchDeleteAttachmentTestCase(TestCase, ProfileTestHelperMixin):
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

    def test_delete_batch_attachment(self):
        attachment_id = self.batch.batch_batch_attachment.first().id
        response = self.client.delete(
            f"/api/v1/batch/attachment/{attachment_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 204)

        # Verify the attachment is deleted
        response = self.client.get(
            f"/api/v1/batch/attachments/{self.batch.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # Verify adding a new comment with a file
        self.batch.refresh_from_db()
        comment = self.batch.batch_batch_comment.filter(
            user=self.submitter,
            comment__icontains="deleted",
        ).first()

        self.assertIsNotNone(comment)
        self.assertIsNotNone(comment.file_path)

    def test_delete_non_existent_attachment(self):
        response = self.client.delete(
            "/api/v1/batch/attachment/9999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Not found.")

    def test_delete_attachment_not_owned(self):
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
        response = self.client.delete(
            f"/api/v1/batch/attachment/{attachment_id}",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )
        self.assertEqual(response.status_code, 403)
