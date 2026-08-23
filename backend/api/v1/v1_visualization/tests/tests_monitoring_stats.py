from django.test.utils import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_forms.models import Forms, Questions, QuestionGroup
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from django.core.management import call_command
from datetime import datetime
from django.utils.timezone import make_aware
from rest_framework_simplejwt.tokens import RefreshToken


@override_settings(USE_TZ=False, TEST_ENV=True)
class MonitoringStatsAPITest(APITestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        self.user = SystemUser.objects.create_user(
            email="test@test.org",
            password="test1234",
            first_name="test",
            last_name="testing",
        )
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()

        self.registration = Forms.objects.create(
            id=8000,
            name="Registration Form",
            parent=None,
        )
        self.monitoring = Forms.objects.create(
            name="Monitoring Form",
            parent=self.registration,
        )

        self.reg_data = FormData.objects.create(
            created=make_aware(datetime(2023, 8, 1)),
            administration=self.administration,
            created_by=self.user,
            form=self.registration,
        )

        self.monitoring_data = FormData.objects.create(
            parent=self.reg_data,
            administration=self.administration,
            created_by=self.user,
            form=self.monitoring,
        )
        # Manually update the created field after creation to bypass
        # auto_now_add
        FormData.objects.filter(id=self.monitoring_data.id).update(
            created=make_aware(datetime(2023, 8, 1))
        )
        self.monitoring_data.refresh_from_db()

        self.question_group = QuestionGroup.objects.create(
            form=self.monitoring, name="qg_1"
        )

        self.question = Questions.objects.create(
            question_group=self.question_group,
            form=self.monitoring,
            name="question_x",
            type=QuestionTypes.number,
        )

        self.date_question = Questions.objects.create(
            question_group=self.question_group,
            form=self.monitoring,
            name="monitoring_date",
            type=QuestionTypes.date,
        )

        Answers.objects.create(
            value=1,
            data=self.monitoring_data,
            question=self.question,
            question_id=self.question.id,
            created_by=self.user,
        )
        self.answer_date = "2025-06-01T07:19:32.243Z"
        Answers.objects.create(
            name=self.answer_date,
            data=self.monitoring_data,
            question=self.date_question,
            created_by=self.user,
        )

        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_stats_without_question_date(self):
        url = (
            f"/api/v1/visualization/monitoring-stats/"
            f"?parent_id={self.reg_data.id}"
            f"&question_id={self.question.id}"
        )
        response = self.client.get(url)
        # The API uses formdata.created date, set to 2023-08-01 in setUp
        expected_date = "01-08-2023"
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(), [{"date": expected_date, "value": 1}]
        )

    def test_stats_with_question_date(self):
        url = (
            f"/api/v1/visualization/monitoring-stats/"
            f"?parent_id={self.reg_data.id}"
            f"&question_id={self.question.id}"
            f"&question_date={self.date_question.id}"
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [{"date": "01-06-2025", "value": 1}])

    def test_missing_params(self):
        url = "/api/v1/visualization/monitoring-stats/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
