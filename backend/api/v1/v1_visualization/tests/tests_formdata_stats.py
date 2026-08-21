from django.core.management import call_command
from django.test.utils import override_settings
from rest_framework.test import APITestCase
from django.utils.timezone import make_aware
from datetime import datetime
from rest_framework_simplejwt.tokens import RefreshToken
from api.v1.v1_profile.models import Administration
from api.v1.v1_forms.models import (
    Forms,
    QuestionTypes,
    Questions,
    QuestionGroup,
)
from api.v1.v1_data.models import FormData
from api.v1.v1_visualization.functions import refresh_materialized_data
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormDataStatsAPITestCases(APITestCase, ProfileTestHelperMixin):
    def setUp(self):
        super().setUp()
        self.maxDiff = None
        call_command("administration_seeder", "--test")

        # Create a new superuser
        self.user = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )

        self.registration = Forms.objects.create(
            id=8100,
            name="Registration Form",
            parent=None,
        )
        self.monitoring = Forms.objects.create(
            name="Monitoring Form",
            parent=self.registration,
        )

        self.base_url = (
            f"/api/v1/visualization/formdata-stats/{self.monitoring.id}"
        )

        self.question_group = QuestionGroup.objects.create(
            form=self.monitoring, name="qg_1"
        )
        # Create questions for the monitoring form
        # Number question
        self.number_question = Questions.objects.create(
            id=8101,
            question_group=self.question_group,
            form=self.monitoring,
            name="test_number_question",
            type=QuestionTypes.number,
        )
        # Option question
        self.option_question = Questions.objects.create(
            id=8102,
            question_group=self.question_group,
            form=self.monitoring,
            name="test_option_question",
            type=QuestionTypes.option,
        )
        self.option_question.options.create(
            id=810201,
            order=1,
            label="Option 1",
            value="option_1",
        )
        self.option_question.options.create(
            id=810202,
            order=2,
            label="Option 2",
            value="option_2",
        )
        # Multiple option question
        self.multiple_option_question = Questions.objects.create(
            id=8103,
            question_group=self.question_group,
            form=self.monitoring,
            name="test_multiple_option_question",
            type=QuestionTypes.multiple_option,
        )
        self.multiple_option_question.options.create(
            id=810301,
            order=1,
            label="Multiple Option 1",
            value="multiple_option_1",
            color="red",
        )
        self.multiple_option_question.options.create(
            id=810302,
            order=2,
            label="Multiple Option 2",
            value="multiple_option_2",
            color="blue",
        )
        self.multiple_option_question.options.create(
            id=810303,
            order=3,
            label="Multiple Option 3",
            value="multiple_option_3",
            color="green",
        )

        # Create a new data registration 1 and the monitoring data
        adm = Administration.objects.filter(
            level__level=4
        ).order_by('?').first()
        self.reg_data_1 = FormData.objects.create(
            id=9100,
            geo=[-18.1190718, 178.4504677],
            uuid="21796178-d317-40d3-95e2-f3bbecca047c",
            name="Registration Data",
            administration=adm,
            created_by=self.user,
            form=self.registration,
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_1,
            created_date=datetime(2025, 8, 1),
            answers={
                'number_question': 1,
                'option_question': 'option_1',
                'multiple_option_question': [
                    'multiple_option_1', 'multiple_option_2'
                ]
            }
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_1,
            created_date=datetime(2025, 8, 5),
            answers={
                'number_question': 2,
                'option_question': 'option_2',
                'multiple_option_question': [
                    'multiple_option_2', 'multiple_option_3'
                ]
            }
        )

        # Create a new data registration 2 and the monitoring data
        self.reg_data_2 = FormData.objects.create(
            id=9101,
            geo=[-18.1175162, 178.4478261],
            uuid="c7275b7e-b654-43b1-a5c9-8e3b98019414",
            name="Registration Data 2",
            administration=adm,
            created_by=self.user,
            form=self.registration,
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_2,
            created_date=datetime(2025, 8, 10),
            answers={
                'number_question': 3,
                'option_question': 'option_1',
                'multiple_option_question': [
                    'multiple_option_2', 'multiple_option_3'
                ]
            }
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_2,
            created_date=datetime(2025, 8, 15),
            answers={
                'number_question': 4,
                'option_question': 'option_2',
                'multiple_option_question': [
                    'multiple_option_1', 'multiple_option_3'
                ]
            }
        )
        # Refresh the materialized view
        refresh_materialized_data()

        # Every endpoint in this app now requires authentication
        # (VIZ-003). This module doesn't use VisualizationValuesTestMixin,
        # so it needs its own credential.
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_form_data_stats_with_option_type_question(self):
        response = self.client.get(
            f"{self.base_url}/?question_id={self.option_question.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("options", data)
        self.assertIn("data", data)

        self.assertTrue(isinstance(data["data"], list))
        self.assertEqual(len(data["data"]), 2)

        self.assertEqual(
            data["options"],
            [
                {
                    "id": 810201,
                    "label": "Option 1",
                    "color": None,
                },
                {
                    "id": 810202,
                    "label": "Option 2",
                    "color": None,
                }
            ]
        )
        # filter data based on registration data id
        reg_data_1 = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data_1), 1)
        self.assertEqual(len(reg_data_2), 1)

        self.assertEqual(
            reg_data_1[0]["value"],
            810202
        )
        self.assertEqual(
            reg_data_2[0]["value"],
            810202
        )

    def test_form_data_stats_with_multiple_option_type_question(self):
        response = self.client.get(
            f"{self.base_url}/?question_id={self.multiple_option_question.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("options", data)
        self.assertIn("data", data)

        self.assertTrue(isinstance(data["data"], list))
        self.assertEqual(len(data["data"]), 4)

        self.assertEqual(
            data["options"],
            [
                {
                    "id": 810301,
                    "label": "Multiple Option 1",
                    "color": "red",
                },
                {
                    "id": 810302,
                    "label": "Multiple Option 2",
                    "color": "blue",
                },
                {
                    "id": 810303,
                    "label": "Multiple Option 3",
                    "color": "green",
                }
            ]
        )
        # filter data based on registration data id
        reg_data_1 = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data_1), 2)
        self.assertEqual(len(reg_data_2), 2)

        self.assertCountEqual(
            [d["value"] for d in reg_data_1],
            [810302, 810303]
        )
        self.assertCountEqual(
            [d["value"] for d in reg_data_2],
            [810301, 810303]
        )

    def test_form_data_stats_with_number_type_question(self):
        response = self.client.get(
            f"{self.base_url}/?question_id={self.number_question.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 2)

        self.assertEqual(data["options"], [])

        # filter data based on registration data id
        reg_data_1 = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data_1), 1)
        self.assertEqual(len(reg_data_2), 1)

        self.assertEqual(
            reg_data_1[0]["value"],
            2
        )
        self.assertEqual(
            reg_data_2[0]["value"],
            4
        )

    def test_form_data_stats_with_invalid_question_id(self):
        response = self.client.get(
            f"{self.base_url}/?question_id=9999"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(
            data["message"],
            'Invalid pk "9999" - object does not exist.'
        )

    def test_form_data_stats_with_invalid_form_id(self):
        response = self.client.get(
            "/api/v1/visualization/formdata-stats/9999"
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["detail"], "Not found.")

    def test_form_data_stats_without_question_id(self):
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(data["message"], "question_id is required.")

    def test_form_data_stats_without_form_id(self):
        response = self.client.get(
            "/api/v1/visualization/formdata-stats/"
        )
        self.assertEqual(response.status_code, 404)

    def test_form_data_stats_with_non_supported_question_type(self):
        # Create a new question with an unsupported type
        unsupported_question = Questions.objects.create(
            id=8104,
            question_group=self.question_group,
            form=self.monitoring,
            name="test_unsupported_question",
            type=QuestionTypes.text,
        )
        response = self.client.get(
            f"{self.base_url}/?question_id={unsupported_question.id}"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(
            data["message"],
            'Invalid pk "8104" - object does not exist.'
        )

    def test_form_data_stats_with_multiple_monitoring_forms(self):
        # Create another monitoring form
        another_monitoring = Forms.objects.create(
            name="Another Monitoring Form",
            parent=self.registration,
        )
        another_group = QuestionGroup.objects.create(
            form=another_monitoring, name="another_qg_1"
        )
        self.another_question = Questions.objects.create(
            id=8105,
            question_group=another_group,
            form=another_monitoring,
            name="test_another_question",
            type=QuestionTypes.number,
        )
        self.another_option_question = Questions.objects.create(
            id=8106,
            question_group=another_group,
            form=another_monitoring,
            name="test_another_option_question",
            type=QuestionTypes.option,
        )
        self.another_option_question.options.create(
            id=810601,
            order=1,
            label="Another Option 1",
            value="another_option_1",
        )
        self.another_option_question.options.create(
            id=810602,
            order=2,
            label="Another Option 2",
            value="another_option_2",
        )

        # Create monitoring data for the new form
        self.create_monitoring_data(
            parent_data=self.reg_data_1,
            created_date=datetime(2025, 8, 20),
            answers={
                'another_question': 5,
                'another_option_question': 'another_option_1',
            },
            form=another_monitoring,
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_1,
            created_date=datetime(2025, 8, 25),
            answers={
                'another_question': 21,
                'another_option_question': 'another_option_1',
            },
            form=another_monitoring,
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_2,
            created_date=datetime(2025, 8, 20),
            answers={
                'another_question': 6,
                'another_option_question': 'another_option_2',
            },
            form=another_monitoring,
        )
        self.create_monitoring_data(
            parent_data=self.reg_data_2,
            created_date=datetime(2025, 8, 25),
            answers={
                'another_question': 77,
                'another_option_question': 'another_option_1',
            },
            form=another_monitoring,
        )

        # Refresh the materialized view for the new form
        refresh_materialized_data()

        response = self.client.get(
            f"/api/v1/visualization/formdata-stats/{another_monitoring.id}/"
            f"?question_id={self.another_question.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)

        # filter data based on registration data id
        reg_data_1 = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data_1), 1)
        self.assertEqual(len(reg_data_2), 1)

        self.assertEqual(
            reg_data_1[0]["value"],
            21
        )
        self.assertEqual(
            reg_data_2[0]["value"],
            77
        )

        response = self.client.get(
            f"/api/v1/visualization/formdata-stats/{another_monitoring.id}/"
            f"?question_id={self.another_option_question.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)

        self.assertIn("options", data)
        self.assertTrue(isinstance(data["data"], list))
        self.assertEqual(len(data["data"]), 2)

        # filter data based on registration data id
        reg_data_1 = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data_1), 1)
        self.assertEqual(len(reg_data_2), 1)

        self.assertEqual(
            reg_data_1[0]["value"],
            810601
        )
        self.assertEqual(
            reg_data_2[0]["value"],
            810601
        )

    def create_monitoring_data(
        self,
        parent_data,
        created_date,
        answers=None,
        form=None,
    ):
        monitoring_data = FormData.objects.create(
            geo=parent_data.geo,
            uuid=parent_data.uuid,
            parent=parent_data,
            administration=parent_data.administration,
            created_by=self.user,
            form=form if form else self.monitoring,
        )

        if created_date:
            monitoring_data.created = make_aware(created_date)
            monitoring_data.save()
            monitoring_data.refresh_from_db()

        if answers:
            for question_attr, answer_value in answers.items():
                question = getattr(self, question_attr, None)
                if not question:
                    continue

                if question.type == QuestionTypes.number:
                    monitoring_data.data_answer.create(
                        question=question,
                        value=answer_value,
                        created_by=self.user,
                        index=0,
                    )
                elif question.type == QuestionTypes.option:
                    option = question.options.get(value=answer_value)
                    monitoring_data.data_answer.create(
                        question=question,
                        created_by=self.user,
                        index=0,
                        options=[option.value],
                    )
                elif question.type == QuestionTypes.multiple_option:
                    if isinstance(answer_value, list):
                        options = [
                            question.options.get(value=value).value
                            for value in answer_value
                        ]
                        monitoring_data.data_answer.create(
                            question=question,
                            created_by=self.user,
                            index=0,
                            options=options,
                        )

        return monitoring_data
