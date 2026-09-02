from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class DraftFormDataDetailsTestCase(TestCase, ProfileTestHelperMixin):
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
        form_data = FormData.objects_draft.filter(
            form__pk=1,
        ).order_by("?").first()
        self.data = form_data
        self.user = form_data.created_by
        self.form = form_data.form
        self.administration = form_data.administration

        self.user.set_password("test")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "test")

    def test_draft_form_data_details(self):
        response = self.client.get(
            f"/api/v1/draft-submission/{self.data.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.json()),
            [
                "id",
                "uuid",
                "name",
                "form",
                "administration",
                "geo",
                "created_by",
                "updated_by",
                "created",
                "updated",
                "submitter",
                "duration",
                "answers",
            ]
        )
        self.assertEqual(response.json()["id"], self.data.id)
        self.assertIsInstance(response.json()["answers"], list)
        self.assertEqual(
            list(response.json()["answers"][0]),
            ["history", "question", "value", "index"],
        )
        adm_answer = list(
            filter(
                lambda x: x["question"] == 104,
                response.json()["answers"],
            )
        )
        self.assertIsInstance(adm_answer, list)

    def test_draft_form_data_details_not_found(self):
        response = self.client.get(
            "/api/v1/draft-submission/999999/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_unauthorized_draft_form_data_details(self):
        response = self.client.get(
            f"/api/v1/draft-submission/{self.data.id}/",
            HTTP_AUTHORIZATION="Bearer invalid_token",
        )
        self.assertEqual(response.status_code, 401)
