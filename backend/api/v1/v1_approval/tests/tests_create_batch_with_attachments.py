from io import StringIO
from django.test import TestCase, override_settings
from unittest import mock
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_approval.models import DataBatch


@override_settings(USE_TZ=False, TEST_ENV=True)
class CreateDataBatchWithAttachmentsTestCase(TestCase, ProfileTestHelperMixin):
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

        # Create a SimpleUploadedFile for testing file uploads
        self.pdf_file = SimpleUploadedFile(
            name="test_attachment.pdf",
            content="This is a test PDF file content".encode(),
            content_type="application/pdf"
        )

    def test_success_create_batch_with_attachments(self):
        # Count batches before the request to verify creation
        batch_count_before = DataBatch.objects.count()

        # Use proper file upload format for Django test client
        data = {
            "name": "Test Batch with Attachments",
            "comment": "This is a test batch with attachments",
            "data": [self.data.id],
            "files": [self.pdf_file],
        }

        response = self.client.post(
            "/api/v1/batch",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response_json = response.json()
        self.assertEqual(response.status_code, 201)
        self.assertIn("message", response_json)
        self.assertEqual(
            response_json["message"], "Batch created successfully"
        )
        # Verify that a new batch was actually created
        batch_count_after = DataBatch.objects.count()
        self.assertEqual(batch_count_before + 1, batch_count_after)
        # Verify that the DataBatchComments were created correctly
        latest_batch = DataBatch.objects.latest('id')
        self.assertEqual(latest_batch.name, "Test Batch with Attachments")

        # Should have 2 comments - from form field and file upload
        comments = latest_batch.batch_batch_comment.all()
        self.assertEqual(comments.count(), 2)
        # Check the manual comment
        comment_text = "This is a test batch with attachments"
        manual_comment = comments.filter(comment=comment_text).first()
        self.assertIsNotNone(manual_comment)
        self.assertEqual(manual_comment.user, self.submitter)
        # Check the file upload comment
        file_comment = comments.filter(
            comment__startswith="Attachment uploaded:"
        ).first()
        self.assertIsNotNone(file_comment)
        self.assertTrue(
            file_comment.file_path,
            "File path should be saved in comment"
        )
        self.assertEqual(file_comment.user, self.submitter)

    def test_create_batch_with_attachments_without_data(self):
        data = {
            "name": "Test Batch with Attachments",
            "comment": "This is a test batch with attachments",
            "data": [],
            "files": [self.pdf_file],
        }

        response = self.client.post(
            "/api/v1/batch",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

        # Check for specific error message
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertIn(
            "field_title is required.",
            response_json["detail"]["data"]
        )

    def test_create_batch_with_attachments_invalid_data(self):
        data = {
            "name": "Test Batch with Attachments",
            "comment": "This is a test batch with attachments",
            "data": [9999],  # Assuming 9999 is an invalid ID
            "files": [self.pdf_file],
        }

        response = self.client.post(
            "/api/v1/batch",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

        # Check for specific error message related to invalid data ID
        response_json = response.json()
        self.assertIn("detail", response_json)
        # The error should be about invalid primary key for FormData
        for err in response_json["detail"]["data"].values():
            self.assertIn(
                'Invalid pk "9999" - object does not exist.',
                err
            )

    @mock.patch('api.v1.v1_approval.serializers.DataBatchList.objects.create')
    def test_transaction_rollback_on_data_list_error(self, mock_create):
        # Mock the DataBatchList.objects.create to raise an exception
        mock_create.side_effect = Exception("Error creating data list")

        payload = {
            "name": "Test Batch Transaction Rollback",
            "comment": "Testing transaction rollback",
            "data": [self.data.id],
        }

        # Count batches before the request
        batch_count_before = DataBatch.objects.count()

        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Verify the response is an error
        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertIn(
            "Failed to create batch data list: Error creating data list",
            response_json["detail"]
        )

        # Verify no batch was created (transaction rolled back)
        batch_count_after = DataBatch.objects.count()
        self.assertEqual(batch_count_before, batch_count_after)

    @mock.patch('api.v1.v1_approval.serializers.send_email')
    def test_transaction_rollback_on_email_error(self, mock_send_email):
        # Mock the send_email function to raise an exception
        mock_send_email.side_effect = Exception("Email sending failed")

        payload = {
            "name": "Test Batch Email Error",
            "comment": "Testing email error handling",
            "data": [self.data.id],
        }

        # Count batches before the request
        batch_count_before = DataBatch.objects.count()

        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Verify the response is an error
        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertIn(
            "Failed to send email to approvers: Email sending failed",
            response_json["detail"]
        )

        # Verify no batch was created (transaction rolled back)
        batch_count_after = DataBatch.objects.count()
        self.assertEqual(batch_count_before, batch_count_after)

    @mock.patch('utils.storage.upload')
    def test_transaction_rollback_on_file_upload_error(self, mock_upload):
        # Mock the storage.upload function to raise an exception
        mock_upload.side_effect = Exception("File upload failed")

        # Count batches before the request
        batch_count_before = DataBatch.objects.count()

        data = {
            "name": "Test Batch File Upload Error",
            "comment": "Testing file upload error handling",
            "data": [self.data.id],
            "files": [self.pdf_file],
        }

        response = self.client.post(
            "/api/v1/batch",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Verify the response is an error
        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertIn(
            "Failed to upload file test_attachment.pdf: File upload failed",
            response_json["detail"]
        )

        # Verify no batch was created (transaction rolled back)
        batch_count_after = DataBatch.objects.count()
        self.assertEqual(batch_count_before, batch_count_after)

    @mock.patch(
        'api.v1.v1_approval.serializers.DataBatchComments.objects.create'
    )
    def test_transaction_rollback_on_comment_error(self, mock_create_comment):
        # Mock the DataBatchComments.objects.create to raise an exception
        mock_create_comment.side_effect = Exception("Failed to add comment")

        payload = {
            "name": "Test Batch Comment Error",
            "comment": "Testing comment error handling",
            "data": [self.data.id],
        }

        # Count batches before the request
        batch_count_before = DataBatch.objects.count()

        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Verify the response is an error
        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertIn(
            "Failed to add comment: Failed to add comment",
            response_json["detail"]
        )

        # Verify no batch was created (transaction rolled back)
        batch_count_after = DataBatch.objects.count()
        self.assertEqual(batch_count_before, batch_count_after)

    def test_user_without_submit_role(self):
        # Remove submit role from the user
        self.submitter.user_user_role.filter(
            role__role_role_access__data_access=DataAccessTypes.submit,
        ).delete()
        # Attempt to create a batch without submit role
        payload = {
            "name": "Test Batch No Submit Role",
            "data": [self.data.id],
        }

        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Verify the response is an error
        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn("detail", response_json)
        self.assertIn(
            "All data must belong to the user's administrations.",
            response_json["detail"]["data"]
        )

    def test_create_batch_with_invalid_file_format(self):
        """Test that attempting to create a batch with an invalid file format
        returns the appropriate error message."""
        # Create an invalid file (e.g., .exe)
        invalid_file = SimpleUploadedFile(
            name="test.exe",
            content=b"invalid executable content",
            content_type="application/octet-stream"
        )

        data = {
            "name": "Test Batch with Invalid File",
            "comment": "This is a test batch with invalid file",
            "data": [self.data.id],
            "files": [invalid_file],
        }

        # Count batches before the request to verify no batch is created
        batch_count_before = DataBatch.objects.count()

        response = self.client.post(
            "/api/v1/batch",
            data=data,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Verify that validation failed with 400 status code
        self.assertEqual(response.status_code, 400)
        response_json = response.json()

        # Check that we get a detail key in the response
        self.assertIn("detail", response_json)

        # Check that the error contains file format message
        error_str = str(response_json["detail"])
        self.assertIn("Invalid file format", error_str)
        self.assertIn("test.exe", error_str)

        # Verify that no batch was created
        batch_count_after = DataBatch.objects.count()
        self.assertEqual(batch_count_before, batch_count_after)
