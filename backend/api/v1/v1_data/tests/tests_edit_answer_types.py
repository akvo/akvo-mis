from django.core.management import call_command
from django.test import TestCase, override_settings

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from rest_framework import status


@override_settings(USE_TZ=False, TEST_ENV=True)
class EditAnswerTypesTestCase(TestCase):
    """Editing an answer must map it onto the same columns as creating it.

    The two PUT endpoints used to carry their own copy of the dispatch,
    missing the cascade and autofield branches. Both failures were silent
    at the API and visible only in the database.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        # The seeded superuser. PUT /form-data requires IsEditor, which
        # short-circuits to True for superusers.
        login = self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.token = login.json().get("token")
        self.user = SystemUser.objects.get(email="admin@akvo.org")
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.form = Forms.objects.create(name="Edit Form", version=1)
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )
        self.cascade_q = Questions.objects.create(
            form=self.form, question_group=self.group, name="adm",
            label="Administration", order=1,
            type=QuestionTypes.cascade,
            api={"endpoint": "/api/v1/administration"},
        )
        self.autofield_q = Questions.objects.create(
            form=self.form, question_group=self.group, name="auto",
            label="Auto", order=2, type=QuestionTypes.autofield,
        )
        self.data = FormData.objects.create(
            name="Datapoint", form=self.form,
            administration=self.administration, created_by=self.user,
        )
        Answers.objects.create(
            data=self.data, question=self.cascade_q,
            name=self.administration.name, value=self.administration.id,
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.data, question=self.autofield_q,
            name="original", created_by=self.user,
        )

    def put_answers(self, payload):
        return self.client.put(
            f"/api/v1/form-data/{self.form.id}?data_id={self.data.id}",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )

    def test_editing_cascade_keeps_its_label(self):
        """The bug: name was set to None, wiping the administration label."""
        child = Administration.objects.filter(
            parent=self.administration
        ).first()
        response = self.put_answers(
            [{"question": self.cascade_q.id, "value": child.id}]
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        answer = Answers.objects.get(data=self.data, question=self.cascade_q)
        self.assertEqual(answer.name, child.name)
        self.assertEqual(answer.value, child.id)

    def test_editing_autofield_stores_a_string_not_a_float(self):
        """The bug: a string was assigned to Answers.value, a FloatField."""
        response = self.put_answers(
            [{"question": self.autofield_q.id, "value": "recomputed"}]
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        answer = Answers.objects.get(data=self.data, question=self.autofield_q)
        self.assertEqual(answer.name, "recomputed")
        self.assertIsNone(answer.value)
