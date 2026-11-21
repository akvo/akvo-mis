from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_data.models import FormData
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_profile.models import Role
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class DataBatchListByApproverTestCase(TestCase, ProfileTestHelperMixin):
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

        # Create a batch with pending data
        self.data = FormData.objects.filter(
            is_pending=True,
            administration__level__level=4,
        ).first()

        self.submitter = self.data.created_by
        self.submitter.set_password("test")
        self.submitter.save()

        # Update the submitter's role to have data submission access
        self.submitter.user_user_role.all().delete()
        # Find a role for the submitter
        role = Role.objects.filter(
            role_role_access__data_access=DataAccessTypes.submit,
            administration_level=self.data.administration.level
        ).first()
        # Assign the role to the submitter
        self.submitter.user_user_role.create(
            role=role,
            administration=self.data.administration,
        )

        submitter_token = self.get_auth_token(self.submitter.email, "test")
        payload = {
            "name": "Test Batch",
            "comment": "This is a test batch",
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
        self.assertIsNotNone(
            self.batch,
            "Batch should be created successfully"
        )

        da = DataAccessTypes.approve
        self.approver = SystemUser.objects.filter(
            user_user_role__role__role_role_access__data_access=da,
            data_approval_user__isnull=False,
        ).first()
        self.approver.set_password("test")
        self.approver.save()

        self.token = self.get_auth_token(self.approver.email, "test")

    def test_success_get_batch_list_by_approver(self):
        response = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("current", response_json)
        self.assertIn("total", response_json)
        self.assertIn("total_page", response_json)
        self.assertIn("batch", response_json)
        self.assertIsInstance(response_json["batch"], list)
        self.assertEqual(response_json["total"], 0)

    def test_get_batch_list_by_subordinate(self):
        response = self.client.get(
            "/api/v1/form-pending-batch?subordinate=true",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertIn("current", response_json)
        self.assertIn("total", response_json)
        self.assertIn("total_page", response_json)
        self.assertIn("batch", response_json)
        self.assertIsInstance(response_json["batch"], list)

        self.assertEqual(response_json["total"], 1)

        ur = self.approver.user_user_role.filter(
            role__role_role_access__data_access=DataAccessTypes.approve,
        ).first()
        approvals = self.batch.batch_approval.filter(
            administration__level__level=ur.administration.level.level + 1,
        ).all()

        self.assertEqual(
            len(response_json["batch"][0]["approver"]),
            approvals.count(),
            "Total approvals should match the number of approvers"
        )

        for a in approvals:
            self.assertIn(
                a.user.get_full_name(),
                [b["name"] for b in response_json["batch"][0]["approver"]],
                "Approver email should be in the batch list"
            )

    def test_get_batch_list_by_approved_status(self):
        response = self.client.get(
            "/api/v1/form-pending-batch?approved=true",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertIn("current", response_json)
        self.assertIn("total", response_json)
        self.assertIn("total_page", response_json)
        self.assertIn("batch", response_json)
        self.assertIsInstance(response_json["batch"], list)

        self.assertEqual(response_json["total"], 0)
        self.assertEqual(
            len(response_json["batch"]),
            0,
            "Batch list should be empty for approved status"
        )

    def test_get_batch_list_by_all_approvers(self):
        data = FormData.objects.filter(
            is_pending=True,
            administration__level__level=4,
            form__parent__isnull=True,
        ).exclude(
            pk=self.data.pk
        ).first()

        parent_adms = data.administration.ancestors.all()

        approver_list = []
        for p in parent_adms:
            da = DataAccessTypes.approve
            approver = SystemUser.objects.filter(
                user_user_role__administration=p,
                user_user_role__role__role_role_access__data_access=da,
            ).order_by("?").first()
            if not approver:
                # create a new approver
                new_approver = self.create_user(
                    email="new.approver@test.com",
                    role_level=self.IS_APPROVER,
                    administration=p,
                    form=data.form,
                )
                approver_list.append({
                    "level": p.level.level,
                    "user": new_approver,
                })
            else:
                approver_list.append({
                    "level": p.level.level,
                    "user": approver,
                })

        # Create a batch with the new data
        submitter = data.created_by
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
            administration=data.administration,
        )

        submitter_token = self.get_auth_token(submitter.email, "test")
        payload = {
            "name": "Test Batch 2",
            "comment": "This is another test batch",
            "data": [data.id],
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 201)
        data.refresh_from_db()

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

        a1_token = self.get_auth_token(
            a1.email,
            "test"
        )
        a1_res = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {a1_token}",
        )
        self.assertEqual(a1_res.status_code, 200)
        a1_json = a1_res.json()
        # a1 waiting for a2 to approve
        self.assertEqual(
            a1_json["total"],
            0,
            "First level approver should not see the batch yet"
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

        a2_token = self.get_auth_token(
            a2.email,
            "test"
        )
        a2_res = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {a2_token}",
        )
        self.assertEqual(a2_res.status_code, 200)
        # a2 waiting for a3 to approve
        a2_json = a2_res.json()
        # Find the batch in the response
        a2_batch = list(
            filter(
                lambda x: x["name"] == "Test Batch 2",
                a2_json["batch"]
            )
        )
        self.assertEqual(
            len(a2_batch),
            0,
            "Second level approver should not see the batch yet"
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

        a3_token = self.get_auth_token(
            a3.email,
            "test"
        )
        a3_res = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {a3_token}",
        )
        self.assertEqual(a3_res.status_code, 200)
        a3_json = a3_res.json()

        self.assertEqual(
            list(a3_json["batch"][0]),
            [
                "id",
                "name",
                "form",
                "administration",
                "created_by",
                "created",
                "approver",
                "approved",
                "total_data",
            ]
        )
        self.assertEqual(
            list(a3_json["batch"][0]["approver"][0]),
            [
                "id",
                "name",
                "administration_level",
                "status",
                "status_text",
                "allow_approve",
            ]
        )

        a3_batch = list(
            filter(
                lambda x: x["name"] == "Test Batch 2",
                a3_json["batch"]
            )
        )[0]
        self.assertEqual(
            a3.get_full_name(),
            a3_batch["approver"][0]["name"],
            "3nd approver name should match the batch approver name"
        )
        self.assertTrue(
            a3_batch["approver"][0]["allow_approve"],
            "3nd approver should be able to approve the batch"
        )
