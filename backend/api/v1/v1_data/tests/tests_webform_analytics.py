from unittest import mock
from django.test import TestCase
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import Administration
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_users.models import Tenant


class WebformAnalyticsTest(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.tenant = Tenant.objects.create(
            subdomain="web-analytics-ws",
        )
        self.form = Forms.objects.filter(parent__isnull=True).first()
        self.form.tenant = self.tenant
        self.form.save()

        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()

        self.user = self.create_user(
            email="webuser@analytics-ws.org",
            administration=self.administration,
            role_level=self.IS_SUPER_ADMIN,
            form=self.form,
        )
        self.user.tenant = self.tenant
        self.user.save()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _full_answer_payload(self):
        # Answer every question so the pending submit passes the
        # required-answers validation (HEAD tightened this gate).
        answers = []
        for q in self.form.form_questions.all().order_by("id"):
            if q.type == QuestionTypes.autofield:
                continue
            if q.type in (QuestionTypes.option, QuestionTypes.multiple_option):
                opt = q.options.first()
                value = [opt.value] if opt else []
            elif q.type == QuestionTypes.number:
                value = 12
            elif q.type == QuestionTypes.geo:
                value = [0.0, 0.0]
            elif q.type in (QuestionTypes.geoshape, QuestionTypes.geotrace):
                value = [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
            elif q.type == QuestionTypes.cascade:
                value = self.administration.id
            elif q.type == QuestionTypes.date:
                value = "2021-01-01"
            else:
                value = "testing"
            answers.append({"question": q.id, "value": value})
        return answers

    @mock.patch("api.v1.v1_data.views.async_task")
    def test_direct_form_data_submit_triggers_matomo(self, mock_async_task):
        first_q = self.form.form_questions.first()
        payload = {
            "data": {
                "name": "Web Datapoint 1",
                "administration": self.administration.id,
            },
            "answer": [
                {
                    "question": first_q.id,
                    "value": "Web Answer Value",
                }
            ],
        }
        res = self.client.post(
            f"/api/v1/form-data/{self.form.id}",
            data=payload,
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_async_task.assert_any_call(
            "utils.matomo.track_submission_task",
            tenant_name="web-analytics-ws",
            form_name=self.form.name,
            form_id=self.form.id,
            source="web",
            user_id=str(self.user.id),
            subdomain="web-analytics-ws",
        )

    @mock.patch("api.v1.v1_data.views.async_task")
    def test_pending_form_data_submit_triggers_matomo(self, mock_async_task):
        payload = {
            "data": {
                "name": "Pending Web Datapoint",
                "administration": self.administration.id,
            },
            "answer": self._full_answer_payload(),
        }
        res = self.client.post(
            f"/api/v1/form-pending-data/{self.form.id}",
            data=payload,
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_async_task.assert_any_call(
            "utils.matomo.track_submission_task",
            tenant_name="web-analytics-ws",
            form_name=self.form.name,
            form_id=self.form.id,
            source="web",
            user_id=str(self.user.id),
            subdomain="web-analytics-ws",
        )
