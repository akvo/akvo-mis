"""Which levels the roles seeder visits, and whose workspace they belong to.

`Levels.objects` is a plain TenantManager -- it adds `for_user`, not an
implicit filter -- so the seeder's original `Levels.objects.all()` walked
every workspace on the database. One `./seeder.sh --tenant=<sub>` run on a
five-workspace install created roles in four workspaces nobody named. The
rows were valid (Role.save() derives `tenant` from the level), which is why
nothing raised and the leak was visible only in the log.
"""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.constants import (
    DataAccessTypes,
    FeatureAccessTypes,
    FeatureTypes,
)
from api.v1.v1_profile.models import Levels, Role, RoleAccess
from api.v1.v1_users.models import Tenant


class RolesSeederMixin:
    def make_tenant(self, subdomain):
        return Tenant.objects.create(subdomain=subdomain)

    def make_levels(self, tenant, *names):
        return [
            Levels.objects.create(name=name, level=depth, tenant=tenant)
            for depth, name in enumerate(names)
        ]

    def roles_of(self, tenant):
        return set(
            Role.objects.filter(tenant=tenant).values_list("name", flat=True)
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class DefaultRolesSeederTenantScopeTest(RolesSeederMixin, TestCase):
    def setUp(self):
        self.acme = self.make_tenant("acme")
        self.other = self.make_tenant("other")
        # The same level name in both workspaces: the screenshot that
        # started this showed "Roles created for National level." four
        # times and no way to tell which workspace each belonged to.
        self.make_levels(self.acme, "National", "Province")
        self.make_levels(self.other, "National", "County")

    def test_seeds_only_the_named_workspace(self):
        call_command("default_roles_seeder", "--tenant", "acme")

        self.assertEqual(
            self.roles_of(self.acme),
            {
                "National Admin",
                "National Submitter",
                "National Approver",
                "Province Admin",
                "Province Submitter",
                "Province Approver",
            },
        )
        # The regression. Against Levels.objects.all() this set held six
        # roles the operator never asked for.
        self.assertEqual(self.roles_of(self.other), set())

    def test_leaves_the_tenant_less_space_alone(self):
        Levels.objects.create(name="Global", level=0, tenant=None)

        call_command("default_roles_seeder", "--tenant", "acme")

        self.assertEqual(Role.objects.filter(tenant=None).count(), 0)

    def test_no_tenant_means_the_tenant_less_space(self):
        """What the ~140 unmodified `--test 1` call sites rest on.

        They seed levels through `administration_seeder --test`, which
        writes tenant=None, so filter(tenant=None) selects exactly what
        .all() used to select in a test database.
        """
        Levels.objects.create(name="Global", level=0, tenant=None)

        call_command("default_roles_seeder")

        self.assertEqual(
            self.roles_of(None),
            {"Global Admin", "Global Submitter", "Global Approver"},
        )
        self.assertEqual(self.roles_of(self.acme), set())
        self.assertEqual(self.roles_of(self.other), set())

    def test_unknown_subdomain_is_rejected_before_any_write(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("default_roles_seeder", "--tenant", "acmee")

        message = str(ctx.exception)
        self.assertIn("No workspace with subdomain 'acmee'", message)
        self.assertIn("acme", message)
        self.assertEqual(Role.objects.count(), 0)

    def test_same_level_name_in_two_workspaces_does_not_collide(self):
        """`unique_role_name_per_tenant` spans (tenant, name), not name."""
        call_command("default_roles_seeder", "--tenant", "acme")
        call_command("default_roles_seeder", "--tenant", "other")

        self.assertEqual(Role.objects.filter(name="National Admin").count(), 2)

    def test_role_tenant_matches_its_level(self):
        """The derivation the fix leans on -- Role.save() stamps it."""
        call_command("default_roles_seeder", "--tenant", "acme")

        for role in Role.objects.all():
            self.assertEqual(
                role.tenant_id, role.administration_level.tenant_id
            )

    def test_output_names_the_workspace(self):
        out = self.call_and_capture("--tenant", "acme")

        self.assertIn("Roles created for National level (acme).", out)

    def call_and_capture(self, *args):
        from io import StringIO

        buffer = StringIO()
        call_command("default_roles_seeder", *args, stdout=buffer)
        return buffer.getvalue()


@override_settings(USE_TZ=False, TEST_ENV=True)
class DefaultRolesSeederAccessTest(RolesSeederMixin, TestCase):
    def setUp(self):
        self.acme = self.make_tenant("acme")
        self.make_levels(self.acme, "National")
        call_command("default_roles_seeder", "--tenant", "acme")

    def access_of(self, name):
        role = Role.objects.get(name=name)
        return set(
            role.role_role_access.values_list("data_access", flat=True)
        )

    def test_admin_role_has_full_data_access(self):
        self.assertEqual(
            self.access_of("National Admin"),
            {
                DataAccessTypes.read,
                DataAccessTypes.submit,
                DataAccessTypes.edit,
                DataAccessTypes.delete,
            },
        )

    def test_admin_role_has_user_and_form_builder_features(self):
        role = Role.objects.get(name="National Admin")
        features = set(
            role.role_role_feature_access.values_list("type", "access")
        )
        self.assertIn(
            (FeatureTypes.user_access, FeatureAccessTypes.invite_user),
            features,
        )
        self.assertEqual(
            {a for t, a in features if t == FeatureTypes.form_builder},
            {
                FeatureAccessTypes.form_view,
                FeatureAccessTypes.form_create,
                FeatureAccessTypes.form_edit,
                FeatureAccessTypes.form_publish,
                FeatureAccessTypes.form_delete,
            },
        )

    def test_submitter_and_approver_roles(self):
        self.assertEqual(
            self.access_of("National Submitter"),
            {DataAccessTypes.read, DataAccessTypes.submit},
        )
        self.assertEqual(
            self.access_of("National Approver"),
            {DataAccessTypes.read, DataAccessTypes.approve},
        )

    def test_rerunning_creates_no_duplicate_access_rows(self):
        before = RoleAccess.objects.count()

        call_command("default_roles_seeder", "--tenant", "acme")

        self.assertEqual(RoleAccess.objects.count(), before)
        self.assertEqual(Role.objects.filter(tenant=self.acme).count(), 3)
