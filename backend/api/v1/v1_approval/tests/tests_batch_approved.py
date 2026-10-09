import os
from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_data.models import FormData
from api.v1.v1_data.tasks import seed_approved_data
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_profile.models import Role
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from mis.settings import STORAGE_PATH


@override_settings(USE_TZ=False, TEST_ENV=True)
class DataBatchApprovedTestCase(TestCase, ProfileTestHelperMixin):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)
        self.call_command(repeat=2, approved=False)

        self.data = FormData.objects.filter(
            is_pending=True,
            administration__level__level=4,
            form__parent__isnull=True,
        ).last()
        parent_adms = self.data.administration.ancestors.all()

        approver_list = []
        for p in parent_adms:
            da = DataAccessTypes.approve
            approver = SystemUser.objects.filter(
                user_user_role__administration=p,
                user_user_role__role__role_role_access__data_access=da,
            ).order_by("?").first()
            approver_list.append({
                "level": p.level.level,
                "user": approver,
            })

        # Create a batch with the new data
        submitter = self.data.created_by
        submitter.set_password("test")
        submitter.save()

        # Update the submitter's role to have data submission access
        submitter.user_user_role.all().delete()
        # Find a role for the submitter
        role = Role.objects.filter(
            role_role_access__data_access=DataAccessTypes.submit,
            administration_level=self.data.administration.level
        ).first()
        # Assign the role to the submitter
        submitter.user_user_role.create(
            role=role,
            administration=self.data.administration,
        )

        submitter_token = self.get_auth_token(submitter.email, "test")
        payload = {
            "name": "Test Batch 2",
            "comment": "This is another test batch",
            "data": [self.data.id],
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 201)
        self.data.refresh_from_db()

        self.batch = self.data.data_batch_list.batch

        # Get batch list by first level approver
        a1 = list(
            filter(
                lambda x: x["level"] == 1,
                approver_list
            )
        )[0]
        a1 = a1["user"]
        a1.set_password("test")
        a1.save()
        self.a1 = a1

        self.a1_token = self.get_auth_token(
            a1.email,
            "test"
        )

        # Get batch list by second level approver
        a2 = list(
            filter(
                lambda x: x["level"] == 2,
                approver_list
            )
        )[0]
        a2 = a2["user"]
        a2.set_password("test")
        a2.save()

        self.a2 = a2
        self.a2_token = self.get_auth_token(
            a2.email,
            "test"
        )

        # Get batch list by third level approver
        a3 = list(
            filter(
                lambda x: x["level"] == 3,
                approver_list
            )
        )[0]
        a3 = a3["user"]
        a3.set_password("test")
        a3.save()

        self.a3 = a3
        self.a3_token = self.get_auth_token(
            a3.email,
            "test"
        )

    def test_batch_approved_by_third_level_approver(self):
        response = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch = response.json()["batch"][0]
        approval = list(
            filter(
                lambda x: x["name"] == self.a3.get_full_name(),
                batch["approver"]
            )
        )[0]
        payload = {
            "approval": approval["id"],
            "status": DataApprovalStatus.approved,
            "comment": "Approved by third level approver",
        }
        # Approve the batch by third level approver
        response = self.client.post(
            "/api/v1/pending-data/approve",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)

        # Check if the data is approved
        self.data.refresh_from_db()
        self.assertTrue(
            self.data.is_pending
        )

    def test_batch_approved_by_second_level_approver(self):
        # Approve the third level approver first
        third_approval = self.batch.batch_approval.filter(
            user=self.a3,
        ).first()
        third_approval.status = DataApprovalStatus.approved
        third_approval.save()

        response = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch = response.json()["batch"][0]
        approval = list(
            filter(
                lambda x: x["name"] == self.a2.get_full_name(),
                batch["approver"]
            )
        )[0]

        payload = {
            "approval": approval["id"],
            "status": DataApprovalStatus.approved,
            "comment": "Approved by second level approver",
        }
        # Approve the batch by second level approver
        response = self.client.post(
            "/api/v1/pending-data/approve",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(response.status_code, 200)
        # Check if the data is approved
        self.data.refresh_from_db()
        self.assertTrue(
            self.data.is_pending
        )

    def test_batch_approved_by_first_level_approver(self):
        # Approve the third and second level approvers first
        third_approval = self.batch.batch_approval.filter(
            user=self.a3,
        ).first()
        third_approval.status = DataApprovalStatus.approved
        third_approval.save()

        second_approval = self.batch.batch_approval.filter(
            user=self.a2,
        ).first()
        second_approval.status = DataApprovalStatus.approved
        second_approval.save()

        # Now approve by first level approver
        response = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a1_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch = response.json()["batch"][0]

        approval = list(
            filter(
                lambda x: x["name"] == self.a1.get_full_name(),
                batch["approver"]
            )
        )[0]
        payload = {
            "approval": approval["id"],
            "status": DataApprovalStatus.approved,
            "comment": "Approved by first level approver",
        }
        # Approve the batch by first level approver
        response = self.client.post(
            "/api/v1/pending-data/approve",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a1_token}",
        )
        self.assertEqual(response.status_code, 200)
        # Check if the data is approved
        self.batch.refresh_from_db()
        self.assertTrue(
            self.batch.approved
        )

        seed_approved_data(self.data)

        self.data.refresh_from_db()
        self.assertFalse(
            self.data.is_pending
        )


class DataBatchApprovedTestCaseWithFileSaving(DataBatchApprovedTestCase):
    """
    This test case is similar to DataBatchApprovedTestCase but it ensures that
    the data is saved to file after approval.
    """

    def test_batch_approved_and_saved_to_file(self):
        # Overriding TEST_ENV to False to allow file saving
        with override_settings(TEST_ENV=False):
            # Approve the batch by first level approver
            self.test_batch_approved_by_first_level_approver()
            self.data.refresh_from_db()
        uuid = self.data.uuid
        self.assertTrue(
            os.path.exists(f"{STORAGE_PATH}/datapoints/{uuid}.json"),
            "File not exists"
        )
        # Remove the file after test
        os.remove(f"{STORAGE_PATH}/datapoints/{uuid}.json")
