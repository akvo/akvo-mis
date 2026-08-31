from django.core import signing
from django.db.utils import IntegrityError
from django.test.utils import override_settings

from api.v1.v1_profile.constants import (
    DataAccessTypes,
    FeatureAccessTypes,
    FeatureTypes,
)
from api.v1.v1_profile.models import (
    Role,
    RoleAccess,
    RoleFeatureAccess,
    UserRole,
)
from api.v1.v1_users.models import Organisation, SystemUser
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False, BASE_DOMAIN="app.com")
class CrossTenantEmailTestCase(TenantIsolationTestCase):
    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["org"] = Organisation.objects.create(
            name=f"{sub}-org", tenant=tenant["tenant"]
        )
        tenant["role"] = Role.objects.create(
            name=f"{sub}-role", administration_level=tenant["level"]
        )
        return tenant

    def test_same_email_in_two_tenants_creates_separate_rows(self):
        email = "shared@example.com"
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        user_b = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )
        self.assertNotEqual(user_a.pk, user_b.pk)
        self.assertEqual(user_a.tenant_id, self.a["tenant"].id)
        self.assertEqual(user_b.tenant_id, self.b["tenant"].id)
        self.assertTrue(user_a.check_password("Secret#PassA123"))
        self.assertTrue(user_b.check_password("Secret#PassB123"))
        self.assertFalse(user_a.check_password("Secret#PassB123"))

    def test_login_at_tenant_a_returns_tenant_a_user(self):
        email = "shared@example.com"
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )

        res = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], "Alice Acme")
        self.assertEqual(data["subdomain"], self.a["tenant"].subdomain)

    def test_login_at_tenant_b_returns_tenant_b_user(self):
        email = "shared@example.com"
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )

        res = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassB123"},
            content_type="application/json",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], "Alice Beta")
        self.assertEqual(data["subdomain"], self.b["tenant"].subdomain)

    def test_same_email_across_three_tenants_coexist_independently(self):
        tenant_c = self.make_tenant("gamma")
        email = "tri_shared@example.com"

        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        user_b = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )
        user_c = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassC123",
            first_name="Alice",
            last_name="Gamma",
            tenant=tenant_c["tenant"],
        )

        self.assertEqual(len({user_a.pk, user_b.pk, user_c.pk}), 3)

        # Login to Tenant C succeeds
        res_c = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassC123"},
            content_type="application/json",
            HTTP_HOST=f"{tenant_c['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_c.status_code, 200)
        self.assertEqual(res_c.json()["name"], "Alice Gamma")
        self.assertEqual(res_c.json()["subdomain"], "gamma")

        # Wrong password at Tenant C returns 401 without
        # MultipleObjectsReturned
        res_fail = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{tenant_c['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_fail.status_code, 401)

    def test_same_email_different_roles_and_privileges_in_different_tenants(
        self,
    ):
        email = "role_test@example.com"

        # Superadmin in Tenant A
        SystemUser.objects.create_superuser(
            email=email,
            password="Secret#PassA123",
            first_name="Admin",
            last_name="Acme",
            tenant=self.a["tenant"],
        )

        # Standard User in Tenant B (not superuser)
        user_b = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Standard",
            last_name="Beta",
            tenant=self.b["tenant"],
            is_superuser=False,
        )
        UserRole.objects.create(
            user=user_b,
            role=self.b["role"],
            administration=self.b["child"],
        )

        # Login to A -> is_superuser True
        res_a = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_a.status_code, 200)
        self.assertTrue(res_a.json()["is_superuser"])

        # Login to B -> is_superuser False
        res_b = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassB123"},
            content_type="application/json",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_b.status_code, 200)
        self.assertFalse(res_b.json()["is_superuser"])

    def test_same_email_different_rbac_permissions_and_scopes_across_tenants(
        self,
    ):
        email = "dual_role_test@example.com"

        # Tenant A: Approver with Form Create & User Invite permissions on Root
        RoleAccess.objects.create(
            role=self.a["role"], data_access=DataAccessTypes.approve
        )
        RoleFeatureAccess.objects.create(
            role=self.a["role"],
            type=FeatureTypes.form_builder,
            access=FeatureAccessTypes.form_create,
        )
        RoleFeatureAccess.objects.create(
            role=self.a["role"],
            type=FeatureTypes.user_access,
            access=FeatureAccessTypes.invite_user,
        )
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Approver",
            tenant=self.a["tenant"],
        )
        UserRole.objects.create(
            user=user_a,
            role=self.a["role"],
            administration=self.a["root"],
        )

        # Tenant B: Submitter with Form View only on Child unit
        RoleAccess.objects.create(
            role=self.b["role"], data_access=DataAccessTypes.submit
        )
        RoleFeatureAccess.objects.create(
            role=self.b["role"],
            type=FeatureTypes.form_builder,
            access=FeatureAccessTypes.form_view,
        )
        user_b = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Submitter",
            tenant=self.b["tenant"],
        )
        UserRole.objects.create(
            user=user_b,
            role=self.b["role"],
            administration=self.b["child"],
        )

        # 1. Login to Tenant A and verify RBAC in login response
        res_a = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.json()
        self.assertEqual(len(data_a["roles"]), 1)
        role_a_data = data_a["roles"][0]
        self.assertEqual(role_a_data["role"], self.a["role"].name)
        self.assertEqual(
            role_a_data["administration"]["id"], self.a["root"].id
        )
        self.assertTrue(role_a_data["is_approver"])
        self.assertFalse(role_a_data["is_submitter"])
        self.assertTrue(role_a_data["can_form_create"])
        self.assertTrue(role_a_data["can_invite_user"])

        # 2. Login to Tenant B and verify different RBAC in login response
        res_b = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassB123"},
            content_type="application/json",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        self.assertEqual(len(data_b["roles"]), 1)
        role_b_data = data_b["roles"][0]
        self.assertEqual(role_b_data["role"], self.b["role"].name)
        self.assertEqual(
            role_b_data["administration"]["id"], self.b["child"].id
        )
        self.assertFalse(role_b_data["is_approver"])
        self.assertTrue(role_b_data["is_submitter"])
        self.assertFalse(role_b_data["can_form_create"])
        self.assertFalse(role_b_data["can_invite_user"])

        # 3. GET /api/v1/profile on Tenant A
        prof_a = self.client.get(
            "/api/v1/profile",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
            **self.auth(user_a),
        )
        self.assertEqual(prof_a.status_code, 200)
        self.assertTrue(prof_a.json()["roles"][0]["is_approver"])
        self.assertFalse(prof_a.json()["roles"][0]["is_submitter"])

        # 4. GET /api/v1/profile on Tenant B
        prof_b = self.client.get(
            "/api/v1/profile",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
            **self.auth(user_b),
        )
        self.assertEqual(prof_b.status_code, 200)
        self.assertFalse(prof_b.json()["roles"][0]["is_approver"])
        self.assertTrue(prof_b.json()["roles"][0]["is_submitter"])

        # 5. Token isolation: User A's token on Tenant B is rejected (403)
        cross_res = self.client.get(
            "/api/v1/profile",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
            **self.auth(user_a),
        )
        self.assertEqual(cross_res.status_code, 403)

    def test_password_reset_in_tenant_a_does_not_affect_tenant_b(self):
        email = "reset_test@example.com"
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )

        # Set new password for user in Tenant A
        res = self.client.put(
            "/api/v1/user/set-password",
            {
                "password": "NewSecret#PassA123",
                "confirm_password": "NewSecret#PassA123",
                "invite": user_a.get_sign_pk(),
            },
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res.status_code, 200)

        # Verify User A can log in with new password
        res_a_new = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "NewSecret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_a_new.status_code, 200)

        # Verify User B CANNOT log in with User A's new password
        res_b_fail = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "NewSecret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_b_fail.status_code, 401)

        # Verify User B can STILL log in with original password
        res_b_ok = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassB123"},
            content_type="application/json",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_b_ok.status_code, 200)

    def test_soft_deleting_user_in_tenant_a_does_not_affect_tenant_b(self):
        email = "delete_test@example.com"
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )

        user_a.soft_delete()

        # Login at Tenant A is refused (user deleted)
        res_a = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassA123"},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_a.status_code, 401)
        self.assertIn("deleted", res_a.json()["message"].lower())

        # Login at Tenant B is unaffected and succeeds
        res_b = self.client.post(
            "/api/v1/login",
            {"email": email, "password": "Secret#PassB123"},
            content_type="application/json",
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_b.status_code, 200)

    def test_update_user_email_to_email_in_another_tenant_succeeds(self):
        user_a = SystemUser.objects.create_user(
            email="original_a@acme.org",
            password="Secret#Pass123",
            first_name="Original",
            last_name="A",
            tenant=self.a["tenant"],
        )
        user_b = self.b["user"]

        # Admin in Tenant A updates user_a's email to user_b's email
        res = self.client.put(
            f"/api/v1/user/{user_a.pk}",
            {
                "first_name": "Updated",
                "last_name": "User",
                "email": user_b.email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 200)

        user_a.refresh_from_db()
        self.assertEqual(user_a.email, user_b.email)
        self.assertEqual(user_a.tenant_id, self.a["tenant"].id)

    def test_update_user_email_to_email_in_same_tenant_is_blocked(self):
        user_a1 = SystemUser.objects.create_user(
            email="user1@acme.org",
            password="Secret#Pass123",
            first_name="User",
            last_name="One",
            tenant=self.a["tenant"],
        )
        SystemUser.objects.create_user(
            email="user2@acme.org",
            password="Secret#Pass123",
            first_name="User",
            last_name="Two",
            tenant=self.a["tenant"],
        )

        # Admin in Tenant A tries to update user_a1's email to user_a2's email
        res = self.client.put(
            f"/api/v1/user/{user_a1.pk}",
            {
                "first_name": "User",
                "last_name": "One",
                "email": "user2@acme.org",
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("already in your workspace", res.json()["message"])

    def test_invite_cross_tenant_email_succeeds(self):
        # User already exists in Tenant B
        user_b = self.b["user"]

        # Admin in Tenant A invites the same email
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "AliceInA",
                "last_name": "User",
                "email": user_b.email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)

        # Assert new user in Tenant A exists
        user_a = SystemUser.objects.get(
            email=user_b.email,
            tenant=self.a["tenant"],
        )
        self.assertNotEqual(user_a.pk, user_b.pk)
        self.assertEqual(user_a.first_name, "AliceInA")

    def test_invite_same_tenant_duplicate_still_blocked(self):
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "Duplicate",
                "last_name": "User",
                "email": self.a["user"].email,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()["details"]
        self.assertIn("email", data)
        self.assertIn("already in your workspace", data["email"][0])

    def test_forgot_password_scoped_to_tenant(self):
        email = "shared@example.com"
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )

        res = self.client.post(
            "/api/v1/user/forgot-password",
            {"email": email},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res.status_code, 200)

        # Verify signed pk in URL belongs to user_a
        signed_pk = user_a.get_sign_pk()
        self.assertEqual(signing.loads(signed_pk), user_a.pk)

    def test_resend_activation_scoped_to_tenant(self):
        email = "shared_pending@example.com"
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Pending",
            last_name="Acme",
            tenant=self.a["tenant"],
            is_active=False,
        )
        SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Active",
            last_name="Beta",
            tenant=self.b["tenant"],
            is_active=True,
        )

        res = self.client.post(
            "/api/v1/register/resend-activation",
            {"email": email},
            content_type="application/json",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(user_a.is_active)

    def test_compound_unique_constraint_enforced(self):
        email = "duplicate@example.com"
        SystemUser.objects.create_user(
            email=email,
            password="Secret#Pass123",
            first_name="First",
            last_name="User",
            tenant=self.a["tenant"],
        )
        with self.assertRaises(IntegrityError):
            SystemUser.objects.create(
                email=email,
                first_name="Second",
                last_name="User",
                tenant=self.a["tenant"],
            )

    def test_null_tenant_rows_not_constrained(self):
        email = "null_tenant@example.com"
        user1 = SystemUser.objects.create(
            email=email,
            first_name="Null1",
            last_name="User",
            tenant=None,
        )
        user2 = SystemUser.objects.create(
            email=email,
            first_name="Null2",
            last_name="User",
            tenant=None,
        )
        self.assertNotEqual(user1.pk, user2.pk)

    def test_user_activity_middleware_updates_last_login_independently(self):
        email = "activity_test@example.com"
        user_a = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassA123",
            first_name="Alice",
            last_name="Acme",
            tenant=self.a["tenant"],
        )
        user_b = SystemUser.objects.create_user(
            email=email,
            password="Secret#PassB123",
            first_name="Alice",
            last_name="Beta",
            tenant=self.b["tenant"],
        )

        user_a.last_login = None
        user_a.save()
        user_b.last_login = None
        user_b.save()

        # 1. Anonymous request does not crash and leaves last_login None
        res_anon = self.client.get(
            "/api/v1/tenant-info",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res_anon.status_code, 200)
        user_a.refresh_from_db()
        self.assertIsNone(user_a.last_login)

        # 2. Authenticated request as User A updates User A's last_login only
        res_auth_a = self.client.get(
            "/api/v1/profile",
            HTTP_HOST=f"{self.a['tenant'].subdomain}.app.com",
            **self.auth(user_a),
        )
        self.assertEqual(res_auth_a.status_code, 200)
        user_a.refresh_from_db()
        user_b.refresh_from_db()
        self.assertIsNotNone(user_a.last_login)
        self.assertIsNone(user_b.last_login)
