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
