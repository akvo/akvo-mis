from django.test.utils import override_settings

from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class FormsTenantIsolationTestCase(TenantIsolationTestCase):
    def test_form_list_excludes_other_tenant(self):
        res = self.client.get("/api/v1/forms", **self.auth(self.a["user"]))
        self.assertEqual(res.status_code, 200)
        ids = [f["id"] for f in res.json()]
        self.assertIn(self.a["form"].id, ids)
        self.assertNotIn(self.b["form"].id, ids)

    def test_published_forms_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/forms/published", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        ids = [f["id"] for f in res.json()]
        self.assertIn(self.a["form"].id, ids)
        self.assertNotIn(self.b["form"].id, ids)

    def test_published_forms_cache_is_not_shared_between_tenants(self):
        # The payload is cached; a key shared across tenants would hand the
        # first caller's forms to the second.
        self.client.get("/api/v1/forms/published", **self.auth(self.a["user"]))
        res = self.client.get(
            "/api/v1/forms/published", **self.auth(self.b["user"])
        )
        ids = [f["id"] for f in res.json()]
        self.assertIn(self.b["form"].id, ids)
        self.assertNotIn(self.a["form"].id, ids)

    def test_web_form_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/form/web/{self.b['form'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_form_builder_list_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/manage/forms", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        ids = [f["id"] for f in res.json()["data"]]
        self.assertIn(self.a["form"].id, ids)
        self.assertNotIn(self.b["form"].id, ids)
