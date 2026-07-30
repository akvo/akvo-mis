from rest_framework_simplejwt.tokens import RefreshToken
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Levels, Role
from api.v1.v1_users.models import SystemUser, Tenant

URL = "/api/v1/levels-management"


@override_settings(USE_TZ=False)
class LevelManagementTestCase(TestCase):
    """A freshly registered tenant: level 0 and its root unit, nothing else.

    The shared TenantIsolationTestCase fixture already has a unit below
    root, which is the frozen state — the opposite of what most of these
    assertions need — so the fixture is local.
    """

    def _tenant(self, sub):
        tenant = Tenant.objects.create(subdomain=sub)
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        root = Administration.objects.create(
            parent=None, level=level, name=sub, tenant=tenant
        )
        admin = SystemUser.objects.create_superuser(
            email=f"a@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        return {
            "tenant": tenant, "level0": level, "root": root, "admin": admin,
        }

    def _auth(self, user):
        return {
            "HTTP_AUTHORIZATION":
                f"Bearer {RefreshToken.for_user(user).access_token}"
        }

    def _unit_below_root(self, fixture):
        return Administration.objects.create(
            parent=fixture["root"], level=fixture["level0"], name="child",
            tenant=fixture["tenant"],
        )

    def setUp(self):
        self.a = self._tenant("acme")
        self.b = self._tenant("beta")

    def test_list_shows_only_own_tenant_levels(self):
        Levels.objects.create(
            name="Beta Province", level=1, tenant=self.b["tenant"]
        )
        res = self.client.get(URL, **self._auth(self.a["admin"]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            [lv["id"] for lv in res.json()], [self.a["level0"].id]
        )

    def test_add_appends_at_max_plus_one_and_ignores_client_level(self):
        res = self.client.post(
            URL, {"name": "Province", "level": 9},
            content_type="application/json", **self._auth(self.a["admin"]),
        )
        self.assertEqual(res.status_code, 201)
        created = Levels.objects.get(name="Province")
        self.assertEqual(created.level, 1)
        self.assertEqual(created.tenant, self.a["tenant"])

    def test_rename_always_allowed_even_with_units(self):
        self._unit_below_root(self.a)
        res = self.client.put(
            f"{URL}/{self.a['level0'].id}", {"name": "Country"},
            content_type="application/json", **self._auth(self.a["admin"]),
        )
        self.assertEqual(res.status_code, 200)
        self.a["level0"].refresh_from_db()
        self.assertEqual(self.a["level0"].name, "Country")

    def test_add_frozen_once_units_exist_below_root(self):
        self._unit_below_root(self.a)
        res = self.client.post(
            URL, {"name": "Province"}, content_type="application/json",
            **self._auth(self.a["admin"]),
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Levels.objects.filter(name="Province").exists())

    def test_delete_removes_deepest_only(self):
        lvl1 = Levels.objects.create(
            name="Province", level=1, tenant=self.a["tenant"]
        )
        res0 = self.client.delete(
            f"{URL}/{self.a['level0'].id}", **self._auth(self.a["admin"])
        )
        self.assertEqual(res0.status_code, 400)
        res1 = self.client.delete(
            f"{URL}/{lvl1.id}", **self._auth(self.a["admin"])
        )
        self.assertEqual(res1.status_code, 204)
        self.assertFalse(Levels.objects.filter(id=lvl1.id).exists())

    def test_delete_blocked_when_units_exist(self):
        lvl1 = Levels.objects.create(
            name="Province", level=1, tenant=self.a["tenant"]
        )
        self._unit_below_root(self.a)
        res = self.client.delete(
            f"{URL}/{lvl1.id}", **self._auth(self.a["admin"])
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Levels.objects.filter(id=lvl1.id).exists())

    def test_delete_blocked_when_role_bound(self):
        # Role.administration_level cascades, so an unguarded delete would
        # silently take the role, its access rows and user assignments.
        lvl1 = Levels.objects.create(
            name="Province", level=1, tenant=self.a["tenant"]
        )
        Role.objects.create(name="r", administration_level=lvl1)
        res = self.client.delete(
            f"{URL}/{lvl1.id}", **self._auth(self.a["admin"])
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Levels.objects.filter(id=lvl1.id).exists())

    def test_delete_level_zero_blocked_root_unit_present(self):
        # Level 0 is the deepest and nothing sits below root, so only the
        # unit-at-this-level guard stands between the root and deletion.
        res = self.client.delete(
            f"{URL}/{self.a['level0'].id}", **self._auth(self.a["admin"])
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(
            Levels.objects.filter(id=self.a["level0"].id).exists()
        )

    def test_foreign_level_is_not_found(self):
        res = self.client.put(
            f"{URL}/{self.b['level0'].id}", {"name": "Hijacked"},
            content_type="application/json", **self._auth(self.a["admin"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_non_superadmin_forbidden(self):
        plain = SystemUser.objects.create_user(
            email="plain@acme.org", password="Secret#Pass123",
            first_name="P", last_name="P", tenant=self.a["tenant"],
        )
        res = self.client.get(URL, **self._auth(plain))
        self.assertEqual(res.status_code, 403)
