"""The seeders that create users and organisations must honour --tenant.

`seeder.sh --tenant=<sub>` threads one workspace through every step, but
`createsuperuser`, `organisation_seeder`, `fake_organisation_seeder` and
`fake_user_seeder` never took the argument, so each wrote `tenant=NULL`.
A superadmin seeded that way cannot authenticate at its workspace host at
all -- `TenantAwareBackend.authenticate` filters on `tenant=` -- and every
tenant-scoped queryset it does reach resolves to `tenant IS NULL`.

Each command keeps its tenant-less behaviour when --tenant is omitted:
that is how the whole test suite and every single-host install run.
"""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration, Levels, UserRole
from api.v1.v1_users.models import Organisation, SystemUser, Tenant


class TenantHierarchyMixin:
    """A two-level hierarchy owned by one workspace."""

    def make_tenant(self, subdomain):
        tenant = Tenant.objects.create(subdomain=subdomain)
        national = Levels.objects.create(
            name="National", level=0, tenant=tenant
        )
        district = Levels.objects.create(
            name="District", level=1, tenant=tenant
        )
        root = Administration.objects.create(
            name=f"{subdomain} country", level=national, tenant=tenant
        )
        Administration.objects.create(
            name=f"{subdomain} district",
            level=district,
            parent=root,
            tenant=tenant,
        )
        return tenant


