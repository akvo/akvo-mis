from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import Organisation, SystemUser, Tenant


@override_settings(USE_TZ=False)
class ForUserMechanismTestCase(TestCase):
    def setUp(self):
        self.acme = Tenant.objects.create(subdomain="acme")
        self.beta = Tenant.objects.create(subdomain="beta")
        self.acme_user = SystemUser.objects.create_superuser(
            email="a@acme.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=self.acme,
        )
        self.acme_level = Levels.objects.create(
            name="", level=0, tenant=self.acme
        )
        self.beta_level = Levels.objects.create(
            name="", level=0, tenant=self.beta
        )
        self.acme_root = Administration.objects.create(
            parent=None, level=self.acme_level, name="acme", tenant=self.acme
        )
        Administration.objects.create(
            parent=None, level=self.beta_level, name="beta", tenant=self.beta
        )
        self.acme_form = Forms.objects.create(name="F", tenant=self.acme)
        Forms.objects.create(name="G", tenant=self.beta)
        Organisation.objects.create(name="Org", tenant=self.acme)
        Organisation.objects.create(name="Org2", tenant=self.beta)

    def test_direct_fk_model_scopes_to_tenant(self):
        levels = Levels.objects.for_user(self.acme_user)
        self.assertEqual(list(levels), [self.acme_level])

    def test_forms_scope_to_tenant(self):
        self.assertEqual(
            list(Forms.objects.for_user(self.acme_user)), [self.acme_form]
        )

    def test_organisation_scopes_to_tenant(self):
        self.assertEqual(
            Organisation.objects.for_user(self.acme_user).count(), 1
        )

    def test_tenantless_user_matches_tenantless_rows(self):
        Levels.objects.create(name="legacy", level=0)  # tenant is NULL
        legacy = SystemUser.objects.create_superuser(
            email="legacy@x.org", password="Secret#Pass123",
            first_name="L", last_name="L",
        )
        scoped = Levels.objects.for_user(legacy)
        self.assertEqual(scoped.count(), 1)
        self.assertTrue(all(lv.tenant_id is None for lv in scoped))
