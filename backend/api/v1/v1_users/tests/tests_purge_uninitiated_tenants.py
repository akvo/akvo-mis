"""A workspace that never finished signing up is deleted, and its
subdomain comes back.

Every test here ages a tenant with a queryset `update`, because
`created_at` is `auto_now_add` and a plain `save()` would silently
overwrite the backdated value with now.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_users.tasks import (
    purge_uninitiated_tenants,
    uninitiated_tenants,
)


class PurgeUninitiatedTenantsTestCase(TestCase):
    def register(self, subdomain="acme"):
        """Exactly what POST /api/v1/register leaves behind: a tenant
        and one inactive superadmin, and nothing else."""
        tenant = Tenant.objects.create(subdomain=subdomain)
        user = SystemUser.objects.create_superuser(
            email="founder@{0}.org".format(subdomain),
            password="Secret#Pass123",
            first_name="",
            last_name="",
            tenant=tenant,
            is_active=False,
        )
        return tenant, user

    def configure(self, tenant):
        """What POST /api/v1/register/configure creates."""
        level = Levels.objects.create(
            name="National", level=0, tenant=tenant
        )
        return Administration.objects.create(
            parent=None, level=level, name="Kenya", tenant=tenant
        )

    def age(self, tenant, hours):
        """Backdate the claim. `update` bypasses auto_now_add."""
        Tenant.objects.filter(pk=tenant.pk).update(
            created_at=timezone.now() - timedelta(hours=hours)
        )

    def test_a_stale_unconfigured_workspace_is_purged(self):
        tenant, user = self.register()
        self.age(tenant, 49)

        result = purge_uninitiated_tenants()

        self.assertEqual(result["purged"], ["acme"])
        self.assertEqual(result["skipped"], [])
        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())
        self.assertFalse(
            SystemUser.objects_with_deleted.filter(pk=user.pk).exists()
        )

    def test_the_subdomain_can_be_claimed_again(self):
        # The point of the whole feature: not that a row vanished, but
        # that the next customer can have the name.
        tenant, _ = self.register()
        self.age(tenant, 49)

        purge_uninitiated_tenants()

        self.assertTrue(Tenant.objects.create(subdomain="acme").pk)

    def test_a_configured_workspace_survives_however_old(self):
        tenant, _ = self.register()
        self.configure(tenant)
        self.age(tenant, 24 * 365)

        result = purge_uninitiated_tenants()

        self.assertEqual(result["purged"], [])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_a_fresh_unconfigured_workspace_survives(self):
        tenant, _ = self.register()
        self.age(tenant, 47)

        result = purge_uninitiated_tenants()

        self.assertEqual(result["purged"], [])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_a_soft_deleted_workspace_is_left_alone(self):
        tenant, _ = self.register()
        self.age(tenant, 49)
        Tenant.objects.filter(pk=tenant.pk).update(
            deleted_at=timezone.now()
        )

        result = purge_uninitiated_tenants()

        self.assertEqual(result["purged"], [])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_dry_run_reports_without_deleting(self):
        tenant, user = self.register()
        self.age(tenant, 49)

        result = purge_uninitiated_tenants(dry_run=True)

        self.assertEqual(result["purged"], ["acme"])
        self.assertTrue(result["dry_run"])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())
        self.assertTrue(
            SystemUser.objects_with_deleted.filter(pk=user.pk).exists()
        )

    def test_the_window_comes_from_the_setting(self):
        tenant, _ = self.register()
        self.age(tenant, 2)

        with override_settings(TENANT_PURGE_AFTER_HOURS=1):
            result = purge_uninitiated_tenants()

        self.assertEqual(result["purged"], ["acme"])

    def test_a_soft_deleted_registrant_does_not_block_the_purge(self):
        # SystemUser.objects and tenant.users both hide this row, but
        # its PROTECT FK is still there. A purge that reached for the
        # users through the default manager would conclude the
        # workspace owned nothing, then fail on the tenant delete and
        # skip it forever.
        tenant, user = self.register()
        user.soft_delete()
        self.age(tenant, 49)

        result = purge_uninitiated_tenants()

        self.assertEqual(result["purged"], ["acme"])
        self.assertEqual(result["skipped"], [])
        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_a_workspace_that_owns_a_form_is_skipped(self):
        tenant, user = self.register()
        Forms.objects.create(
            name="stray", tenant=tenant, status=FormStatus.published
        )
        self.age(tenant, 49)
        # A second stale workspace, to prove one protected row costs
        # one workspace rather than the whole run.
        other, _ = self.register(subdomain="beta")
        self.age(other, 49)

        result = purge_uninitiated_tenants()

        self.assertEqual(result["skipped"], ["acme"])
        self.assertEqual(result["purged"], ["beta"])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())
        self.assertFalse(Tenant.objects.filter(pk=other.pk).exists())
        # The atomicity invariant: the user hard-delete happens inside
        # the same atomic block as the tenant delete, so a
        # ProtectedError on the tenant rolls the user delete back too.
        self.assertTrue(
            SystemUser.objects_with_deleted.filter(pk=user.pk).exists()
        )

    def test_a_soft_deleted_form_still_protects_its_workspace(self):
        # Forms is a SoftDeletes model, so tenant.forms.all() returns
        # nothing here while the FK still protects. This is the case
        # an enumerated pre-flight guard would get wrong.
        tenant, _ = self.register()
        form = Forms.objects.create(
            name="stray", tenant=tenant, status=FormStatus.published
        )
        form.soft_delete()
        self.age(tenant, 49)

        result = purge_uninitiated_tenants()

        self.assertEqual(result["skipped"], ["acme"])
        self.assertEqual(result["purged"], [])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_configuring_mid_run_saves_the_workspace(self):
        # The registrant finishes /register/configure between the
        # candidate query and the delete. Nothing locks the tenant;
        # what saves it is that it now owns a level and a root, and
        # both FKs are PROTECT.
        tenant, user = self.register()
        self.age(tenant, 49)
        stale_view_of_the_world = uninitiated_tenants()
        self.assertEqual(len(stale_view_of_the_world), 1)
        self.configure(tenant)

        with mock.patch(
            "api.v1.v1_users.tasks.uninitiated_tenants",
            return_value=stale_view_of_the_world,
        ):
            result = purge_uninitiated_tenants()

        self.assertEqual(result["skipped"], ["acme"])
        self.assertEqual(result["purged"], [])
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())
        self.assertTrue(
            Administration.objects.filter(tenant=tenant).exists()
        )
        # Same atomicity invariant as the Forms case above: the
        # rollback on the tenant's ProtectedError must take the user
        # hard-delete with it.
        self.assertTrue(
            SystemUser.objects_with_deleted.filter(pk=user.pk).exists()
        )


class PurgeCommandTestCase(PurgeUninitiatedTenantsTestCase):
    """The command is a thin wrapper, so it is tested thinly: that it
    reaches the task, that --dry-run reaches it too, and that an
    operator can read the answer off the terminal."""

    def run_command(self, *args):
        out = StringIO()
        call_command(
            "purge_uninitiated_tenants", *args, stdout=out, stderr=out
        )
        return out.getvalue()

    def test_the_command_purges(self):
        tenant, _ = self.register()
        self.age(tenant, 49)

        output = self.run_command()

        self.assertIn("acme", output)
        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_the_command_dry_runs(self):
        tenant, _ = self.register()
        self.age(tenant, 49)

        output = self.run_command("--dry-run")

        self.assertIn("Would purge", output)
        self.assertIn("acme", output)
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_the_command_names_what_it_skipped(self):
        tenant, _ = self.register()
        Forms.objects.create(
            name="stray", tenant=tenant, status=FormStatus.published
        )
        self.age(tenant, 49)

        output = self.run_command()

        self.assertIn("Skipped 1", output)
        self.assertIn("acme", output)
