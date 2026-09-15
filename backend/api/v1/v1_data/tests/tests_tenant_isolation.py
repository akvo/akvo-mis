from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class DataTenantIsolationTestCase(TenantIsolationTestCase):
    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["data"] = FormData.objects.create(
            name=f"{sub}-dp",
            form=tenant["form"],
            administration=tenant["child"],
            created_by=tenant["user"],
        )
        return tenant

    def test_data_list_shows_only_own_tenant(self):
        res = self.client.get(
            f"/api/v1/form-data/{self.a['form'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 200)
        ids = [d["id"] for d in res.json()["data"]]
        self.assertIn(self.a["data"].id, ids)
        self.assertNotIn(self.b["data"].id, ids)

    def test_data_list_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/form-data/{self.b['form'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_data_detail_404_on_foreign_object(self):
        res = self.client.get(
            f"/api/v1/data-details/{self.b['data'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_answer_detail_404_on_foreign_object(self):
        res = self.client.get(
            f"/api/v1/data/{self.b['data'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_draft_list_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/draft-submissions/{self.b['form'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_pending_list_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/form-pending-data/{self.b['form'].id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
