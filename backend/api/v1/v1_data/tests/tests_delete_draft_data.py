from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class DeleteDraftFormDataTestCase(TestCase, ProfileTestHelperMixin):
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
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.call_command(repeat=2, draft=True, approved=False)
        form_data = FormData.objects_draft.order_by("?").first()
        self.data = form_data
        self.user = form_data.created_by
        self.form = form_data.form
        self.administration = form_data.administration

        self.user.set_password("test")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "test")

    def test_delete_draft_form_data(self):
        response = self.client.delete(
            f"/api/v1/draft-submission/{self.data.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 204)

        # Check if the data is actually deleted
        response = self.client.get(
            f"/api/v1/draft-submission/{self.data.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

        # Ensure the data is no longer available - hard delete
        with self.assertRaises(FormData.DoesNotExist):
            FormData.objects.get(id=self.data.id)

    def test_delete_draft_form_data_unauthorized(self):
        # Attempt to delete without authentication
        response = self.client.delete(
            f"/api/v1/draft-submission/{self.data.id}/"
        )
        self.assertEqual(response.status_code, 401)

    def test_delete_draft_form_data_forbidden(self):
        # Create a different user and try to delete the data
        other_user = self.create_user(
            email="other.123@test.com",
            role_level=self.IS_ADMIN,
            administration=self.administration,
            form=self.form,
        )
        other_user.set_password("password")
        other_user.save()

        other_token = self.get_auth_token(other_user.email, "password")

        response = self.client.delete(
            f"/api/v1/draft-submission/{self.data.id}/",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "You do not have permission to perform this action."
        )

    def test_delete_draft_form_data_with_invalid_data_id(self):
        response = self.client.delete(
            "/api/v1/draft-submission/9999/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Not found.")

    def test_delete_draft_form_data_with_invalid_token(self):
        response = self.client.delete(
            f"/api/v1/draft-submission/{self.data.id}/",
            HTTP_AUTHORIZATION="Bearer invalid_token",
        )
        self.assertEqual(response.status_code, 401)
