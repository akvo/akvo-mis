from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_approval.models import DataApproval
from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_data.models import FormData
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_profile.models import Role
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class DataBatchRejectedTestCase(TestCase, ProfileTestHelperMixin):
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
            form_id=1,
        ).first()

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

    def test_rejected_by_third_level_approver(self):
        # Update the DataApproval for third approval
        a3_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a3,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a3_approval.status, DataApprovalStatus.pending)
        # Now, we can reject via the API
        payload = {
            "approval": a3_approval.id,
            "status": DataApprovalStatus.rejected,
            "comment": "Rejecting the data for testing",
        }
        a3_res = self.client.post(
            "/api/v1/pending-data/approve",
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(a3_res.status_code, 200)
        a3_approval.refresh_from_db()
        self.assertEqual(a3_approval.status, DataApprovalStatus.rejected)

        # 3d approval should not see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 0)

        # Verify the status is updated by login as a submitter
        submitter_token = self.get_auth_token(
            self.data.created_by.email,
            "test"
        )
        response = self.client.get(
            f"/api/v1/batch/?form={self.batch.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)
        all_approvers = batch_data["data"][0]["approvers"]
        a3_approver = list(
            filter(
                lambda x: x["name"] == self.a3.get_full_name(),
                all_approvers
            )
        )[0]
        self.assertEqual(
            a3_approver["status"],
            DataApprovalStatus.rejected
        )

    def test_rejected_by_second_level_approver(self):
        # Update the DataApproval for third approval
        a3_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a3,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a3_approval.status, DataApprovalStatus.pending)
        # Now, we can approve the data
        a3_approval.status = DataApprovalStatus.approved
        a3_approval.save()

        # Update the DataApproval for second approval
        a2_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a2,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a2_approval.status, DataApprovalStatus.pending)
        # Now, we can reject the data via API
        a2_res = self.client.post(
            "/api/v1/pending-data/approve",
            data={
                "approval": a2_approval.id,
                "status": DataApprovalStatus.rejected,
                "comment": "Rejecting the data for testing",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(a2_res.status_code, 200)

        a2_approval.refresh_from_db()
        self.assertEqual(a2_approval.status, DataApprovalStatus.rejected)

        # 2nd approval should not see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 0)

        # But 2nd approval should see the batch in subordinate state
        response = self.client.get(
            "/api/v1/form-pending-batch?subordinate=true",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

        # 3nd approval should see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

        # Verify the status is updated by login as a submitter
        submitter_token = self.get_auth_token(
            self.data.created_by.email,
            "test"
        )
        response = self.client.get(
            f"/api/v1/batch/?form={self.batch.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)
        all_approvers = batch_data["data"][0]["approvers"]
        a2_approver = list(
            filter(
                lambda x: x["name"] == self.a2.get_full_name(),
                all_approvers
            )
        )[0]
        self.assertEqual(
            a2_approver["status"],
            DataApprovalStatus.rejected
        )

    def test_rejected_by_first_level_approver(self):
        # Update the DataApproval for third approval
        a3_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a3,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a3_approval.status, DataApprovalStatus.pending)
        # Now, we can approve the data
        a3_approval.status = DataApprovalStatus.approved
        a3_approval.save()
        # Update the DataApproval for second approval
        a2_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a2,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a2_approval.status, DataApprovalStatus.pending)
        # Now, we can approve the data
        a2_approval.status = DataApprovalStatus.approved
        a2_approval.save()

        # Update the DataApproval for first approval
        a1_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a1,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a1_approval.status, DataApprovalStatus.pending)
        # Now, we can reject via API
        a1_res = self.client.post(
            "/api/v1/pending-data/approve",
            data={
                "approval": a1_approval.id,
                "status": DataApprovalStatus.rejected,
                "comment": "Rejecting the data for testing",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a1_token}",
        )
        self.assertEqual(a1_res.status_code, 200)

        a1_approval.refresh_from_db()
        self.assertEqual(a1_approval.status, DataApprovalStatus.rejected)

        # 1st approval should not see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a1_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 0)

        # But 1st approval should see the batch in subordinate state
        response = self.client.get(
            "/api/v1/form-pending-batch?subordinate=true",
            HTTP_AUTHORIZATION=f"Bearer {self.a1_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

        # 2nd approval should see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

        # 3nd approval should see the batch in approved state
        response = self.client.get(
            "/api/v1/form-pending-batch?approved=true",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

        # Verify the status is updated by login as a submitter
        submitter_token = self.get_auth_token(
            self.data.created_by.email,
            "test"
        )
        response = self.client.get(
            f"/api/v1/batch/?form={self.batch.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)
        all_approvers = batch_data["data"][0]["approvers"]
        a1_approver = list(
            filter(
                lambda x: x["name"] == self.a1.get_full_name(),
                all_approvers
            )
        )[0]
        self.assertEqual(
            a1_approver["status"],
            DataApprovalStatus.rejected
        )

    def test_resubmit_after_rejection_by_third_approver(self):
        # Update the DataApproval for third approval
        a3_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a3,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a3_approval.status, DataApprovalStatus.pending)
        # Now, we can approve the data
        a3_approval.status = DataApprovalStatus.approved
        a3_approval.save()

        # Update the DataApproval for second approval
        a2_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a2,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a2_approval.status, DataApprovalStatus.pending)
        # Now, we can reject the data via API
        a2_res = self.client.post(
            "/api/v1/pending-data/approve",
            data={
                "approval": a2_approval.id,
                "status": DataApprovalStatus.rejected,
                "comment": "Rejecting the data for testing",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(a2_res.status_code, 200)

        a2_approval.refresh_from_db()
        self.assertEqual(a2_approval.status, DataApprovalStatus.rejected)

        # 2nd approval should not see the batch in pending state
        a2_batch = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(a2_batch.status_code, 200)
        batch_data = a2_batch.json()
        self.assertEqual(batch_data["total"], 0)

        # 3rd approval should see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

        # Resubmit the batch after rejection by third level approver
        payload = [
            {
                "value": "/images/question_107.jpg",
                "question": 107,
            }
        ]
        response = self.client.put(
            (
                f"/api/v1/form-pending-data/{self.data.form.id}/"
                f"?pending_data_id={self.data.id}"
            ),
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)

        a3_approval.refresh_from_db()
        self.assertEqual(a3_approval.status, DataApprovalStatus.approved)

        # 2nd approval should see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a2_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)

    def test_resubmit_after_rejection_by_submitter(self):
        # Update the DataApproval for third approval
        a3_approval = DataApproval.objects.filter(
            batch=self.batch,
            user=self.a3,
        ).first()
        # First, we need to ensure the data is in pending state
        self.assertEqual(a3_approval.status, DataApprovalStatus.pending)
        # Now, we can reject the data via API
        a3_res = self.client.post(
            "/api/v1/pending-data/approve",
            data={
                "approval": a3_approval.id,
                "status": DataApprovalStatus.rejected,
                "comment": "Rejecting the data for testing",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(a3_res.status_code, 200)
        a3_approval.refresh_from_db()
        self.assertEqual(a3_approval.status, DataApprovalStatus.rejected)

        # 3rd approval should not see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 0)

        # Resubmit the batch after rejection by first level approver
        submitter_token = self.get_auth_token(
            self.data.created_by.email,
            "test"
        )
        payload = [
            {
                "value": "/images/question_107.jpg",
                "question": 107,
            }
        ]
        response = self.client.put(
            (
                f"/api/v1/form-pending-data/{self.data.form.id}/"
                f"?pending_data_id={self.data.id}"
            ),
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "update success"})

        # 3rd approval should see the batch in pending state
        response = self.client.get(
            "/api/v1/form-pending-batch",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(response.status_code, 200)
        batch_data = response.json()
        self.assertEqual(batch_data["total"], 1)
