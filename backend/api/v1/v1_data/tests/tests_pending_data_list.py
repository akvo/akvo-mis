from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_data.functions import add_fake_answers


@override_settings(USE_TZ=False, TEST_ENV=True)
class PendingDataListTestCase(TestCase, ProfileTestHelperMixin):

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test")

        self.parent_form = Forms.objects.get(pk=1)
        self.form = self.parent_form.children.first()
        self.administration = Administration.objects.filter(
            level__level=3
        ).order_by("id").first()

        self.submitter = self.create_user(
            email="submitter@test.com",
            role_level=self.IS_ADMIN,
            password="test",
            administration=self.administration,
            form=self.form,
        )
        self.submitter.set_password("test")
        self.submitter.save()

        self.token = self.get_auth_token(self.submitter.email, "test")

        registration_data = FormData.objects.create(
            name="New Registration Data",
            form=self.parent_form,
            created_by=self.submitter,
            administration=self.administration,
            geo=[7.2088, 126.8456],
            is_pending=True,
        )
        add_fake_answers(registration_data)

        data = FormData.objects.create(
            name="Test Pending Monitoring Data",
            parent=registration_data,
            form=self.form,
            created_by=self.submitter,
            administration=self.administration,
            geo=[7.2088, 126.8456],
            is_pending=True,
        )
        add_fake_answers(data)

        self.data = data

    def test_pending_monitoring_data_list(self):
        response = self.client.get(
            f"/api/v1/form-pending-data/{self.form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertIn("current", res)
        self.assertIn("total", res)
        self.assertIn("total_page", res)
        self.assertIn("data", res)
        self.assertGreater(res["total"], 0)
        self.assertEqual(
            list(res["data"][0]),
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
        self.assertEqual(
            res["data"][0]["created_by"],
            self.submitter.get_full_name()
        )

    def test_pending_registration_data_list(self):
        registration_data = FormData.objects.create(
            name="Test Registration Data",
            form=self.parent_form,
            created_by=self.submitter,
            administration=self.administration,
            geo=[7.2088, 126.8456],
            is_pending=True,
        )
        add_fake_answers(registration_data)

        response = self.client.get(
            f"/api/v1/form-pending-data/{self.parent_form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertIn("current", res)
        self.assertIn("total", res)
        self.assertIn("total_page", res)
        self.assertIn("data", res)
        self.assertGreaterEqual(res["total"], 0)

    def test_pending_data_list_invalid_form_id(self):
        response = self.client.get(
            "/api/v1/form-pending-data/9999/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_pending_data_list_unauthorized(self):
        response = self.client.get(
            f"/api/v1/form-pending-data/{self.form.id}/",
            HTTP_AUTHORIZATION="Bearer invalid_token",
        )
        self.assertEqual(response.status_code, 401)

    def test_pending_data_list_by_user_has_no_form_access(self):
        unauthorized_user = self.create_user(
            email="new.user123@test.com",
            role_level=self.IS_ADMIN,
            administration=self.administration,
            form=Forms.objects.exclude(pk=self.parent_form.id).first()
        )
        unauthorized_user.set_password("test1234")
        unauthorized_user.save()

        unauthorized_token = self.get_auth_token(
            unauthorized_user.email, "test1234"
        )
        response = self.client.get(
            f"/api/v1/form-pending-data/{self.form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {unauthorized_token}",
        )
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertEqual(res["total"], 0)
