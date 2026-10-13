from django.test import TestCase
from django.core.management import call_command
from rest_framework import status

from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


class MobileDatapointUserScopeTest(TestCase, ProfileTestHelperMixin):
    """A mobile assignment must not hand the device data outside the device
    user's own administration access.

    An assignment configured with an administration broader than the user's
    roles (here the national root for a province-scoped user) previously let
    the device download the whole country. The datapoint list now intersects
    the assignment's administrations with the user's role scope.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.root = Administration.objects.get(level__level=0)
        level1 = list(
            Administration.objects.filter(level__level=1).order_by("id")
        )
        self.prov_in = level1[0]
        self.prov_out = level1[1]
        self.form = Forms.objects.filter(parent__isnull=True).first()

        # User's only role is at prov_in.
        self.user = self.create_user(
            email="collector@test.org",
            role_level=self.IS_ADMIN,
            administration=self.prov_in,
            form=self.form,
        )

        self.passcode = "scopepass123"
        assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="collector", passcode=self.passcode
        )
        # Assignment is (mis)configured with the national root -- broader than
        # the user's province role.
        assignment.administrations.add(self.root)
        assignment.forms.add(self.form)

        self.dp_in = self._make_datapoint(self.prov_in, "InScope DP")
        self.dp_out = self._make_datapoint(self.prov_out, "OutOfScope DP")

    def _make_datapoint(self, administration, name):
        return FormData.objects.create(
            name=name,
            geo=None,
            form=self.form,
            administration=administration,
            created_by=self.user,
            is_pending=False,
            is_draft=False,
        )

    def _device_token(self):
        response = self.client.post(
            "/api/v1/device/auth",
            {"code": self.passcode},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["syncToken"]

    def test_device_only_sees_in_scope_datapoints(self):
        token = self._device_token()
        response = self.client.get(
            f"/api/v1/device/datapoint-list?form_id={self.form.id}",
            follow=True,
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.json()["data"]]
        self.assertIn(self.dp_in.id, ids)
        self.assertNotIn(self.dp_out.id, ids)
