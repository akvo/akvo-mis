from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import (
    ProfileTestHelperMixin,
    TenantTestHelperMixin,
)


@override_settings(USE_TZ=False)
class SuperAdminDraftAccessTestCase(
    TestCase, ProfileTestHelperMixin, TenantTestHelperMixin
):
    """#459: a super admin can list, view, edit, delete and publish any
    draft in their tenant; everyone else keeps owner-only access."""

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.form = Forms.objects.get(pk=1)
        adm = (
            Administration.objects.filter(level__level=3)
            .order_by("?")
            .first()
        )

        self.owner = self.create_user(
            email="owner@akvo.org",
            role_level=self.IS_ADMIN,
            administration=adm,
            form=self.form,
        )
        self.other = self.create_user(
            email="other@akvo.org",
            role_level=self.IS_ADMIN,
            administration=adm,
            form=self.form,
        )
        self.superadmin = self.create_user(
            email="super@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.owner_token = self.get_auth_token(self.owner.email)
        self.other_token = self.get_auth_token(self.other.email)
        self.super_token = self.get_auth_token(self.superadmin.email)

        self.draft = self._create_draft(self.owner_token, "Owner Draft", adm)
        self._create_draft(self.other_token, "Other Draft", adm)
        self.adm = adm

    def _payload(self, name, adm):
        return {
            "data": {
                "name": name,
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
            },
            "answer": [
                {"question": 101, "value": "Jane"},
                {"question": 102, "value": ["female"]},
                {"question": 103, "value": 6212111},
                {"question": 104, "value": 2.0},
                {"question": 105, "value": [6.2088, 106.8456]},
                {"question": 106, "value": ["parent"]},
                {"question": 109, "value": 0},
            ],
        }

    def _create_draft(self, token, name, adm):
        response = self.client.post(
            f"/api/v1/draft-submissions/{self.form.id}/",
            data=self._payload(name, adm),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 201)
        return FormData.objects_draft.get(name=name)

    def _auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_superadmin_lists_all_users_drafts(self):
        response = self.client.get(
            f"/api/v1/draft-submissions/{self.form.id}/",
            **self._auth(self.super_token),
        )
        self.assertEqual(response.status_code, 200)
        creators = {d["created_by"] for d in response.json()["data"]}
        self.assertIn(self.owner.get_full_name(), creators)
        self.assertIn(self.other.get_full_name(), creators)

    def test_submitter_lists_only_own_drafts(self):
        response = self.client.get(
            f"/api/v1/draft-submissions/{self.form.id}/",
            **self._auth(self.owner_token),
        )
        self.assertEqual(response.status_code, 200)
        names = [d["name"] for d in response.json()["data"]]
        self.assertEqual(names, ["Owner Draft"])

    def test_superadmin_views_other_users_draft(self):
        response = self.client.get(
            f"/api/v1/draft-submission/{self.draft.id}/",
            **self._auth(self.super_token),
        )
        self.assertEqual(response.status_code, 200)

    def test_submitter_cannot_view_other_users_draft(self):
        response = self.client.get(
            f"/api/v1/draft-submission/{self.draft.id}/",
            **self._auth(self.other_token),
        )
        self.assertEqual(response.status_code, 400)

    def test_superadmin_edits_other_users_draft(self):
        response = self.client.put(
            f"/api/v1/draft-submission/{self.draft.id}/",
            data=self._payload("Edited by Super", self.adm),
            content_type="application/json",
            **self._auth(self.super_token),
        )
        self.assertEqual(response.status_code, 200)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.name, "Edited by Super")
        self.assertEqual(self.draft.created_by, self.owner)
        self.assertEqual(self.draft.updated_by, self.superadmin)

    def test_superadmin_deletes_other_users_draft(self):
        response = self.client.delete(
            f"/api/v1/draft-submission/{self.draft.id}/",
            **self._auth(self.super_token),
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(FormData.objects.filter(pk=self.draft.id).exists())

    def test_submitter_cannot_delete_other_users_draft(self):
        response = self.client.delete(
            f"/api/v1/draft-submission/{self.draft.id}/",
            **self._auth(self.other_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_superadmin_publishes_other_users_draft_direct_to_data(self):
        response = self.client.post(
            f"/api/v1/publish-draft-submission/{self.draft.id}",
            content_type="application/json",
            **self._auth(self.super_token),
        )
        self.assertEqual(response.status_code, 200)
        data = FormData.objects.get(pk=self.draft.id)
        self.assertFalse(data.is_draft)
        self.assertFalse(data.is_pending)
        self.assertEqual(data.created_by, self.owner)

    def test_superadmin_of_other_tenant_gets_404(self):
        other = self.create_tenant("othertenant", ["Country"], "Elsewhere")
        for method in ("get", "delete"):
            response = getattr(self.client, method)(
                f"/api/v1/draft-submission/{self.draft.id}/",
                **self.bearer(other.admin),
            )
            self.assertEqual(response.status_code, 404, method)
