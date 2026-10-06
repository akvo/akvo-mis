import os
from django.test import TestCase
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import Administration
from django.core.management import call_command
from rest_framework import status

from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData
from api.v1.v1_data.functions import add_fake_answers
from mis.settings import STORAGE_PATH


class MobileDownloadDataPointListWithSpecificAdminTestCase(
    TestCase, AssignmentTokenTestHelperMixin, ProfileTestHelperMixin
):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        # Create a superadmin user
        self.user = self.create_user(
            email="test@test.org",
            role_level=self.IS_SUPER_ADMIN,
        )

        # Create a mobile assignment for the user
        self.administration = Administration.objects.filter(
            level__level=1
        ).order_by("?").last()
        self.form = Forms.objects.get(pk=1)
        self.passcode = "passcode1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=self.passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.mobile_assignment.administrations.add(
            self.administration
        )
        self.mobile_assignment.forms.add(self.form)
        self.token = self.get_assignment_token(self.passcode)

        # Seed form data with correct administration
        self.data_1 = FormData.objects.create(
            uuid="test-uuid-1",
            form=self.form,
            created_by=self.user,
            administration=self.administration,
            submitter=self.mobile_assignment.name,
            name="Test Form Data",
        )
        add_fake_answers(self.data_1)
        self.data_1.write_file()

        # Seed form data with different administration
        self.other_administration = Administration.objects.filter(
            level__level=1
        ).exclude(
            id=self.administration.id
        ).order_by("?").first()
        self.data_2 = FormData.objects.create(
            uuid="test-uuid-2",
            form=self.form,
            created_by=self.user,
            administration=self.other_administration,
            submitter=self.mobile_assignment.name,
            name="Other Admin Form Data",
        )
        add_fake_answers(self.data_2)
        self.data_2.write_file()

    def tearDown(self):
        # Clean up the created files
        if os.path.exists(
            f"{STORAGE_PATH}/datapoints/{self.data_1.uuid}.json"
        ):
            os.remove(f"{STORAGE_PATH}/datapoints/{self.data_1.uuid}.json")
        if os.path.exists(
            f"{STORAGE_PATH}/datapoints/{self.data_2.uuid}.json"
        ):
            os.remove(f"{STORAGE_PATH}/datapoints/{self.data_2.uuid}.json")

    def test_mobile_sync_specific_administration(self):
        response = self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("total", data)
        self.assertIn("data", data)
        self.assertEqual(data["total"], 1)

        self.assertEqual(data["data"][0]["id"], self.data_1.id)

        # Ensure that form data from other administration is not included
        self.assertNotIn(
            self.data_2.id,
            [item["id"] for item in data["data"]]
        )
