from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


def administration_label(administration):
    """What ListFormDataSerializer should render for a unit.

    Deliberately expressed as "ancestors minus the root, then the unit"
    rather than by re-splitting full_name -- the string split is the bug
    these assertions used to encode.
    """
    ancestors = list(administration.ancestors or [])
    return " - ".join(
        [a.name for a in ancestors[1:]] + [administration.name]
    )


@override_settings(USE_TZ=False, TEST_ENV=True)
class DraftFormDataListTestCase(TestCase, ProfileTestHelperMixin):
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

    def test_draft_form_data_list(self):
        response = self.client.get(
            f"/api/v1/draft-submissions/{self.form.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.json()),
            [
                "current",
                "total",
                "total_page",
                "data",
            ]
        )
        self.assertGreater(
            response.json()["total"], 0
        )

    def test_search_by_name_draft_form_data_list(self):
        search = self.data.name.lower()[:5]
        response = self.client.get(
            f"/api/v1/draft-submissions/{self.form.id}/?search={search}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(
            response.json()["total"], 0
        )
        for data in response.json()["data"]:
            self.assertIn(self.data.name, data["name"])

    def test_administration_filter_draft_form_data_list(self):
        response = self.client.get(
            (
                f"/api/v1/draft-submissions/{self.form.id}/"
                f"?administration={self.administration.id}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(
            response.json()["total"], 0
        )
        self.assertIn(
            administration_label(self.administration),
            [
                data["administration"]
                for data in response.json()["data"]
            ]
        )

    def test_unauthorized_draft_form_data_list(self):
        response = self.client.get(
            f"/api/v1/draft-submissions/{self.form.id}/",
            HTTP_AUTHORIZATION="Bearer invalid_token",
        )
        self.assertEqual(response.status_code, 401)

    def test_draft_form_data_list_with_invalid_form_id(self):
        response = self.client.get(
            "/api/v1/draft-submissions/9999/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
