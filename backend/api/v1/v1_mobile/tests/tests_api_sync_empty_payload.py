from django.test import TestCase
from api.v1.v1_profile.models import Levels
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser
from django.core.management import call_command
from api.v1.v1_data.models import FormData, Answers
from rest_framework import status
from utils.custom_helper import CustomPasscode


class MobileAssignmentApiSyncEmptyPayloadTest(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_user_seeder", "--repeat", 5, "--test", 1)

        adm_level = Levels.objects.order_by("-level")[1:2].first()
        self.form = Forms.objects.get(pk=1)
        user = SystemUser.objects.filter(
            user_user_role__administration__level=adm_level,
        ).first()

        # Create a mobile assignment for the user
        mobile_user = user.mobile_assignments.create(
            name="Test mobile",
            passcode=CustomPasscode().encode("123456"),
        )
        # Assign administration to the mobile assignment
        mobile_user.administrations.add(
            user.user_user_role.order_by("?").first().administration
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

    def test_empty_required_text_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                102: ["female"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo.jpeg",
                108: "2024-04-29",
                109: 0.6,
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_required_number_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John Doe",
                102: ["male"],
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo.jpeg",
                108: "2024-04-29",
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_allowed_zero_required_number_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "Jane Doe",
                102: ["female"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo.jpeg",
                108: "2024-04-29",
                109: 0,
                114: ["no"],
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
        pending_data = FormData.objects.last()
        self.assertTrue(pending_data.id)

        a_109 = Answers.objects.filter(
            question_id=109, data_id=pending_data.id
        ).first()
        self.assertTrue(a_109)
        self.assertEqual(a_109.value, 0)
        total_null_answers = Answers.objects.filter(
            data=pending_data,
            name__isnull=True,
            value__isnull=True,
            options__isnull=True,
        ).count()
        self.assertEqual(total_null_answers, 0)

    def test_empty_required_option_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John Doe",
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                107: "photo.jpeg",
                108: "2024-04-29",
                109: 0.6,
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_required_multiple_options_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John Doe",
                102: ["male"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                107: "photo.jpeg",
                108: "2024-04-29",
                109: 0.6,
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_required_geo_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John Doe",
                102: ["male"],
                103: 62723817,
                104: mobile_adm.id,
                106: ["children"],
                107: "photo.jpeg",
                108: "2024-04-29",
                109: 0.6,
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_non_required_autofield_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John",
                102: ["male"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo.jpeg",
                108: "2024-04-29",
                109: 0.6,
                114: ["no"],
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
        pending_data = FormData.objects.last()
        self.assertTrue(pending_data.id)
        a_111 = Answers.objects.filter(
            question_id=111, data_id=pending_data.id
        ).first()
        self.assertFalse(a_111)
        total_null_answers = Answers.objects.filter(
            data=pending_data,
            name__isnull=True,
            value__isnull=True,
            options__isnull=True,
        ).count()
        self.assertEqual(total_null_answers, 0)

    def test_empty_required_photo_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John Doe",
                102: ["male"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                108: "2024-04-29",
                109: 7.6,
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_required_date_type_of_question(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "Jane Doe",
                102: ["female"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo-123.jpeg",
                109: 7.6,
                114: ["no"],
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_pending_answers_for_all_questions(self):
        mobile_adm = self.mobile_user.administrations.first()
        payload = {
            "formId": self.form.id,
            "name": "datapoint #1",
            "duration": 1,
            "submittedAt": "2024-04-29T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "Jane Doe",
                102: ["female"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo-123.jpeg",
                108: "2024-04-29",
                109: 5.1,
                111: "10.2",
                114: ["no"],
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
        pending_data = FormData.objects.last()
        self.assertTrue(pending_data.id)
        self.assertEqual(pending_data.data_answer.count(), 11)

        a_101 = pending_data.data_answer.filter(
            question_id=101
        ).first()
        a_102 = pending_data.data_answer.filter(
            question_id=102
        ).first()
        a_103 = pending_data.data_answer.filter(
            question_id=103
        ).first()
        a_104 = pending_data.data_answer.filter(
            question_id=104
        ).first()
        a_105 = pending_data.data_answer.filter(
            question_id=105
        ).first()
        a_106 = pending_data.data_answer.filter(
            question_id=106
        ).first()
        a_107 = pending_data.data_answer.filter(
            question_id=107
        ).first()
        a_108 = pending_data.data_answer.filter(
            question_id=108
        ).first()
        a_109 = pending_data.data_answer.filter(
            question_id=109
        ).first()
        a_111 = pending_data.data_answer.filter(
            question_id=111
        ).first()
        a_114 = pending_data.data_answer.filter(
            question_id=114
        ).first()
        self.assertEqual(a_101.name, "Jane Doe")
        self.assertEqual(a_102.options, ["female"])
        self.assertEqual(a_103.value, 62723817)
        self.assertEqual(a_104.value, mobile_adm.id)
        self.assertEqual(a_105.options, [6.2088, 106.8456])
        self.assertEqual(a_106.options, ["wife__husband__partner"])
        self.assertEqual(a_107.name, "photo-123.jpeg")
        self.assertEqual(a_108.name, "2024-04-29")
        self.assertEqual(a_109.value, 5.1)
        self.assertEqual(a_111.name, "10.2")
        self.assertEqual(a_114.options, ["no"])
