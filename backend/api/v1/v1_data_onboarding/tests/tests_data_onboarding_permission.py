from django.test.utils import override_settings

from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import Role, RoleFeatureAccess, UserRole
from api.v1.v1_users.models import SystemUser
from utils.tenant_test_case import TenantIsolationTestCase

LIST_URL = "/api/v1/data-onboarding"


@override_settings(USE_TZ=False, BASE_DOMAIN="app.com")
class DataOnboardingPermissionTestCase(TenantIsolationTestCase):
    def host(self):
        return {"HTTP_HOST": f"{self.a['tenant'].subdomain}.app.com"}

    def user_with(self, feature_type, access):
        user = SystemUser.objects.create_user(
            email=f"user-{feature_type}-{access}@acme.org",
            password="Secret#Pass123",
            first_name="U",
            last_name="U",
            tenant=self.a["tenant"],
        )
        role = Role.objects.create(
            name=f"role-{feature_type}-{access}",
            administration_level=self.a["level"],
        )
        RoleFeatureAccess.objects.create(
            role=role, type=feature_type, access=access
        )
        UserRole.objects.create(
            user=user, role=role, administration=self.a["root"]
        )
        return user

    def get(self, url, user):
        return self.client.get(url, **self.auth(user), **self.host())

    def test_constants_continue_after_the_highest_persisted_numbers(self):
        # Values are persisted in role_feature_access rows: never reuse.
        self.assertEqual(FeatureAccessTypes.data_onboard, 13)
        self.assertEqual(FeatureTypes.data_onboarding, 4)
        self.assertEqual(
            FeatureTypes.FieldGroup[FeatureTypes.data_onboarding],
            [FeatureAccessTypes.data_onboard],
        )

    def test_super_admin_lists_without_any_role_grant(self):
        res = self.get(LIST_URL, self.a["user"])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_granted_role_lists(self):
        user = self.user_with(
            FeatureTypes.data_onboarding, FeatureAccessTypes.data_onboard
        )
        res = self.get(LIST_URL, user)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_user_without_the_permission_is_refused(self):
        user = self.user_with(
            FeatureTypes.form_builder, FeatureAccessTypes.form_create
        )
        res = self.get(LIST_URL, user)
        self.assertEqual(res.status_code, 403)

    def test_profile_exposes_the_role_flag(self):
        # The web client builds its CASL ability from these role flags.
        granted = self.user_with(
            FeatureTypes.data_onboarding, FeatureAccessTypes.data_onboard
        )
        other = self.user_with(
            FeatureTypes.form_builder, FeatureAccessTypes.form_view
        )
        roles = self.get("/api/v1/profile", granted).json()["roles"]
        self.assertTrue(roles[0]["can_data_onboard"])
        roles = self.get("/api/v1/profile", other).json()["roles"]
        self.assertFalse(roles[0]["can_data_onboard"])
