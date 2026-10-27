from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class TenantModelTestCase(TestCase):
    def test_superuser_links_to_tenant(self):
        tenant = Tenant.objects.create(subdomain="acme")
        user = SystemUser.objects.create_superuser(
            email="founder@acme.org",
            password="Secret#Pass123",
            first_name="Ada",
            last_name="Founder",
            tenant=tenant,
        )
        self.assertEqual(user.tenant, tenant)
        self.assertEqual(list(tenant.users.all()), [user])

    def test_existing_users_have_no_tenant(self):
        user = SystemUser.objects.create_user(
            email="plain@example.org",
            password="Secret#Pass123",
            first_name="No",
            last_name="Tenant",
        )
        self.assertIsNone(user.tenant)

    def test_tenant_defaults_language_to_en(self):
        tenant = Tenant.objects.create(subdomain="default-lang")
        self.assertEqual(tenant.language, "en")

    def test_tenant_persists_custom_language(self):
        tenant = Tenant.objects.create(
            subdomain="french-workspace", language="fr"
        )
        tenant.refresh_from_db()
        self.assertEqual(tenant.language, "fr")

    def test_tenant_defaults_logo_to_none(self):
        tenant = Tenant.objects.create(subdomain="default-logo")
        self.assertIsNone(tenant.logo)

    def test_tenant_persists_custom_logo(self):
        tenant = Tenant.objects.create(
            subdomain="branded-workspace",
            logo="/images/logo-branded-123.png",
        )
        tenant.refresh_from_db()
        self.assertEqual(tenant.logo, "/images/logo-branded-123.png")

    def test_tenant_defaults_name_to_empty_string(self):
        tenant = Tenant.objects.create(subdomain="default-name")
        self.assertEqual(tenant.name, "")

    def test_tenant_persists_custom_name(self):
        tenant = Tenant.objects.create(
            subdomain="mohhs",
            name="Ministry of Health & Human Services",
        )
        tenant.refresh_from_db()
        self.assertEqual(tenant.name, "Ministry of Health & Human Services")

    def test_tenant_display_name_and_mis_title_properties(self):
        named_tenant = Tenant.objects.create(
            subdomain="mohhs",
            name="Ministry of Health & Human Services",
        )
        self.assertEqual(
            named_tenant.display_name, "Ministry of Health & Human Services"
        )
        self.assertEqual(
            named_tenant.mis_title,
            "Ministry of Health & Human Services MIS",
        )

        already_mis = Tenant.objects.create(
            subdomain="kenya-mis",
            name="Kenya MIS",
        )
        self.assertEqual(already_mis.display_name, "Kenya MIS")
        self.assertEqual(already_mis.mis_title, "Kenya MIS")

        unnamed = Tenant.objects.create(subdomain="legacy")
        self.assertEqual(unnamed.display_name, "legacy")
        self.assertEqual(unnamed.mis_title, "legacy MIS")

    def test_backfill_tenant_name_from_subdomain(self):
        import importlib

        migration = importlib.import_module(
            "api.v1.v1_users.migrations.0014_tenant_name"
        )
        backfill_tenant_name = migration.backfill_tenant_name

        tenant = Tenant.objects.create(subdomain="backfill-me", name="")
        tenant_with_name = Tenant.objects.create(
            subdomain="leave-me", name="Already Named"
        )

        class DummyApps:
            def get_model(self, app_label, model_name):
                return Tenant

        backfill_tenant_name(DummyApps(), None)

        tenant.refresh_from_db()
        tenant_with_name.refresh_from_db()

        self.assertEqual(tenant.name, "backfill-me")
        self.assertEqual(tenant_with_name.name, "Already Named")