@override_settings(USE_TZ=False, TEST_ENV=True)
class CreateSuperUserTenantTestCase(TestCase):
    def test_stamps_the_named_workspace(self):
        tenant = Tenant.objects.create(subdomain="acme")
        call_command(
            "createsuperuser",
            "--noinput",
            email="super@acme.test",
            first_name="Acme",
            last_name="Admin",
            tenant="acme",
        )
        user = SystemUser.objects.get(email="super@acme.test")
        self.assertEqual(user.tenant_id, tenant.id)
        self.assertTrue(user.is_superuser)

    def test_without_tenant_stays_tenant_less(self):
        Tenant.objects.create(subdomain="acme")
        call_command(
            "createsuperuser",
            "--noinput",
            email="super@nowhere.test",
            first_name="No",
            last_name="Tenant",
        )
        user = SystemUser.objects.get(email="super@nowhere.test")
        self.assertIsNone(user.tenant_id)

    def test_rejects_an_unknown_workspace(self):
        # A typo must not silently seed into the tenant-less space --
        # that failure is invisible until the account cannot log in.
        with self.assertRaises(CommandError):
            call_command(
                "createsuperuser",
                "--noinput",
                email="super@typo.test",
                first_name="Ty",
                last_name="Po",
                tenant="acme",
            )
        self.assertFalse(
            SystemUser.objects.filter(email="super@typo.test").exists()
        )

    def test_rejects_a_duplicate_email_without_stranding_the_account(self):
        # Django checks the username field for uniqueness without knowing
        # workspaces exist, so `unique_email_per_tenant` is what actually
        # rejects this -- after the row has been written. Un-atomic, that
        # left a tenant-less superadmin behind on every collision.
        Tenant.objects.create(subdomain="acme")
        call_command(
            "createsuperuser",
            "--noinput",
            email="dupe@acme.test",
            first_name="First",
            last_name="Account",
            tenant="acme",
        )
        with self.assertRaises(CommandError):
            call_command(
                "createsuperuser",
                "--noinput",
                email="dupe@acme.test",
                first_name="Second",
                last_name="Account",
                tenant="acme",
            )
        self.assertEqual(
            SystemUser.objects_with_deleted.filter(
                email="dupe@acme.test"
            ).count(),
            1,
        )
        self.assertEqual(
            SystemUser.objects_with_deleted.filter(tenant=None).count(), 0
        )

    def test_leaves_other_workspaces_alone(self):
        acme = Tenant.objects.create(subdomain="acme")
        beta = Tenant.objects.create(subdomain="beta")
        call_command(
            "createsuperuser",
            "--noinput",
            email="one@acme.test",
            first_name="A",
            last_name="One",
            tenant="acme",
        )
        call_command(
            "createsuperuser",
            "--noinput",
            email="two@beta.test",
            first_name="B",
            last_name="Two",
            tenant="beta",
        )
        self.assertEqual(
            SystemUser.objects.get(email="one@acme.test").tenant_id, acme.id
        )
        self.assertEqual(
            SystemUser.objects.get(email="two@beta.test").tenant_id, beta.id
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class OrganisationSeederTenantTestCase(TestCase):
    def test_stamps_the_named_workspace(self):
        tenant = Tenant.objects.create(subdomain="acme")
        call_command("organisation_seeder", "--test", 1, tenant="acme")
        seeded = Organisation.objects.all()
        self.assertGreater(seeded.count(), 0)
        self.assertEqual(
            seeded.exclude(tenant=tenant).count(),
            0,
            "every seeded organisation belongs to the named workspace",
        )

    def test_seeds_each_workspace_independently(self):
        # The pre-fix lookup was keyed on the CSV's primary key, so the
        # second workspace found the first one's rows and created none.
        acme = Tenant.objects.create(subdomain="acme")
        beta = Tenant.objects.create(subdomain="beta")
        call_command("organisation_seeder", "--test", 1, tenant="acme")
        acme_count = Organisation.objects.filter(tenant=acme).count()
        call_command("organisation_seeder", "--test", 1, tenant="beta")
        beta_count = Organisation.objects.filter(tenant=beta).count()

        self.assertGreater(acme_count, 0)
        self.assertEqual(acme_count, beta_count)
        # Re-seeding the first workspace is still idempotent.
        self.assertEqual(
            Organisation.objects.filter(tenant=acme).count(), acme_count
        )

    def test_without_tenant_keeps_the_csv_primary_keys(self):
        call_command("organisation_seeder", "--test", 1)
        seeded = Organisation.objects.all()
        self.assertGreater(seeded.count(), 0)
        self.assertEqual(seeded.exclude(tenant=None).count(), 0)
        # The tenant-less path inserts explicit ids from the CSV; 1 and 2
        # are its first two rows.
        self.assertTrue(Organisation.objects.filter(pk=1).exists())
        self.assertTrue(Organisation.objects.filter(pk=2).exists())

    def test_rejects_an_unknown_workspace(self):
        with self.assertRaises(CommandError):
            call_command("organisation_seeder", "--test", 1, tenant="nope")


@override_settings(USE_TZ=False, TEST_ENV=True)
class FakeOrganisationSeederTenantTestCase(TestCase):
    def test_stamps_the_named_workspace(self):
        tenant = Tenant.objects.create(subdomain="acme")
        call_command("fake_organisation_seeder", "--repeat", 2, tenant="acme")
        seeded = Organisation.objects.all()
        self.assertGreater(seeded.count(), 0)
        self.assertEqual(seeded.exclude(tenant=tenant).count(), 0)

    def test_without_tenant_stays_tenant_less(self):
        call_command("fake_organisation_seeder", "--repeat", 2)
        self.assertGreater(Organisation.objects.count(), 0)
        self.assertEqual(
            Organisation.objects.exclude(tenant=None).count(), 0
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class AssignFormsTenantTestCase(TestCase):
    """The step seeder.sh runs straight after createsuperuser.

    Email addresses repeat across workspaces, so an unscoped lookup could
    resolve to somebody else's account -- and the form list it handed out
    spanned every workspace on the install.
    """

    def setUp(self):
        self.acme = Tenant.objects.create(subdomain="acme")
        self.beta = Tenant.objects.create(subdomain="beta")
        self.acme_form = Forms.objects.create(
            name="Acme form", tenant=self.acme
        )
        self.beta_form = Forms.objects.create(
            name="Beta form", tenant=self.beta
        )

    def make_user(self, tenant):
        return SystemUser.objects.create(
            email="shared@example.test",
            first_name="Shared",
            last_name="Email",
            tenant=tenant,
        )

    def test_assigns_only_the_users_own_workspace_forms(self):
        user = self.make_user(self.acme)
        call_command("assign_forms", user.email, tenant="acme")
        assigned = user.user_form.all()
        self.assertEqual(assigned.count(), 1)
        self.assertEqual(assigned.first().form_id, self.acme_form.id)

    def test_picks_the_account_in_the_named_workspace(self):
        self.make_user(self.acme)
        beta_user = self.make_user(self.beta)
        call_command("assign_forms", beta_user.email, tenant="beta")
        self.assertEqual(beta_user.user_form.count(), 1)
        self.assertEqual(
            beta_user.user_form.first().form_id, self.beta_form.id
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FakeUserSeederTenantTestCase(TestCase, TenantHierarchyMixin):
    def test_stamps_and_scopes_to_the_named_workspace(self):
        acme = self.make_tenant("acme")
        beta = self.make_tenant("beta")
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder", "--repeat", 2, tenant="acme")

        call_command(
            "fake_user_seeder", "--repeat", 6, "--test", 1, tenant="acme"
        )

        created = SystemUser.objects.all()
        self.assertGreater(created.count(), 0)
        self.assertEqual(
            created.exclude(tenant=acme).count(),
            0,
            "every seeded user belongs to the named workspace",
        )
        self.assertEqual(created.filter(tenant=beta).count(), 0)

        # The administrations they are given must come from the same
        # workspace -- the unscoped lookup picked a root at random from
        # whichever workspace sorted first.
        roles = UserRole.objects.all()
        self.assertGreater(roles.count(), 0)
        self.assertEqual(
            roles.exclude(administration__tenant=acme).count(), 0
        )
        self.assertEqual(roles.exclude(role__tenant=acme).count(), 0)

        # Organisations are workspace-owned too, so the users must not
        # land org-less the way the tenant-scoped fake data seeder does.
        self.assertEqual(
            created.filter(organisation__isnull=True, is_superuser=False)
            .count(),
            0,
        )

    def test_without_tenant_stays_tenant_less(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder", "--repeat", 2)
        call_command("fake_user_seeder", "--repeat", 4, "--test", 1)

        created = SystemUser.objects.all()
        self.assertGreater(created.count(), 0)
        self.assertEqual(created.exclude(tenant=None).count(), 0)

    def test_rejects_an_unknown_workspace(self):
        with self.assertRaises(CommandError):
            call_command(
                "fake_user_seeder", "--repeat", 1, "--test", 1, tenant="nope"
            )

    def test_requires_workspace_hierarchy(self):
        Tenant.objects.create(subdomain="acme")
        with self.assertRaises(CommandError):
            call_command(
                "fake_user_seeder", "--repeat", 1, "--test", 1, tenant="acme"
            )
