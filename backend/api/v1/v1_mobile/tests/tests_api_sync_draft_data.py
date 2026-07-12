import os
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
from api.v1.v1_data.models import FormData
from api.v1.v1_data.functions import add_fake_answers
from rest_framework import status
from mis.settings import STORAGE_PATH


class MobileAssignmentApiSyncNewDraftTest(
    TestCase, AssignmentTokenTestHelperMixin, ProfileTestHelperMixin
):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        adm_level = Levels.objects.filter(level=3).order_by("?").first()
        self.administration = Administration.objects.filter(
            level=adm_level
        ).order_by("?").last()
        self.geo = [-121.8863, 37.3382]
        self.uuid = "2f14a095-fb1e-48c1-ae13-d3ca8ba92cfe"

        self.form = Forms.objects.get(pk=1)

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
        self.user.set_password("test1234")
        self.user.save()

        self.user_token = self.get_auth_token(self.user.email, "test1234")

        passcode = "passcode1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.administration_children = Administration.objects.filter(
            parent=self.administration
        ).all()
        self.mobile_assignment.administrations.add(
            *self.administration_children
        )
        self.mobile_assignment.forms.add(self.form)
        self.mobile_token = self.get_assignment_token(passcode)

    def test_sync_new_draft(self):
        """
        Test creating a new draft submission.
        """
        payload = {
            "formId": self.form.id,
            "name": "New Draft #1",
            "duration": 2000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: "John Doe",
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["parent", "children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            "/api/v1/device/sync?is_draft=true",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        draft = FormData.objects_draft.first()
        self.assertIsNotNone(draft)
        # The device stores this id as draftId so its next save syncs as
        # ?id=<draft> (an update) instead of creating a duplicate draft.
        self.assertEqual(
            data,
            {"message": "ok", "id": draft.id},
        )

    def test_sync_update_existing_draft_with_form_and_uuid(self):
        # Create an initial draft submission
        draft = FormData.objects.create(
            form=self.form,
            name="Initial Draft",
            duration=1000,
            geo=self.geo,
            uuid=self.uuid,
            created_by=self.user,
            administration=self.administration,
        )
        draft.mark_as_draft()

        add_fake_answers(draft)

        draft.refresh_from_db()

        payload = {
            "formId": self.form.id,
            "name": "Update Draft #1",
            "duration": 3000,
            "submittedAt": "2025-07-03T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: "John Update",
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            "/api/v1/device/sync?is_draft=true",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(
            data,
            {"message": "ok", "id": draft.id},
        )
        draft_total = FormData.objects_draft.count()
        self.assertEqual(draft_total, 1)
        draft = FormData.objects_draft.first()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.name, "Update Draft #1")
        self.assertEqual(draft.duration, 3000)

        answer_101 = draft.data_answer.filter(question_id=101).first()
        self.assertIsNotNone(answer_101)
        self.assertEqual(answer_101.name, "John Update")

    def test_sync_update_existing_draft_with_param_id(self):
        # Create an initial draft submission
        draft = FormData.objects.create(
            form=self.form,
            name="Initial Draft",
            duration=1000,
            geo=self.geo,
            uuid=self.uuid,
            created_by=self.user,
            administration=self.administration,
        )
        draft.mark_as_draft()

        add_fake_answers(draft)

        draft.refresh_from_db()

        payload = {
            "formId": self.form.id,
            "name": "Update Draft #1",
            "duration": 3000,
            "submittedAt": "2025-07-03T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: "John With Param ID",
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }
        response = self.client.post(
            f"/api/v1/device/sync?is_draft=true&id={draft.id}",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(
            data,
            {"message": "ok", "id": draft.id},
        )

        draft_total = FormData.objects_draft.count()
        self.assertEqual(draft_total, 1)
        draft = FormData.objects_draft.first()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.name, "Update Draft #1")
        self.assertEqual(draft.duration, 3000)

        answer_101 = draft.data_answer.filter(question_id=101).first()
        self.assertIsNotNone(answer_101)
        self.assertEqual(answer_101.name, "John With Param ID")

    def test_sync_publish_draft(self):
        # Create an initial draft submission
        draft = FormData.objects.create(
            form=self.form,
            name="Initial Draft",
            duration=1000,
            geo=self.geo,
            uuid=self.uuid,
            created_by=self.user,
            administration=self.administration,
        )
        draft.mark_as_draft()

        add_fake_answers(draft)

        draft.refresh_from_db()

        payload = {
            "formId": self.form.id,
            "name": "Update Draft #1",
            "duration": 3000,
            "submittedAt": "2025-07-03T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: "John Update",
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            "/api/v1/device/sync?is_draft=true&is_published=true",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        published = FormData.objects.filter(
            form=self.form,
            uuid=self.uuid,
        ).first()
        self.assertIsNotNone(published)
        direct_to_data = (
            self.user.is_superuser or
            not published.has_approval
        )
        self.assertFalse(
            direct_to_data,
            "Published draft should not be direct to data"
        )

    def test_sync_publish_draft_with_generated_json(self):
        # Create a new superuser
        superuser = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )

        passcode = "super1234"
        mobile_assignment = MobileAssignment.objects.create_assignment(
            user=superuser,
            name="super.mobile",
            passcode=passcode
        )
        mobile_assignment.administrations.add(
            self.administration
        )
        mobile_assignment.forms.add(self.form)
        super_token = self.get_assignment_token(passcode)

        # Create an initial draft submission
        draft = FormData.objects.create(
            form=self.form,
            name="Initial Draft",
            duration=1000,
            geo=self.geo,
            uuid=self.uuid,
            created_by=superuser,
            administration=self.administration,
        )
        draft.mark_as_draft()

        add_fake_answers(draft)

        draft.refresh_from_db()

        payload = {
            "formId": self.form.id,
            "name": "Update Draft #1",
            "duration": 3500,
            "submittedAt": "2025-07-03T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: "Jane Update",
                102: ["female"],
                103: 616161,
                104: self.administration.id,
                105: self.geo,
                106: ["children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-15T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            f"/api/v1/device/sync?id={draft.id}&is_published=true",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {super_token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        published = FormData.objects.filter(
            form=self.form,
            uuid=self.uuid,
        ).first()
        self.assertIsNotNone(published)

        self.assertTrue(
            os.path.exists(
                f"{STORAGE_PATH}/datapoints/{published.uuid}.json"
            ),
            "File not exists"
        )
        os.remove(f"{STORAGE_PATH}/datapoints/{published.uuid}.json")

    def test_sync_new_draft_with_invalid_data(self):
        """
        Test creating a new draft submission with invalid data.
        """
        payload = {
            "formId": self.form.id,
            "name": "New Draft #2",
            "duration": 2000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: ["John"],  # Invalid name
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["parent", "children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            "/api/v1/device/sync?is_draft=true",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(
            data["message"],
            "Valid string value is required for Question:101",
        )

    def test_sync_update_draft_with_invalid_data(self):
        """
        Test updating an existing draft submission with invalid data.
        """
        # Create an initial draft submission
        draft = FormData.objects.create(
            form=self.form,
            name="Initial Draft",
            duration=1000,
            geo=self.geo,
            uuid=self.uuid,
            created_by=self.user,
            administration=self.administration,
        )
        draft.mark_as_draft()

        add_fake_answers(draft)

        draft.refresh_from_db()

        payload = {
            "formId": self.form.id,
            "name": "New Draft #2",
            "duration": 2000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: ["John"],  # Invalid name
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["parent", "children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            "/api/v1/device/sync?is_draft=true",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sync_update_draft_with_invalid_param_id(self):
        """
        Test updating an existing draft submission with an invalid param id.
        """
        # Create an initial draft submission
        draft = FormData.objects.create(
            form=self.form,
            name="Initial Draft",
            duration=1000,
            geo=self.geo,
            uuid=self.uuid,
            created_by=self.user,
            administration=self.administration,
        )
        draft.mark_as_draft()

        add_fake_answers(draft)

        draft.refresh_from_db()

        payload = {
            "formId": self.form.id,
            "name": "New Draft #2",
            "duration": 2000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": self.geo,
            "uuid": self.uuid,
            "answers": {
                101: "John invalid ID",
                102: ["male"],
                103: 6129912345,
                104: self.administration.id,
                105: self.geo,
                106: ["children"],
                107: "http://example.com/image.jpg",
                108: "2025-07-01T00:00:00.000Z",
                114: ["no"],
            },
        }

        response = self.client.post(
            "/api/v1/device/sync?is_draft=true&id=999999",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(
            data["message"],
            'Invalid pk "999999" - object does not exist.',
        )
