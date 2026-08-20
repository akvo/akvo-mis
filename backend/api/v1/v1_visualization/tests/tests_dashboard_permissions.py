from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings

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


class DashboardConstantsTestCase(SimpleTestCase):
    """The five accesses and the group the role editor renders."""

    def test_access_values_continue_from_form_delete(self):
        # 2 stays a gap on purpose: FeatureAccessTypes values are
        # persisted in role_feature_access rows, so reusing a retired
        # number would silently re-point existing grants.
        self.assertEqual(DASHBOARD_ACCESSES, [8, 9, 10, 11, 12])

    def test_dashboard_builder_groups_all_five(self):
        # generate_config walks FieldStr and emits each key's FieldGroup
        # members, so this is the whole role-editor integration.
        self.assertEqual(FeatureTypes.dashboard_builder, 3)
        self.assertEqual(
            FeatureTypes.FieldGroup[FeatureTypes.dashboard_builder],
            DASHBOARD_ACCESSES,
        )

    def test_every_feature_group_resolves(self):
        # generate_config walks FieldStr, then FieldGroup[key], then
        # FeatureAccessTypes.FieldStr[access_id]. A desync between any two
        # of those maps KeyErrors here instead of at config-generation.
        for key in FeatureTypes.FieldStr:
            for access_id in FeatureTypes.FieldGroup[key]:
                FeatureAccessTypes.FieldStr[access_id]


@override_settings(USE_TZ=False)
class DashboardAccessPermissionTestCase(TestCase):
    """DashboardAccess must gate on type AND access, not either."""

    def setUp(self):
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

    def check(self, user, required_access):
        # DashboardAccess reads request.user and nothing else.
        request = SimpleNamespace(user=user)
        return DashboardAccess(required_access)().has_permission(
            request, view=None
        )

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

    def test_denied_when_the_two_halves_come_from_different_rows(self):
        # DashboardAccess matches type and access inside a single
        # .filter(role__role_role_feature_access__type=...,
        # access=...) call, so both conditions must be satisfied by the
        # same role_feature_access row. This test fails if that filter
        # is ever split into two chained .filter() calls: Django then
        # joins role_role_feature_access twice (once per call), and a
        # role holding "the right type" on one access row and "the
        # right access" on another row of its own would wrongly pass,
        # even though no single row has both.
        #
        # Note this needs the two halves on one role's two access rows,
        # not two different roles/UserRole rows: a per-role .filter()
        # is scoped to that role's own role_role_feature_access set
        # either way, so splitting the filter across separate roles
        # does not, by itself, reproduce the cross-row leak.
        role = Role.objects.create(
            name="Half type, half access",
            administration_level=self.level,
        )
        RoleFeatureAccess.objects.create(
            role=role,
            type=FeatureTypes.form_builder,
            access=FeatureAccessTypes.dashboard_view,
        )
        RoleFeatureAccess.objects.create(
            role=role,
            type=FeatureTypes.dashboard_builder,
            access=FeatureAccessTypes.form_view,
        )
        UserRole.objects.create(
            user=self.user, role=role, administration=self.administration
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
