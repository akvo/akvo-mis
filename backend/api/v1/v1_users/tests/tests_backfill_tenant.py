import importlib

from django.apps import apps as global_apps
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Levels
from api.v1.v1_users.models import SystemUser, Tenant

# Migration modules start with a digit, so importlib is the only way in.
backfill_migration = importlib.import_module(
    "api.v1.v1_users.migrations.0004_backfill_default_tenant"
)


@override_settings(USE_TZ=False)
class BackfillDefaultTenantTestCase(TestCase):
    def test_backfill_stamps_tenantless_rows_and_is_idempotent(self):
        Levels.objects.create(name="National", level=0)
        user = SystemUser.objects.create_user(
            email="legacy@example.org",
            password="Secret#Pass123",
            first_name="Legacy",
            last_name="User",
        )
        backfill_migration.backfill_default_tenant(global_apps, None)
        tenant = Tenant.objects.get(subdomain="default")
        user.refresh_from_db()
        self.assertEqual(user.tenant, tenant)
        self.assertEqual(Levels.objects.get(level=0).tenant, tenant)
        # Second run: no new tenant, nothing re-stamped.
        backfill_migration.backfill_default_tenant(global_apps, None)
        self.assertEqual(Tenant.objects.filter(subdomain="default").count(), 1)

    def test_rows_with_a_tenant_are_left_alone(self):
        acme = Tenant.objects.create(subdomain="acme")
        level = Levels.objects.create(name="", level=0, tenant=acme)
        backfill_migration.backfill_default_tenant(global_apps, None)
        level.refresh_from_db()
        self.assertEqual(level.tenant, acme)
