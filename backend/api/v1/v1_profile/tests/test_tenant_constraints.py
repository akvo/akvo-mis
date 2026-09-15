from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import Organisation, Tenant


@override_settings(USE_TZ=False)
class TenantConstraintsTestCase(TestCase):
    def setUp(self):
        self.acme = Tenant.objects.create(subdomain="acme")
        self.beta = Tenant.objects.create(subdomain="beta")

    def test_same_level_number_allowed_across_tenants(self):
        Levels.objects.create(name="", level=0, tenant=self.acme)
        Levels.objects.create(name="", level=0, tenant=self.beta)
        self.assertEqual(Levels.objects.filter(level=0).count(), 2)

    def test_duplicate_level_number_rejected_within_tenant(self):
        Levels.objects.create(name="", level=0, tenant=self.acme)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Levels.objects.create(name="other", level=0, tenant=self.acme)

    def test_tenantless_levels_stay_unconstrained(self):
        # Test seeders create tenant-less rows; NULLs are distinct, so the
        # per-tenant constraint must not apply to them.
        Levels.objects.create(name="", level=0)
        Levels.objects.create(name="", level=0)
        self.assertEqual(
            Levels.objects.filter(level=0, tenant__isnull=True).count(), 2
        )

    def test_one_root_administration_per_tenant(self):
        level = Levels.objects.create(name="", level=0, tenant=self.acme)
        Administration.objects.create(
            parent=None, level=level, name="a", tenant=self.acme
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Administration.objects.create(
                    parent=None, level=level, name="b", tenant=self.acme
                )

    def test_roots_allowed_across_tenants(self):
        acme_level = Levels.objects.create(name="", level=0, tenant=self.acme)
        beta_level = Levels.objects.create(name="", level=0, tenant=self.beta)
        Administration.objects.create(
            parent=None, level=acme_level, name="a", tenant=self.acme
        )
        Administration.objects.create(
            parent=None, level=beta_level, name="b", tenant=self.beta
        )
        self.assertEqual(
            Administration.objects.filter(parent__isnull=True).count(), 2
        )

    def test_organisation_name_unique_per_tenant_only(self):
        Organisation.objects.create(name="MoH", tenant=self.acme)
        Organisation.objects.create(name="MoH", tenant=self.beta)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Organisation.objects.create(name="MoH", tenant=self.acme)
