from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIRequestFactory

from api.v1.v1_profile.constants import (
    FeatureAccessTypes,
    FeatureTypes,
)
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    RoleFeatureAccess,
    UserRole,
)
from api.v1.v1_users.models import SystemUser, Tenant
from utils.custom_permissions import DashboardAccess


DASHBOARD_ACCESSES = [
    FeatureAccessTypes.dashboard_view,
    FeatureAccessTypes.dashboard_create,
    FeatureAccessTypes.dashboard_edit,
    FeatureAccessTypes.dashboard_publish,
    FeatureAccessTypes.dashboard_delete,
]


@override_settings(USE_TZ=False)
class DashboardConstantsTestCase(TestCase):
    """The five accesses and the group the role editor renders."""

    def test_access_values_continue_from_form_delete(self):
        # 2 stays a gap on purpose: FeatureAccessTypes values are
        # persisted in role_feature_access rows, so reusing a retired
        # number would silently re-point existing grants.
        self.assertEqual(DASHBOARD_ACCESSES, [8, 9, 10, 11, 12])

    def test_every_access_has_a_label(self):
        for access in DASHBOARD_ACCESSES:
            self.assertIn(access, FeatureAccessTypes.FieldStr)

    def test_dashboard_builder_groups_all_five(self):
        # generate_config walks FieldStr and emits each key's FieldGroup
        # members, so this is the whole role-editor integration.
        self.assertEqual(FeatureTypes.dashboard_builder, 3)
        self.assertIn(FeatureTypes.dashboard_builder, FeatureTypes.FieldStr)
        self.assertEqual(
            FeatureTypes.FieldGroup[FeatureTypes.dashboard_builder],
            DASHBOARD_ACCESSES,
        )

    def test_role_feature_payload_builds(self):
        # Mirrors the loop in v1_data/management/commands/generate_config.py.
        # It KeyErrors if either map is missing an entry.
        payload = [
            {
                "id": key,
                "name": value,
                "access": [
                    {
                        "id": access_id,
                        "name": FeatureAccessTypes.FieldStr[access_id],
                    }
                    for access_id in FeatureTypes.FieldGroup[key]
                ],
            }
            for key, value in FeatureTypes.FieldStr.items()
        ]
        builder = [
            f for f in payload if f["id"] == FeatureTypes.dashboard_builder
        ][0]
        self.assertEqual(builder["name"], "Dashboard Builder")
        self.assertEqual(len(builder["access"]), 5)


@override_settings(USE_TZ=False)
class DashboardAccessPermissionTestCase(TestCase):
    """DashboardAccess must gate on type AND access, not either."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.tenant = Tenant.objects.create(subdomain="acme")
        self.level = Levels.objects.create(
            name="National", level=0, tenant=self.tenant
        )
        self.administration = Administration.objects.create(
            parent=None, level=self.level, name="Acme", tenant=self.tenant
        )
        self.user = SystemUser.objects.create_user(
            email="viewer@akvo.org",
            password="Secret#Pass123",
            first_name="View",
            last_name="Er",
            tenant=self.tenant,
        )

    def grant(self, feature_type, access):
        role = Role.objects.create(
            name=f"Role {feature_type}-{access}",
            administration_level=self.level,
        )
        RoleFeatureAccess.objects.create(
            role=role, type=feature_type, access=access
        )
        UserRole.objects.create(
            user=self.user, role=role, administration=self.administration
        )
        return role

    def check(self, user, required_access):
        request = self.factory.get("/")
        request.user = user
        permission = DashboardAccess(required_access)()
        return permission.has_permission(request, view=None)

    def test_denied_without_any_role(self):
        self.assertFalse(
            self.check(self.user, FeatureAccessTypes.dashboard_view)
        )

    def test_granted_with_matching_access(self):
        self.grant(
            FeatureTypes.dashboard_builder,
            FeatureAccessTypes.dashboard_view,
        )
        self.assertTrue(
            self.check(self.user, FeatureAccessTypes.dashboard_view)
        )

    def test_denied_for_a_different_access_in_the_same_group(self):
        self.grant(
            FeatureTypes.dashboard_builder,
            FeatureAccessTypes.dashboard_view,
        )
        self.assertFalse(
            self.check(self.user, FeatureAccessTypes.dashboard_delete)
        )

    def test_denied_when_the_access_belongs_to_another_feature(self):
        # The guard must match on type as well; without it a form_builder
        # grant numbered 8 would open the dashboard builder.
        self.grant(
            FeatureTypes.form_builder,
            FeatureAccessTypes.dashboard_view,
        )
        self.assertFalse(
            self.check(self.user, FeatureAccessTypes.dashboard_view)
        )

    def test_superuser_bypasses_the_check(self):
        superuser = SystemUser.objects.create_superuser(
            email="root@akvo.org",
            password="Secret#Pass123",
            first_name="Root",
            last_name="User",
            tenant=self.tenant,
        )
        self.assertTrue(
            self.check(superuser, FeatureAccessTypes.dashboard_delete)
        )
