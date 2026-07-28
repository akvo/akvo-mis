from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class FormsTenantIsolationTestCase(TestCase):
    def _tenant(self, sub):
        tenant = Tenant.objects.create(subdomain=sub)
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        Administration.objects.create(
            parent=None, level=level, name=sub, tenant=tenant
        )
        user = SystemUser.objects.create_superuser(
            email=f"admin@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        form = Forms.objects.create(
            name=f"{sub}-form", tenant=tenant, status=FormStatus.published
        )
        return {"tenant": tenant, "user": user, "form": form}

    def _auth(self, user):
        return {
            "HTTP_AUTHORIZATION":
                f"Bearer {RefreshToken.for_user(user).access_token}"
        }

    def setUp(self):
        self.a = self._tenant("acme")
        self.b = self._tenant("beta")

    def test_form_list_excludes_other_tenant(self):
        res = self.client.get("/api/v1/forms", **self._auth(self.a["user"]))
        self.assertEqual(res.status_code, 200)
        ids = [f["id"] for f in res.json()]
        self.assertIn(self.a["form"].id, ids)
        self.assertNotIn(self.b["form"].id, ids)

    def test_published_forms_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/forms/published", **self._auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        ids = [f["id"] for f in res.json()]
        self.assertIn(self.a["form"].id, ids)
        self.assertNotIn(self.b["form"].id, ids)

    def test_published_forms_cache_is_not_shared_between_tenants(self):
        # The payload is cached; a key shared across tenants would hand the
        # first caller's forms to the second.
        self.client.get(
            "/api/v1/forms/published", **self._auth(self.a["user"])
        )
        res = self.client.get(
            "/api/v1/forms/published", **self._auth(self.b["user"])
        )
        ids = [f["id"] for f in res.json()]
        self.assertIn(self.b["form"].id, ids)
        self.assertNotIn(self.a["form"].id, ids)

    def test_web_form_404_on_foreign_form(self):
        res = self.client.get(
            f"/api/v1/form/web/{self.b['form'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_form_builder_list_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/manage/forms", **self._auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        ids = [f["id"] for f in res.json()["data"]]
        self.assertIn(self.a["form"].id, ids)
        self.assertNotIn(self.b["form"].id, ids)
