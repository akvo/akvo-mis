from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Entity
from api.v1.v1_users.models import Organisation, SystemUser
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class WriteGuardTestCase(TenantIsolationTestCase):
    """A PUT/PATCH/DELETE aimed at another tenant's object must 404.

    404 rather than 403: the object's existence is not revealed, matching
    the read detail endpoints.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["data"] = FormData.objects.create(
            name=f"{sub}-dp",
            form=tenant["form"],
            administration=tenant["child"],
            created_by=tenant["user"],
        )
        tenant["org"] = Organisation.objects.create(
            name=f"{sub}-org", tenant=tenant["tenant"]
        )
        tenant["entity"] = Entity.objects.create(
            name=f"{sub}-entity", tenant=tenant["tenant"]
        )
        return tenant

    def test_delete_foreign_datapoint_404s(self):
        res = self.client.delete(
            f"/api/v1/data/{self.b['data'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
        self.assertTrue(FormData.objects.filter(id=self.b["data"].id).exists())

    def test_delete_foreign_form_404s(self):
        res = self.client.delete(
            f"/api/v1/manage/forms/{self.b['form'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
        self.assertTrue(
            Forms.objects_with_deleted.filter(
                id=self.b["form"].id, deleted_at__isnull=True
            ).exists()
        )

    def test_delete_foreign_user_404s(self):
        res = self.client.delete(
            f"/api/v1/user/{self.b['user'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
        self.assertTrue(
            SystemUser.objects.filter(id=self.b["user"].id).exists()
        )

    def test_edit_foreign_organisation_404s(self):
        res = self.client.put(
            f"/api/v1/organisation/{self.b['org'].id}",
            {"name": "Hijacked", "attributes": [1]},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
        self.b["org"].refresh_from_db()
        self.assertEqual(self.b["org"].name, "beta-org")

    def test_edit_foreign_entity_404s(self):
        res = self.client.put(
            f"/api/v1/entities/{self.b['entity'].id}",
            {"name": "Hijacked"},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
        self.b["entity"].refresh_from_db()
        self.assertEqual(self.b["entity"].name, "beta-entity")

    def test_monitoring_form_cannot_parent_to_foreign_form(self):
        # A cross-tenant write that no lookup guarded: the parent id was
        # resolved against every form in the table.
        self.b["form"].status = 1
        self.b["form"].save()
        res = self.client.post(
            "/api/v1/manage/forms",
            {
                "name": "Sneaky Monitoring",
                "type": "monitoring",
                "parent": self.b["form"].id,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(
            Forms.objects.filter(name="Sneaky Monitoring").exists()
        )
