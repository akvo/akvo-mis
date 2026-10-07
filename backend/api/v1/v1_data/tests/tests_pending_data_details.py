from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_data.functions import add_fake_answers


@override_settings(USE_TZ=False, TEST_ENV=True)
class PendingDataDetailsTestCase(TestCase, ProfileTestHelperMixin):

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test")

        self.parent_form = Forms.objects.get(pk=1)
        self.form = self.parent_form.children.filter(pk=10002).first()
        self.administration = (
            Administration.objects.filter(
                level__level=3
            ).order_by("id").first()
        )
        self.geo = [7.2088, 126.8456]

        # Create a approver user
        self.approver = self.create_user(
            email="approver.123@test.com",
            role_level=self.IS_APPROVER,
            administration=self.administration,
            form=self.parent_form,
        )
        self.approver.set_password("test")
        self.approver.save()

        self.submitter = self.create_user(
            email="submitter@test.com",
            role_level=self.IS_ADMIN,
            password="test",
            administration=self.administration,
            form=self.form,
        )
        self.submitter.set_password("test")
        self.submitter.save()

        self.token = self.get_auth_token(self.submitter.email, "test")

        # create registration data
        registration_data = FormData.objects.create(
            name="New Registration Data",
            form=self.parent_form,
            created_by=self.submitter,
            administration=self.administration,
            geo=self.geo,
            is_pending=False,
        )
        add_fake_answers(registration_data)

        self.uuid = registration_data.uuid

        # create monitoring data #1
        monitoring_data = FormData.objects.create(
            parent=registration_data,
            name="Monitoring #1",
            form=self.form,
            created_by=self.submitter,
            administration=self.administration,
            geo=self.geo,
            is_pending=False,
        )
        add_fake_answers(monitoring_data)

        # create monitoring data #2
        monitoring_data_2 = FormData.objects.create(
            parent=registration_data,
            name="Monitoring #2",
            form=self.form,
            created_by=self.submitter,
            administration=self.administration,
            geo=self.geo,
            is_pending=False,
        )
        add_fake_answers(monitoring_data_2)

    def test_pending_data_number_overview(self):
        # create a new pending monitoring data
        payload = {
            "data": {
                "name": "New pending monitoring data",
                "administration": self.administration.id,
                "geo": self.geo,
                "uuid": self.uuid,
            },
            "answer": [
                {"question": 10121, "value": "2025-07-14"},
                {"question": 10122, "value": 99.2},
            ],
        }
        data = self.client.post(
            f"/api/v1/form-pending-data/{self.form.id}",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})

        last_pending_data = FormData.objects.filter(
            form=self.form, is_pending=True
        ).last()
        self.assertIsNotNone(last_pending_data)

        response = self.client.get(
            f"/api/v1/pending-data/{last_pending_data.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            list(data[0]),
            [
                "history",
                "question",
                "value",
                "last_value",
                "index",
            ],
        )
        # find question 10121 in the response
        question_10121 = next(
            (item for item in data if item["question"] == 10121), None
        )
        self.assertIsNotNone(question_10121)
        self.assertEqual(question_10121["value"], "2025-07-14")

        # find question 10122 in the response
        question_10122 = next(
            (item for item in data if item["question"] == 10122), None
        )
        self.assertIsNotNone(question_10122)
        self.assertEqual(question_10122["value"], 99.2)

    def test_get_pending_data_with_invalid_id(self):
        # Attempt to get pending data with an invalid ID
        response = self.client.get(
            "/api/v1/pending-data/9999999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["detail"], "Not found.")

    def test_get_pending_data_with_non_auth_header(self):
        payload = {
            "data": {
                "name": "New pending monitoring data",
                "administration": self.administration.id,
                "geo": self.geo,
                "uuid": self.uuid,
            },
            "answer": [
                {"question": 10121, "value": "2025-07-15"},
                {"question": 10122, "value": 72.6},
            ],
        }
        data = self.client.post(
            f"/api/v1/form-pending-data/{self.form.id}",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})

        last_pending_data = FormData.objects.filter(
            form=self.form, is_pending=True
        ).last()
        self.assertIsNotNone(last_pending_data)

        # Attempt to get pending data without an authorization header
        response = self.client.get(
            f"/api/v1/pending-data/{last_pending_data.id}",
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(
            data["detail"], "Authentication credentials were not provided."
        )
