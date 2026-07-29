from django.test.utils import override_settings
from django.urls import NoReverseMatch, reverse

from api.v1.v1_users.models import Organisation
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class UsersTenantIsolationTestCase(TenantIsolationTestCase):
    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["org"] = Organisation.objects.create(
            name=f"{sub}-org", tenant=tenant["tenant"]
        )
        return tenant

    def test_user_list_excludes_other_tenant(self):
        res = self.client.get("/api/v1/users", **self.auth(self.a["user"]))
        self.assertEqual(res.status_code, 200)
        emails = [u["email"] for u in res.json()["data"]]
        self.assertIn(self.a["user"].email, emails)
        self.assertNotIn(self.b["user"].email, emails)

    def test_user_detail_404_on_foreign_user(self):
        res = self.client.get(
            f"/api/v1/user/{self.b['user'].id}", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 404)

    def test_organisation_list_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/organisations", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        rows = body.get("data", body) if isinstance(body, dict) else body
        names = [o["name"] for o in rows]
        self.assertIn(self.a["org"].name, names)
        self.assertNotIn(self.b["org"].name, names)

    def test_levels_list_excludes_other_tenant(self):
        res = self.client.get("/api/v1/levels", **self.auth(self.a["user"]))
        self.assertEqual(res.status_code, 200)
        ids = [lv["id"] for lv in res.json()]
        self.assertIn(self.a["level"].id, ids)
        self.assertNotIn(self.b["level"].id, ids)

    def test_administration_detail_404_on_foreign_root(self):
        res = self.client.get(
            f"/api/v1/administration/{self.b['root'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_public_administration_endpoint_is_gone(self):
        # Deleted rather than scoped: it returned every tenant's units to
        # anyone, and its only consumer was the authenticated form-builder.
        with self.assertRaises(NoReverseMatch):
            reverse("public-administrations-list")
        res = self.client.get("/api/v1/public/administrations")
        self.assertEqual(res.status_code, 404)
