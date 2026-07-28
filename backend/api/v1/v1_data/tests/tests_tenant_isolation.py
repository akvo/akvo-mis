from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class DataTenantIsolationTestCase(TestCase):
    """Two tenants, each with a form and a datapoint of their own.

    Tenant A's superadmin must see only A's rows and must not be able to
    reach B's objects by guessing an id.
    """

    def _tenant(self, sub):
        tenant = Tenant.objects.create(subdomain=sub)
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        child_level = Levels.objects.create(
            name="district", level=1, tenant=tenant
        )
        root = Administration.objects.create(
            parent=None, level=level, name=sub, tenant=tenant
        )
        # Datapoints hang off a child unit, not the root: the list filters
        # on administration__path__startswith and a root's path is NULL.
        child = Administration.objects.create(
            parent=root, level=child_level, name=f"{sub}-d", tenant=tenant
        )
        user = SystemUser.objects.create_superuser(
            email=f"admin@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        form = Forms.objects.create(name=f"{sub}-form", tenant=tenant)
        data = FormData.objects.create(
            name=f"{sub}-dp", form=form, administration=child,
            created_by=user,
        )
        return {
            "tenant": tenant, "user": user, "form": form,
            "root": root, "child": child, "data": data,
        }

    def _auth(self, user):
        return {
            "HTTP_AUTHORIZATION":
                f"Bearer {RefreshToken.for_user(user).access_token}"
        }

    def setUp(self):
        self.a = self._tenant("acme")
        self.b = self._tenant("beta")

    def test_data_list_shows_only_own_tenant(self):
        res = self.client.get(
            f"/api/v1/form-data/{self.a['form'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 200)
        ids = [d["id"] for d in res.json()["data"]]
        self.assertIn(self.a["data"].id, ids)
        self.assertNotIn(self.b["data"].id, ids)

    def test_data_list_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/form-data/{self.b['form'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_data_detail_404_on_foreign_object(self):
        res = self.client.get(
            f"/api/v1/data-details/{self.b['data'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_answer_detail_404_on_foreign_object(self):
        res = self.client.get(
            f"/api/v1/data/{self.b['data'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_draft_list_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/draft-submissions/{self.b['form'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_pending_list_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/form-pending-data/{self.b['form'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
