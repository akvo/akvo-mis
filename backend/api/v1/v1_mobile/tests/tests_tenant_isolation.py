from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_mobile.models import MobileAssignment
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class MobileTenantIsolationTestCase(TenantIsolationTestCase):
    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["data"] = FormData.objects.create(
            name=f"{sub}-dp",
            form=tenant["form"],
            administration=tenant["child"],
            created_by=tenant["user"],
        )
        assignment = MobileAssignment.objects.create_assignment(
            user=tenant["user"], name=f"{sub}-device"
        )
        assignment.administrations.add(tenant["child"])
        assignment.forms.add(tenant["form"])
        tenant["assignment"] = assignment
        return tenant

    def test_mobile_assignment_list_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/mobile-assignments", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        names = [m["name"] for m in res.json()["data"]]
        self.assertIn(self.a["assignment"].name, names)
        self.assertNotIn(self.b["assignment"].name, names)

    def test_datapoint_detail_404_on_foreign_object(self):
        res = self.client.get(
            f"/api/v1/maps/datapoint/{self.b['data'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
