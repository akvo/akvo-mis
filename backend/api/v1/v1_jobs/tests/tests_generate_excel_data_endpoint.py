from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class GenerateExcelDataAPITestCase(TestCase, ProfileTestHelperMixin):
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
        self.call_command(repeat=2, approved=True)

        self.form = Forms.objects.get(pk=1)
        self.administration = Administration.objects.filter(
            level__level=1
        ).order_by("?").first()
        user = self.create_user(
            email="admin@akvo.org",
            password="Test105*",
            role_level=self.IS_ADMIN,
            administration=self.administration,
            form=self.form
        )
        self.token = self.get_auth_token(
            email=user.email,
            password="Test105*"
        )
        self.url = "/api/v1/download/generate"

    def test_generate_export_data_with_form_only(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_allows_own_administration(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}"
            f"&administration_id={self.administration.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_refuses_out_of_scope_administration(self):
        # A sibling administration the user has no role in.
        other = (
            Administration.objects.filter(level__level=1)
            .exclude(id=self.administration.id)
            .order_by("?")
            .first()
        )
        self.assertIsNotNone(other)
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}"
            f"&administration_id={other.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_export_data_with_invalid_form(self):
        response = self.client.get(
            f"{self.url}?form_id=9999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_export_data_with_form_and_administration(self):
        response = self.client.get(
            (
                f"{self.url}?form_id={self.form.id}"
                f"&administration_id={self.administration.id}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_export_data_with_invalid_administration(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&administration_id=9999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_export_data_with_download_type_all(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&type=all",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_export_data_with_download_type_recent(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&type=recent",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_export_data_with_invalid_download_type(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&type=invalid",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_export_data_with_use_label_true(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&use_label=true",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_export_data_with_use_label_false(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&use_label=false",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_export_data_with_invalid_use_label(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}&use_label=invalid",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_export_data_with_empty_params(self):
        response = self.client.get(
            f"{self.url}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_export_data_unauthenticated(self):
        response = self.client.get(
            f"{self.url}?form_id={self.form.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
