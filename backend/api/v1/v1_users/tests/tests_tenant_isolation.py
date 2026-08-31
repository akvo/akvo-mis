from django.db.utils import IntegrityError
from django.test.utils import override_settings
from django.urls import NoReverseMatch, reverse

from api.v1.v1_profile.models import Role
from api.v1.v1_users.models import Organisation, SystemUser
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class UsersTenantIsolationTestCase(TenantIsolationTestCase):
    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["org"] = Organisation.objects.create(
            name=f"{sub}-org", tenant=tenant["tenant"]
        )
        tenant["role"] = Role.objects.create(
            name=f"{sub}-role", administration_level=tenant["level"]
        )
        return tenant

    def test_role_options_exclude_other_tenant(self):
        # The role picker on the add-user screen. A role belongs to its
        # level's tenant, so offering every role lets one workspace's admin
        # see — and assign — another's.
        res = self.client.get(
            "/api/v1/user/roles", **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        labels = [r["label"] for r in res.json()]
        self.assertIn(self.a["role"].name, labels)
        self.assertNotIn(self.b["role"].name, labels)

    def test_two_tenants_can_share_a_role_name(self):
        # `name` was globally unique, so the second workspace to want a
        # "Data Entry" role simply could not have one.
        for fixture in (self.a, self.b):
            Role.objects.create(
                name="Data Entry",
                administration_level=fixture["child_level"],
            )
        self.assertEqual(Role.objects.filter(name="Data Entry").count(), 2)

    def test_one_tenant_cannot_repeat_a_role_name(self):
        # Unique per tenant, not per level: the same name at a different
        # tier of the same workspace is still the same role to a human.
        Role.objects.create(
            name="Data Entry", administration_level=self.a["level"]
        )
        with self.assertRaises(IntegrityError):
            Role.objects.create(
                name="Data Entry", administration_level=self.a["child_level"]
            )

    def test_a_role_carries_its_levels_tenant(self):
        # The column is denormalised, so it is only trustworthy if it cannot
        # be set to anything else.
        role = Role.objects.create(
            name="Derived", administration_level=self.b["child_level"]
        )
        self.assertEqual(role.tenant, self.b["tenant"])

    def test_role_options_require_a_session(self):
        # It carried no permission_classes, so DRF's AllowAny default made
        # every tenant's roles readable without a credential at all.
        res = self.client.get("/api/v1/user/roles")
        self.assertEqual(res.status_code, 401)

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

    def test_invite_active_user_from_other_workspace_succeeds(
        self,
    ):
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "Test",
                "last_name": "User",
                "email": self.b["user"].email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)
        created_user = SystemUser.objects.get(
            email=self.b["user"].email,
            tenant=self.a["tenant"],
        )
        self.assertNotEqual(created_user.pk, self.b["user"].pk)
        self.assertEqual(created_user.tenant_id, self.a["tenant"].id)

    def test_invite_soft_deleted_user_from_other_workspace_creates_new_row(
        self,
    ):
        self.b["user"].soft_delete()

        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "Test",
                "last_name": "User",
                "email": self.b["user"].email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)

        # Assert target user in workspace B remains deleted
        # and tenant_id is unchanged
        user_b = SystemUser.objects_with_deleted.get(pk=self.b["user"].pk)
        self.assertEqual(user_b.tenant_id, self.b["tenant"].id)
        self.assertIsNotNone(user_b.deleted_at)

        # Assert new user in workspace A is created and active
        user_a = SystemUser.objects.get(
            email=self.b["user"].email,
            tenant=self.a["tenant"],
        )
        self.assertIsNone(user_a.deleted_at)
        self.assertNotEqual(user_a.pk, user_b.pk)

    def test_invite_pending_user_from_other_workspace_succeeds(
        self,
    ):
        pending_user = SystemUser.objects.create_user(
            email="pending@beta.org",
            password="Secret#Pass123",
            first_name="Pending",
            last_name="User",
            tenant=self.b["tenant"],
            is_active=False,
        )

        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "Test",
                "last_name": "User",
                "email": pending_user.email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)
        created_user = SystemUser.objects.get(
            email=pending_user.email,
            tenant=self.a["tenant"],
        )
        self.assertNotEqual(created_user.pk, pending_user.pk)

    def test_invite_duplicate_in_same_workspace_returns_same_workspace_error(
        self,
    ):
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "Test",
                "last_name": "User",
                "email": self.a["user"].email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()["details"]
        self.assertIn("email", data)
        self.assertIn("already in your workspace", data["email"][0])

    def test_reinvite_soft_deleted_user_in_same_workspace_restores(self):
        # Create a second superuser in workspace A
        # so they can perform the invite
        admin_a2 = SystemUser.objects.create_superuser(
            email="admin2@acme.org",
            password="Secret#Pass123",
            first_name="A2",
            last_name="A2",
            tenant=self.a["tenant"],
        )

        self.a["user"].soft_delete()

        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "Restored",
                "last_name": "User",
                "email": self.a["user"].email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            **self.auth(admin_a2),
        )
        self.assertIn(res.status_code, (200, 201))

        user_a = SystemUser.objects_with_deleted.get(pk=self.a["user"].pk)
        self.assertIsNone(user_a.deleted_at)
        self.assertEqual(user_a.first_name, "Restored")
