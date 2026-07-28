from django.test import TestCase
from django.test.utils import override_settings
from django.urls import NoReverseMatch, reverse
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import Organisation, SystemUser, Tenant


@override_settings(USE_TZ=False)
class UsersTenantIsolationTestCase(TestCase):
    def _tenant(self, sub):
        tenant = Tenant.objects.create(subdomain=sub)
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        root = Administration.objects.create(
            parent=None, level=level, name=sub, tenant=tenant
        )
        user = SystemUser.objects.create_superuser(
            email=f"admin@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        org = Organisation.objects.create(name=f"{sub}-org", tenant=tenant)
        return {
            "tenant": tenant, "user": user, "root": root,
            "level": level, "org": org,
        }

    def _auth(self, user):
        return {
            "HTTP_AUTHORIZATION":
                f"Bearer {RefreshToken.for_user(user).access_token}"
        }

    def setUp(self):
        self.a = self._tenant("acme")
        self.b = self._tenant("beta")

    def test_user_list_excludes_other_tenant(self):
        res = self.client.get("/api/v1/users", **self._auth(self.a["user"]))
        self.assertEqual(res.status_code, 200)
        emails = [u["email"] for u in res.json()["data"]]
        self.assertIn(self.a["user"].email, emails)
        self.assertNotIn(self.b["user"].email, emails)

    def test_user_detail_404_on_foreign_user(self):
        res = self.client.get(
            f"/api/v1/user/{self.b['user'].id}", **self._auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 404)

    def test_organisation_list_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/organisations", **self._auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        names = [o["name"] for o in (body.get("data", body) if isinstance(
            body, dict
        ) else body)]
        self.assertIn(self.a["org"].name, names)
        self.assertNotIn(self.b["org"].name, names)

    def test_levels_list_excludes_other_tenant(self):
        res = self.client.get("/api/v1/levels", **self._auth(self.a["user"]))
        self.assertEqual(res.status_code, 200)
        ids = [lv["id"] for lv in res.json()]
        self.assertIn(self.a["level"].id, ids)
        self.assertNotIn(self.b["level"].id, ids)

    def test_administration_detail_404_on_foreign_root(self):
        res = self.client.get(
            f"/api/v1/administration/{self.b['root'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_public_administration_endpoint_is_gone(self):
        # Deleted rather than scoped: it returned every tenant's units to
        # anyone, and its only consumer was the authenticated form-builder.
        with self.assertRaises(NoReverseMatch):
            reverse("public-administrations-list")
        res = self.client.get("/api/v1/public/administrations")
        self.assertEqual(res.status_code, 404)
