from django.test import TestCase
from api.v1.v1_profile.models import Levels
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from django.core.management import call_command
from rest_framework import status
from utils.custom_helper import CustomPasscode


class MobileAssignmentApiSyncRepeatGroupTest(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_user_seeder", "--repeat", 5, "--test", 1)

        adm_level = Levels.objects.order_by("-level")[1:2].first()
        self.form = Forms.objects.get(pk=4)
        user = SystemUser.objects.filter(
            user_user_role__administration__level=adm_level,
        ).first()

        # Create approver based on the user's administration
        user_adm = user.user_user_role.order_by("?").first().administration
        self.create_user(
            email="approver.123@test.com",
            role_level=self.IS_APPROVER,
            administration=user_adm,
            form=self.form,
        )

        # Create a mobile assignment for the user
        mobile_user = user.mobile_assignments.create(
            name="Test mobile",
            passcode=CustomPasscode().encode("123456"),
        )
        # Assign administration to the mobile assignment
        mobile_user.administrations.add(
            user_adm
        )
        # Assign form to the mobile assignment
        mobile_user.forms.add(self.form)

        self.mobile_user = mobile_user
        self.code = CustomPasscode().decode(
            encoded_passcode=self.mobile_user.passcode
        )
        res = self.client.post(
            "/api/v1/device/auth",
            {"code": self.code},
            content_type="application/json",
        )
        data = res.json()
        self.token = data["syncToken"]

    def test_success_save_repeated_values(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "data example-4 #1",
            "duration": 1,
            "submittedAt": "2025-05-16T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                442: "John Doe",
                443: "/attachment/screenshot_likes_uuid23323.jpeg",
                444: "/attachments/my_works_uuid12333.pdf",
                445: "/attachment/application_letter_2024-04-29.pdf",
                446: mobile_adm.id,
                551: "data:base64,examplesignature122323",
                661: "Good Job",
                "661-1": "Nice!",
                "661-2": "Looks good to me",
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        pending_form_data = FormData.objects.filter(
            form=self.form,
            name=payload["name"],
            submitter=self.mobile_user.name,
            is_pending=True
        ).first()

        self.assertIsNotNone(pending_form_data)

        repeat_answers = Answers.objects.filter(
            question__pk=661,
            data=pending_form_data
        ).all()
        self.assertEqual(repeat_answers.count(), 3)
        # Check all repeated answers index list
        self.assertEqual(
            list(
                repeat_answers.values_list("index", flat=True)
                .order_by("index")
            ),
            [0, 1, 2]
        )
