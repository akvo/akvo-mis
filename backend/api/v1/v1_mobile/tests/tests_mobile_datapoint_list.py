from mis.settings import WEBDOMAIN
from django.test import TestCase
from api.v1.v1_mobile.tests.mixins import DatapointFilesWrittenMixin
from django.core.management import call_command
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import (
    Administration,
)
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_data.functions import add_fake_answers
from rest_framework import status


class MobileDataPointDownloadListTestCase(
    DatapointFilesWrittenMixin, TestCase, ProfileTestHelperMixin
):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.forms = Forms.objects.filter(parent__isnull=True).all()
        self.user = self.create_user(
            email="test@test.org",
            role_level=self.IS_ADMIN,
            administration=self.administration,
        )
        for f in self.forms:
            self.user.user_form.create(
                form=f,
            )
            self.user.save()
        self.uuid = "uuid-1234-5678-9101"
        self.passcode = "passcode1234"
        self.mobile_assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="test", passcode=self.passcode
        )
        self.adm_children = self.administration.parent_administration.all()
        self.mobile_assignment.administrations.add(
            *self.adm_children
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.mobile_assignment.forms.add(*self.forms)
        self.form_data = FormData.objects.create(
            name="TEST",
            geo=None,
            form=self.forms[0],
            administration=self.adm_children.first(),
            created_by=self.user,
            uuid=self.uuid,
        )

    def test_get_datapoints_list_url(self):
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], self.form_data.id)
        self.assertEqual(data["data"][0]["name"], self.form_data.name)
        self.assertEqual(data["data"][0]["form_id"], self.forms[0].id)
        self.assertEqual(
            data["data"][0]["administration_id"],
            self.form_data.administration.id,
        )
        self.assertFalse(self.mobile_assignment.last_synced_at, None)
        # test if url is correct
        self.assertEqual(
            data["data"][0]["url"], f"{WEBDOMAIN}/datapoints/{self.uuid}.json"
        )
        self.assertEqual(
            list(data["data"][0]),
            [
                "id",
                "form_id",
                "name",
                "administration_id",
                "url",
                "last_updated",
            ],
        )

    def test_get_datapoints_list_by_national_user(self):
        # Remove current administration mobile assignment
        self.mobile_assignment.administrations.clear()
        # Add national administration
        self.mobile_assignment.administrations.add(
            self.administration
        )
        self.mobile_assignment.save()
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)

    def test_get_datapoints_list_by_second_level_administration(self):
        # Remove current administration mobile assignment
        self.mobile_assignment.administrations.clear()
        # Add second level administration
        self.mobile_assignment.administrations.add(
            self.administration.parent_administration.first()
        )
        self.mobile_assignment.save()
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)

    def test_get_datapoints_list_by_last_administration_level(self):
        # Remove current administration mobile assignment
        self.mobile_assignment.administrations.clear()
        # Add last level administration
        adm = self.adm_children.first()
        adm_children = adm.parent_administration.first()
        self.mobile_assignment.administrations.add(
            adm_children
        )
        self.mobile_assignment.save()
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # No data points for last level administration
        self.assertEqual(data["total"], 0)

    def test_get_datapoints_list_exclude_pending_data(self):
        # Create a pending form data
        pending_form_data = FormData.objects.create(
            name="Pending Data",
            geo=None,
            form=self.forms[0],
            administration=self.adm_children.first(),
            created_by=self.user,
            uuid="pending-uuid-1234",
            is_pending=True,  # Mark as pending
        )
        add_fake_answers(pending_form_data)

        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Ensure that the pending data is not included in the list
        self.assertEqual(data["total"], 1)
        self.assertNotIn(pending_form_data.id, [d["id"] for d in data["data"]])

    def test_get_datapoint_list_from_last_synced_at(self):
        # Create a new form data after the last synced time
        self.mobile_assignment.last_synced_at = self.form_data.created
        self.mobile_assignment.save()

        new_form_data = FormData.objects.create(
            name="New Data",
            geo=None,
            form=self.forms[0],
            administration=self.adm_children.first(),
            created_by=self.user,
            uuid="new-uuid-1234",
        )
        add_fake_answers(new_form_data)

        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Ensure that the new data is included in the list
        self.assertEqual(data["total"], 2)
        self.assertIn(new_form_data.id, [d["id"] for d in data["data"]])

    def test_get_datapoint_list_exclude_draft_data(self):
        # Create a draft form data
        draft_form_data = FormData.objects.create(
            name="Draft Data",
            geo=None,
            form=self.forms[0],
            administration=self.adm_children.first(),
            created_by=self.user,
            uuid="draft-uuid-1234",
            is_pending=False,  # Not pending
            is_draft=True,  # Mark as draft
        )
        add_fake_answers(draft_form_data)

        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["syncToken"]
        url = "/api/v1/device/datapoint-list/"
        response = self.client.get(
            url,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Ensure that the draft data is not included in the list
        self.assertEqual(data["total"], 1)
        self.assertNotIn(draft_form_data.id, [d["id"] for d in data["data"]])

    def test_get_datapoints_list_with_form_id_filter(self):
        """Filter by form_id returns only that form's datapoints."""
        second_form_data = FormData.objects.create(
            name="Second Form Data",
            geo=None,
            form=self.forms[1],
            administration=self.adm_children.first(),
            created_by=self.user,
            uuid="uuid-second-form",
        )
        add_fake_answers(second_form_data)

        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]

        # Without form_id -> both datapoints
        response = self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total"], 2)

        # Re-auth to reset last_synced_at
        token_2 = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        ).data["syncToken"]

        # With form_id -> only that form's datapoints
        response = self.client.get(
            f"/api/v1/device/datapoint-list/?form_id={self.forms[0].id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token_2}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["form_id"], self.forms[0].id)

    def test_get_datapoints_list_with_invalid_form_id(self):
        """form_id not in assignment returns 404."""
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]

        response = self.client.get(
            "/api/v1/device/datapoint-list/?form_id=999999",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_form_id_filter_does_not_update_last_synced_at(self):
        """When form_id is specified, last_synced_at should NOT update."""
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]

        # Fetch with form_id (reaches last page)
        response = self.client.get(
            f"/api/v1/device/datapoint-list/?form_id={self.forms[0].id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # last_synced_at should still be None
        self.mobile_assignment.refresh_from_db()
        self.assertIsNone(self.mobile_assignment.last_synced_at)

    def test_no_form_id_does_update_last_synced_at(self):
        """Without form_id, last_synced_at IS updated on last page."""
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]

        response = self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.mobile_assignment.refresh_from_db()
        self.assertIsNotNone(self.mobile_assignment.last_synced_at)

    def test_mark_sync_complete(self):
        """POST /sync-complete updates last_synced_at."""
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]

        self.mobile_assignment.refresh_from_db()
        self.assertIsNone(self.mobile_assignment.last_synced_at)

        response = self.client.post(
            "/api/v1/device/sync-complete",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.mobile_assignment.refresh_from_db()
        self.assertIsNotNone(self.mobile_assignment.last_synced_at)

    def test_auth_keep_last_synced_at_returns_only_new_data(self):
        """Auth with keep_last_synced_at=true preserves last_synced_at,
        so datapoint-list returns only new data."""
        code = {"code": self.passcode}
        # First auth (resets last_synced_at to None)
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]

        # Fetch all datapoints (triggers last_synced_at update)
        response = self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total"], 1)

        # last_synced_at should now be set
        self.mobile_assignment.refresh_from_db()
        self.assertIsNotNone(self.mobile_assignment.last_synced_at)

        # Create new data AFTER last_synced_at
        new_form_data = FormData.objects.create(
            name="New After Sync",
            geo=None,
            form=self.forms[0],
            administration=self.adm_children.first(),
            created_by=self.user,
            uuid="uuid-new-after-sync",
        )
        add_fake_answers(new_form_data)

        # Re-auth WITH keep_last_synced_at=true
        response = self.client.post(
            "/api/v1/device/auth?keep_last_synced_at=true",
            code,
            content_type="application/json",
        )
        token_2 = response.data["syncToken"]

        # last_synced_at should still be set (not reset)
        self.mobile_assignment.refresh_from_db()
        self.assertIsNotNone(self.mobile_assignment.last_synced_at)

        # Datapoint list should only return the new data
        response = self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token_2}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], new_form_data.id)

    def test_auth_without_keep_last_synced_at_returns_all_data(self):
        """Auth without keep_last_synced_at resets last_synced_at,
        so datapoint-list returns all data."""
        code = {"code": self.passcode}
        # First auth + fetch to set last_synced_at
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token = response.data["syncToken"]
        self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.mobile_assignment.refresh_from_db()
        self.assertIsNotNone(self.mobile_assignment.last_synced_at)

        # Re-auth WITHOUT keep_last_synced_at (default behavior)
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )
        token_2 = response.data["syncToken"]

        # last_synced_at should be reset to None
        self.mobile_assignment.refresh_from_db()
        self.assertIsNone(self.mobile_assignment.last_synced_at)

        # Datapoint list returns all data
        response = self.client.get(
            "/api/v1/device/datapoint-list/",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token_2}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total"], 1)

    def test_mark_sync_complete_unauthenticated(self):
        """POST /sync-complete without token returns 401."""
        response = self.client.post(
            "/api/v1/device/sync-complete",
            content_type="application/json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED
        )
