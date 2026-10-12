from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_data.models import FormData
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_profile.models import Role
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class PeerApprovalHiddenTestCase(TestCase, ProfileTestHelperMixin):
    """
    When multiple approvers share the same Administration, and one approves a
    batch, the others must no longer see that batch in their pending list.

    The DataApproval records are not mutated — the filtering is query-only.
    """

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
            approver = SystemUser.objects.filter(
                user_user_role__administration=p,
                user_user_role__role__role_role_access__data_access=(
                    DataAccessTypes.approve
                ),
            ).order_by("?").first()
            if approver:
                approver_list.append({
                    "level": p.level.level, "user": approver
                })

        # Pick the lowest-level approver (level=3 in test data)
        a3_entry = max(approver_list, key=lambda x: x["level"])
        self.a3 = a3_entry["user"]
        self.a3.set_password("test")
        self.a3.save()

        a3_role_qs = self.a3.user_user_role.filter(
            role__role_role_access__data_access=DataAccessTypes.approve,
        )
        a3_user_role = a3_role_qs.first()
        self.a3_administration = a3_user_role.administration

        # Create a PEER approver at the SAME administration, BEFORE batch
        # creation so that DataApproval records are generated for both.
        self.a3_peer = self.create_user(
            email="a3.peer@test.com",
            role_level=self.IS_APPROVER,
            password="test",
            administration=self.a3_administration,
            form=self.data.form,
        )

        # Create the batch (approvers() will now include both a3 and a3_peer)
        submitter = self.data.created_by
        submitter.set_password("test")
        submitter.save()
        submitter.user_user_role.all().delete()
        role = Role.objects.filter(
            role_role_access__data_access=DataAccessTypes.submit,
            administration_level=self.data.administration.level,
        ).first()
        submitter.user_user_role.create(
            role=role,
            administration=self.data.administration,
        )

        submitter_token = self.get_auth_token(submitter.email, "test")
        response = self.client.post(
            "/api/v1/batch",
            {"name": "Peer Approval Test Batch", "data": [self.data.id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {submitter_token}",
        )
        self.assertEqual(response.status_code, 201)
        self.data.refresh_from_db()
        self.batch = self.data.data_batch_list.batch

        self.a3_token = self.get_auth_token(self.a3.email, "test")
        self.a3_peer_token = self.get_auth_token("a3.peer@test.com", "test")

        # Sanity: both users must have a DataApproval record for this batch
        self.assertTrue(
            self.batch.batch_approval.filter(user=self.a3).exists(),
            "a3 must have a DataApproval record",
        )
        self.assertTrue(
            self.batch.batch_approval.filter(user=self.a3_peer).exists(),
            "a3_peer must have a DataApproval record",
        )

    # ------------------------------------------------------------------
    # Pre-condition: both peers see the batch before anyone acts
    # ------------------------------------------------------------------

    def test_both_peers_see_batch_before_any_approval(self):
        """
        Both approvers at the same Administration see the batch initially.
        """
        for token, label in [
            (self.a3_token, "a3"),
            (self.a3_peer_token, "a3_peer"),
        ]:
            with self.subTest(approver=label):
                response = self.client.get(
                    "/api/v1/form-pending-batch",
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                )
                self.assertEqual(response.status_code, 200)
                batch_ids = [b["id"] for b in response.json()["batch"]]
                self.assertIn(
                    self.batch.id,
                    batch_ids,
                    f"{label} should see batch before any approval",
                )

    # ------------------------------------------------------------------
    # Core behaviour: peer disappears after colleague approves
    # ------------------------------------------------------------------

    def test_peer_hidden_after_colleague_approves_via_api(self):
        """
        After a3 approves via the approve endpoint, a3_peer's pending list
        must no longer include that batch.
        """
        # a3 gets their approval id from the pending list
        pending_res = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(pending_res.status_code, 200)
        batch = next(
            (
                b for b in pending_res.json()["batch"]
                if b["id"] == self.batch.id
            ),
            None,
        )
        self.assertIsNotNone(batch, "a3 should see the batch before approving")
        approval_id = next(
            (a["id"] for a in batch["approver"] if a["allow_approve"]),
            None,
        )
        self.assertIsNotNone(approval_id, "a3 must have an approvable entry")

        # a3 approves
        approve_res = self.client.post(
            "/api/v1/pending-data/approve",
            {"approval": approval_id, "status": DataApprovalStatus.approved},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_token}",
        )
        self.assertEqual(approve_res.status_code, 200)

        # a3_peer must no longer see the batch in pending list
        peer_res = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_peer_token}",
        )
        self.assertEqual(peer_res.status_code, 200)
        batch_ids = [b["id"] for b in peer_res.json()["batch"]]
        self.assertNotIn(
            self.batch.id,
            batch_ids,
            "a3_peer must not see batch after"
            "a3 approved at the same Administration",
        )

    def test_peer_hidden_after_colleague_approves_direct(self):
        """
        Direct approval (bypassing the API) also hides the batch from peers.
        Verifies the list view filtering is purely query-based.
        """
        a3_approval = self.batch.batch_approval.filter(user=self.a3).first()
        a3_approval.status = DataApprovalStatus.approved
        a3_approval.save()

        peer_res = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_peer_token}",
        )
        self.assertEqual(peer_res.status_code, 200)
        batch_ids = [b["id"] for b in peer_res.json()["batch"]]
        self.assertNotIn(
            self.batch.id,
            batch_ids,
            "Batch must be excluded from peer's list after colleague approves",
        )

    # ------------------------------------------------------------------
    # Audit integrity: DataApproval record not mutated
    # ------------------------------------------------------------------

    def test_peer_approval_record_stays_pending(self):
        """
        The peer's DataApproval record must remain PENDING — Option B keeps
        the audit trail intact without mutating unacted records.
        """
        a3_approval = self.batch.batch_approval.filter(user=self.a3).first()
        a3_approval.status = DataApprovalStatus.approved
        a3_approval.save()

        peer_approval = self.batch.batch_approval.filter(
            user=self.a3_peer
        ).first()
        self.assertEqual(
            peer_approval.status,
            DataApprovalStatus.pending,
            "Peer's DataApproval must stay PENDING (not auto-mutated)",
        )

    # ------------------------------------------------------------------
    # Approved view unchanged
    # ------------------------------------------------------------------

    def test_peer_not_in_approved_list_after_colleague_approves(self):
        """
        The approved=true list for a3_peer must NOT include the batch,
        since the peer never acted on it.
        """
        a3_approval = self.batch.batch_approval.filter(user=self.a3).first()
        a3_approval.status = DataApprovalStatus.approved
        a3_approval.save()

        peer_res = self.client.get(
            "/api/v1/form-pending-batch?approved=true",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.a3_peer_token}",
        )
        self.assertEqual(peer_res.status_code, 200)
        batch_ids = [b["id"] for b in peer_res.json()["batch"]]
        self.assertNotIn(
            self.batch.id,
            batch_ids,
            "Peer must not appear in approved list (they never acted)",
        )
