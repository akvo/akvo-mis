from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class WebFormDetailsTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)

        self.form = Forms.objects.get(pk=1)

        self.adm = Administration.objects.filter(
            level__level__gt=2,
        ).first()

        user = self.create_user(
            email="user.123@test.com",
            role_level=self.IS_ADMIN,
            administration=self.adm,
            form=self.form,
        )
        user.set_password("password")
        user.save()

        self.token = self.get_auth_token(
            email=user.email,
            password="password",
        )

    def test_success_get_web_form_details(self):
        response = self.client.get(
            f"/api/v1/form/web/{self.form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("version", data)
        self.assertIn("cascades", data)
        self.assertIn("approval_instructions", data)
        self.assertIn("parent", data)
        self.assertIn("question_group", data)
        grp = data["question_group"][0]
        for key in [
            "name",
            "label",
            "question",
            "repeatable",
            "repeat_text",
            "order",
        ]:
            self.assertIn(key, grp)

    def test_get_web_form_details_by_superuser(self):
        superuser = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        superuser.set_password("password")
        superuser.save()

        token = self.get_auth_token(
            email=superuser.email,
            password="password",
        )

        response = self.client.get(
            f"/api/v1/form/web/{self.form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_get_web_form_details_with_max_level_administration(self):
        q = self.form.form_questions.filter(
            id=104
        ).first()
        q.api = {
            "max_level": 1
        }
        q.save()

        response = self.client.get(
            f"/api/v1/form/web/{self.form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        question_group = data["question_group"][0]
        question = next(
            filter(lambda x: x["id"] == 104, question_group["question"]),
            None
        )

        self.assertIn("query_params", question["api"])
        self.assertEqual(question["api"]["query_params"], "&max_level=1")

    def test_get_web_form_details_with_invalid_form_id(self):
        response = self.client.get(
            "/api/v1/form/web/9999/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_get_web_form_details_without_authentication(self):
        response = self.client.get(f"/api/v1/form/web/{self.form.id}/")
        self.assertEqual(response.status_code, 401)
