from django.core.management import call_command
from django.test import TestCase
from rest_framework import status

from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


class MobileAssignmentApiDraftDeleteTest(
    TestCase, AssignmentTokenTestHelperMixin, ProfileTestHelperMixin
):
    """
    Deleting a draft from the device.

    The web route (DELETE /draft-submission/<id>) cannot serve this: it is
    gated on IsAuthenticated, and AssignmentAwareJWTAuthentication resolves a
    MobileAssignmentToken to AnonymousUser, so a device never passes it.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        adm_level = Levels.objects.filter(level=3).order_by("?").first()
        self.administration = (
            Administration.objects.filter(level=adm_level)
            .order_by("?")
            .last()
        )
        self.geo = [-121.8863, 37.3382]
        self.uuid = "2f14a095-fb1e-48c1-ae13-d3ca8ba92cfe"
        self.form = Forms.objects.get(pk=1)

        self.user = self.create_user(
            email="owner@test.org",
            administration=self.administration,
            role_level=self.IS_ADMIN,
            form=self.form,
        )
        self.user.set_password("test1234")
        self.user.save()

        self.other_user = self.create_user(
            email="someone.else@test.org",
            administration=self.administration,
            role_level=self.IS_ADMIN,
            form=self.form,
        )

        self.draft = self.create_draft(self.user)
        self.other_draft = self.create_draft(self.other_user)

        # A published submission, to prove this route cannot reach one.
        self.submission = FormData.objects.create(
            form=self.form,
            created_by=self.user,
            administration=self.administration,
            uuid=self.uuid,
            geo=self.geo,
        )
        add_fake_answers(self.submission)

        self.user_token = self.get_auth_token(self.user.email, "test1234")

        passcode = "passcode1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.mobile_assignment.forms.add(self.form)
        self.mobile_token = self.get_assignment_token(passcode)

    def create_draft(self, user):
        draft = FormData.objects.create(
            form=self.form,
            created_by=user,
            administration=self.administration,
            uuid=self.uuid,
            geo=self.geo,
        )
        draft.mark_as_draft()
        add_fake_answers(draft)
        return draft

    def delete_draft(self, draft_id, token):
        return self.client.delete(
            f"/api/v1/device/draft-list/{draft_id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

    def test_delete_draft(self):
        response = self.delete_draft(self.draft.id, self.mobile_token)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # _base_manager bypasses the soft-delete managers: the row must be gone
        # from the table, not merely flagged. A soft-deleted draft would come
        # back through the draft-list download and undo the deletion.
        self.assertFalse(
            FormData._base_manager.filter(pk=self.draft.id).exists()
        )

    def test_delete_draft_leaves_other_drafts_alone(self):
        self.delete_draft(self.draft.id, self.mobile_token)

        self.assertTrue(
            FormData.objects_draft.filter(pk=self.other_draft.id).exists()
        )

    def test_delete_draft_owned_by_another_user(self):
        response = self.delete_draft(
            self.other_draft.id, self.mobile_token
        )

        # get_queryset scopes to the assignment's user, so someone else's draft
        # is simply not found — never deleted, and never acknowledged.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            FormData.objects_draft.filter(pk=self.other_draft.id).exists()
        )

    def test_delete_published_submission(self):
        response = self.delete_draft(self.submission.id, self.mobile_token)

        # objects_draft excludes published rows, so a real submission cannot be
        # destroyed through the draft route.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            FormData.objects.filter(pk=self.submission.id).exists()
        )

    def test_delete_draft_with_invalid_token(self):
        response = self.delete_draft(self.draft.id, "invalid_token")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(
            FormData.objects_draft.filter(pk=self.draft.id).exists()
        )

    def test_delete_draft_with_user_token(self):
        # A web session token is not a device token: IsMobileAssignment checks
        # for a MobileAssignmentToken specifically.
        response = self.delete_draft(self.draft.id, self.user_token)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            FormData.objects_draft.filter(pk=self.draft.id).exists()
        )

    def test_draft_list_still_routes(self):
        # The list pattern is unanchored, so the detail route must be
        # declared before it. This guards that ordering: both keep resolving.
        response = self.client.get(
            "/api/v1/device/draft-list",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total"], 1)

    def test_get_on_detail_route_is_not_allowed(self):
        response = self.client.get(
            f"/api/v1/device/draft-list/{self.draft.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.mobile_token}"},
        )

        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )
