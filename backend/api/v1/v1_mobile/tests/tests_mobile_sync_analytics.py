from unittest import mock
from django.test import TestCase
from django.core.management import call_command
from rest_framework import status

from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import Tenant


class MobileSyncAnalyticsTest(
    TestCase, AssignmentTokenTestHelperMixin, ProfileTestHelperMixin
):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.tenant = Tenant.objects.create(
            subdomain="analytics-ws",
        )

        adm_level = Levels.objects.filter(level__gt=0).order_by("?").first()
        self.administration = Administration.objects.filter(
            level=adm_level
        ).order_by("?").last()
        self.form = Forms.objects.filter(parent__isnull=True).first()
        self.form.tenant = self.tenant
        self.form.save()

        self.user = self.create_user(
            email="enumerator@analytics-ws.org",
            administration=self.administration,
            role_level=self.IS_ADMIN,
            form=self.form,
        )
        self.user.tenant = self.tenant
        self.user.save()

        self.passcode = "passcode-analytics"
        MobileAssignment.objects.create_assignment(
            user=self.user,
            name="Enumerator Assignment",
            passcode=self.passcode,
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.administration_children = Administration.objects.filter(
            parent=self.administration
        ).all()
        self.mobile_assignment.administrations.add(
            *self.administration_children
        )
        self.mobile_assignment.administrations.add(self.administration)
        self.mobile_assignment.forms.add(self.form)
        self.token = self.get_assignment_token(self.passcode)

    def _build_answers(self):
        json_form = self.client.get(
            f"/api/v1/device/form/{self.form.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        ).json()
        questions = []
        for question_group in json_form.get("question_group", []):
            for question in question_group.get("question", []):
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
        return answers

    @mock.patch("api.v1.v1_mobile.views.async_task")
    def test_mobile_sync_triggers_matomo_async_task(self, mock_async_task):
        token = self.get_assignment_token(self.passcode)
        payload = {
            "formId": self.form.id,
            "name": "Datapoint 1",
            "duration": 120,
            "submittedAt": "2026-10-09T00:00:00.000Z",
            "geo": [1.23, 4.56],
            "answers": self._build_answers(),
        }
        res = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_async_task.assert_called_with(
            "utils.matomo.track_submission_task",
            tenant_name="analytics-ws",
            form_name=self.form.name,
            form_id=self.form.id,
            source="mobile",
            user_id=str(self.user.id),
            subdomain="analytics-ws",
        )

    @mock.patch("api.v1.v1_mobile.views.async_task")
    def test_mobile_draft_sync_does_not_trigger_matomo(self, mock_async_task):
        token = self.get_assignment_token(self.passcode)
        payload = {
            "formId": self.form.id,
            "name": "Draft Datapoint",
            "duration": 50,
            "answers": {},
        }
        res = self.client.post(
            "/api/v1/device/sync?is_draft=true",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for call_item in mock_async_task.call_args_list:
            self.assertNotEqual(
                call_item[0][0], "utils.matomo.track_submission_task"
            )
