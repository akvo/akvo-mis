from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.models import Dashboard

BASE_URL = "/api/v1/manage/dashboards"


def auth(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}


@override_settings(USE_TZ=False)
class DashboardVisibilityTestCase(TestCase, ProfileTestHelperMixin):
    """Only a published dashboard can be made public (spec D-1)."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_visibility@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.header = auth(self.user)
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=Forms.objects.get(pk=6001),
            created_by=self.user,
        )
        self.url = "{0}/{1}/visibility".format(BASE_URL, self.dashboard.id)

    def post(self, is_public):
        return self.client.post(
            self.url,
            {"is_public": is_public},
            content_type="application/json",
            **self.header
        )

    def publish_it(self):
        self.dashboard.status = DashboardStatus.published
        self.dashboard.published_config = {
            "default_filters": {}, "widgets": []
        }
        self.dashboard.save()

    def test_making_a_draft_public_is_rejected(self):
        res = self.post(True)
        self.assertEqual(res.status_code, 400)
        self.dashboard.refresh_from_db()
        self.assertFalse(self.dashboard.is_public)

    def test_making_a_published_dashboard_public(self):
        self.publish_it()
        res = self.post(True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["is_public"])
        self.dashboard.refresh_from_db()
        self.assertTrue(self.dashboard.is_public)

    def test_making_a_public_dashboard_private_again(self):
        self.publish_it()
        self.post(True)
        res = self.post(False)
        self.assertEqual(res.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertFalse(self.dashboard.is_public)

    def test_making_a_draft_private_is_allowed(self):
        # Never an error to reduce exposure, even when it is a no-op.
        res = self.post(False)
        self.assertEqual(res.status_code, 200)

    def test_is_public_missing_from_the_body_is_400(self):
        res = self.client.post(
            self.url, {}, content_type="application/json", **self.header
        )
        self.assertEqual(res.status_code, 400)

    def test_unpublishing_a_public_dashboard_makes_it_private(self):
        self.publish_it()
        self.post(True)
        res = self.client.post(
            "{0}/{1}/unpublish".format(BASE_URL, self.dashboard.id),
            **self.header
        )
        self.assertEqual(res.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertFalse(self.dashboard.is_public)

    def test_republishing_does_not_restore_public(self):
        # The regression that matters: the failure here is silent
        # re-exposure, not an error, so nothing else would catch it.
        self.publish_it()
        self.post(True)
        self.client.post(
            "{0}/{1}/unpublish".format(BASE_URL, self.dashboard.id),
            **self.header
        )
        self.client.post(
            "{0}/{1}/publish".format(BASE_URL, self.dashboard.id),
            **self.header
        )
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.status, DashboardStatus.published)
        self.assertFalse(self.dashboard.is_public)
