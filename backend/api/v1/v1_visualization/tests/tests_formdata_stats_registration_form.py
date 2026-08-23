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
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormDataStatsRegistrationFormAPITestCases(
    APITestCase,
    ProfileTestHelperMixin
):
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

        self.base_url = (
            f"/api/v1/visualization/formdata-stats/{self.registration.id}"
        )

        self.question_group = QuestionGroup.objects.create(
            form=self.registration, name="qg_1"
        )
        # Create questions for the monitoring form
        # Number question
        self.number_question = Questions.objects.create(
            id=8101,
            question_group=self.question_group,
            form=self.registration,
            name="test_number_question",
            type=QuestionTypes.number,
        )
        # Option question
        self.option_question = Questions.objects.create(
            id=8102,
            question_group=self.question_group,
            form=self.registration,
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
            form=self.registration,
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
        adm = Administration.objects.filter(
            level__level=4
        ).order_by('?').first()

        # Create registration data 1
        self.reg_data = FormData.objects.create(
            id=9100,
            geo=[-18.1190718, 178.4504677],
            uuid="21796178-d317-40d3-95e2-f3bbecca047c",
            name="Registration Data",
            administration=adm,
            created_by=self.user,
            form=self.registration,
        )
        self.reg_data.created = make_aware(datetime(2025, 8, 1))
        self.reg_data.save()
        self.reg_data.refresh_from_db()
        self.create_data(
            form_data=self.reg_data,
            answers={
                'number_question': 11,
                'option_question': 'option_1',
                'multiple_option_question': [
                    'multiple_option_3', 'multiple_option_2'
                ]
            }
        )
        # Create registration data 2
        self.reg_data_2 = FormData.objects.create(
            id=9101,
            geo=[-18.1175162, 178.4478261],
            uuid="c7275b7e-b654-43b1-a5c9-8e3b98019414",
            name="Registration Data 2",
            administration=adm,
            created_by=self.user,
            form=self.registration,
        )
        self.reg_data_2.created = make_aware(datetime(2025, 8, 11))
        self.reg_data_2.save()
        self.reg_data_2.refresh_from_db()
        self.create_data(
            form_data=self.reg_data_2,
            answers={
                'number_question': 21,
                'option_question': 'option_2',
                'multiple_option_question': [
                    'multiple_option_1', 'multiple_option_2'
                ]
            }
        )

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
        reg_data = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data), 1)
        self.assertEqual(len(reg_data_2), 1)

        self.assertEqual(
            reg_data[0]["value"],
            810201
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
        reg_data = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data), 2)
        self.assertEqual(len(reg_data_2), 2)

        self.assertCountEqual(
            [d["value"] for d in reg_data],
            [810302, 810303]
        )
        self.assertCountEqual(
            [d["value"] for d in reg_data_2],
            [810301, 810302]
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
        reg_data = list(filter(
            lambda x: x["id"] == 9100, data["data"]
        ))
        reg_data_2 = list(filter(
            lambda x: x["id"] == 9101, data["data"]
        ))
        self.assertEqual(len(reg_data), 1)
        self.assertEqual(len(reg_data_2), 1)

        self.assertEqual(
            reg_data[0]["value"],
            11
        )
        self.assertEqual(
            reg_data_2[0]["value"],
            21
        )

    def create_data(
        self,
        form_data,
        answers,
    ):
        for question_attr, answer_value in answers.items():
            question = getattr(self, question_attr, None)
            if not question:
                continue

            if question.type == QuestionTypes.number:
                form_data.data_answer.create(
                    question=question,
                    value=answer_value,
                    created_by=self.user,
                    index=0,
                )
            elif question.type == QuestionTypes.option:
                option = question.options.get(value=answer_value)
                form_data.data_answer.create(
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
                    form_data.data_answer.create(
                        question=question,
                        created_by=self.user,
                        index=0,
                        options=options,
                    )

        return form_data
