from django.test import TestCase
from django.core.management import call_command
from rest_framework import status

from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData


class MobileAssignmentDraftRejectionTest(
    TestCase, AssignmentTokenTestHelperMixin, ProfileTestHelperMixin
):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        adm_level = Levels.objects.filter(level__gt=0).order_by("?").first()
        self.administration = Administration.objects.filter(
            level=adm_level
        ).order_by("?").last()

        self.form = Forms.objects.filter(parent__isnull=True).first()

        self.user = self.create_user(
            email="mobile.tester@test.org",
            administration=self.administration,
            role_level=self.IS_ADMIN,
            form=self.form,
        )

        self.passcode = "passcode1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=self.passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.administration_children = Administration.objects.filter(
            parent=self.administration
        ).all()
        self.mobile_assignment.administrations.add(
            *self.administration_children
        )
        self.mobile_assignment.forms.add(self.form)
        self.token = self.get_assignment_token(self.passcode)

    def test_sync_with_is_draft_param_returns_400(self):
        initial_count = FormData.objects.count()
        payload = {
            "formId": self.form.id,
            "name": "Draft test",
            "duration": 100,
            "geo": [6.2088, 106.8456],
            "answers": {101: "Sample"},
        }
        response = self.client.post(
            "/api/v1/device/sync?is_draft=true",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json().get("message"),
            "Draft sync is no longer supported. Submit the form to sync it.",
        )
        self.assertEqual(FormData.objects.count(), initial_count)

    def test_sync_with_id_and_is_draft_param_returns_400(self):
        initial_count = FormData.objects.count()
        payload = {
            "formId": self.form.id,
            "name": "Draft test with id",
            "duration": 100,
            "geo": [6.2088, 106.8456],
            "answers": {101: "Sample"},
        }
        response = self.client.post(
            "/api/v1/device/sync?id=99999&is_draft=true",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json().get("message"),
            "Draft sync is no longer supported. Submit the form to sync it.",
        )
        self.assertEqual(FormData.objects.count(), initial_count)
