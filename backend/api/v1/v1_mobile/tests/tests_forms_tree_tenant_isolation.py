from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class FormsTreeTenantIsolationTestCase(TenantIsolationTestCase):
    """The assignment-builder tree must show only the caller's forms.

    get_forms_tree queried Forms.objects.filter(...) unscoped, so the UI
    listed every tenant's published forms by name and id.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["monitoring"] = Forms.objects.create(
            name=f"{sub}-monitoring",
            tenant=tenant["tenant"],
            status=FormStatus.published,
            parent=tenant["form"],
        )
        return tenant

    def test_tree_excludes_another_tenants_registration_form(self):
        res = self.client.get(
            "/api/v1/forms-tree", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        names = [f["name"] for f in res.json()]
        self.assertIn("acme-form", names)
        self.assertNotIn("beta-form", names)

    def test_tree_excludes_another_tenants_monitoring_child(self):
        res = self.client.get(
            "/api/v1/forms-tree", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        children = [c["name"] for f in res.json() for c in f["children"]]
        self.assertIn("acme-monitoring", children)
        self.assertNotIn("beta-monitoring", children)
