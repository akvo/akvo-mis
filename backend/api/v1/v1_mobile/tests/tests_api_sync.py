from django.test import TestCase
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import (
    Administration,
    Levels,
)
from django.core.management import call_command
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData, Answers
from rest_framework import status


class MobileAssignmentApiSyncTest(
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

        # Create approver user
        self.create_user(
            email="approver.123@test.com",
            administration=self.administration,
            role_level=self.IS_APPROVER,
            form=self.form,
        )

        # Create admnin user
        self.user = self.create_user(
            email="test@test.org",
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

    def test_get_form_details(self):
        token = self.get_assignment_token(self.passcode)
        response = self.client.get(
            f"/api/v1/device/form/{self.form.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        cascades = [
            q
            for q in data["question_group"][0]["question"]
            if q["type"] in ("cascade", "administration")
        ]
        self.assertEqual(
            cascades[0]["source"]["parent_id"],
            [adm.id for adm in self.administration_children],
        )

    def test_mobile_sync_to_pending_datapoint(self):
        token = self.get_assignment_token(self.passcode)
        response = self.client.get(
            f"/api/v1/device/form/{self.form.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_form = response.json()
        questions = []
        for question_group in json_form["question_group"]:
            for question in question_group["question"]:
                questions.append(question)

        answers = {}
        for question in questions:
            if question["type"] == "option":
                answers[question["id"]] = [question["option"][0]["value"]]
            elif question["type"] == "multiple_option":
                answers[question["id"]] = [question["option"][0]["value"]]
            elif question["type"] == "number":
                answers[question["id"]] = 12
            elif question["type"] == "geo":
                answers[question["id"]] = [0, 0]
            elif question["type"] == "date":
                answers[question["id"]] = "2021-01-01T00:00:00.000Z"
            elif question["type"] == "image":
                answers[question["id"]] = "https://picsum.photos/200/300"
            elif question["type"] in ("cascade", "administration"):
                answers[question["id"]] = self.administration.id
            else:
                answers[question["id"]] = "testing"

        post_data = {
            "formId": self.form.id,
            "name": "testing datapoint",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": answers,
        }
        self.assertEqual(len(answers), len(questions))

        response = self.client.post(
            "/api/v1/device/sync",
            post_data,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        pending_data = FormData.objects.filter(
            created_by=self.user,
            is_pending=True
        ).all()
        self.assertEqual(pending_data.count(), 1)
        answer_data = Answers.objects.filter(
            data=pending_data[0]
        ).count()
        self.assertEqual(answer_data, len(list(answers)))
        self.assertTrue(pending_data[0].geo, [0, 0])
        self.assertEqual(
            pending_data[0].submitter, self.mobile_assignment.name
        )
        self.assertEqual(pending_data[0].duration, 3000)

        # Submit with invalid token
        response = self.client.post(
            "/api/v1/device/sync",
            post_data,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": "Bearer eyjsomethinginvalid"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Submit invalid request
        response = self.client.post(
            "/api/v1/device/sync",
            {},  # everything is is empty
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.post(
            "/api/v1/device/sync",
            {"formId": self.form.id},  # required params is incomplete
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Submit with invalid data
        response = self.client.post(
            "/api/v1/device/sync",
            {
                "formId": self.form.id,
                "name": "testing datapoint",
                "duration": 3000,
                "submittedAt": "2021-01-01T00:00:00.000Z",
                "geo": [0, 0],
                "answers": {"1": "testing"},
            },  # data is empty
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
