import pandas as pd
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Entity, Levels
from api.v1.v1_users.models import SystemUser, Tenant
from utils.upload_administration import (
    generate_administration_excel,
    generate_entities_data_excel,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class TemplateTenantScopingTestCase(TestCase):
    """Two tenants whose hierarchies are named differently.

    Every level lookup in the generators read the whole table, so each
    tenant's template carried the other's columns. The names are chosen
    to share no substring, so a leak cannot hide behind a coincidence.
    """

    def setUp(self):
        self.acme = self._tenant("acme", ["Country", "Province"], "Kenya")
        self.beta = self._tenant("beta", ["State", "City"], "Uganda")

    def _tenant(self, sub, level_names, root_name):
        tenant = Tenant.objects.create(subdomain=sub)
        levels = [
            Levels.objects.create(name=name, level=idx, tenant=tenant)
            for idx, name in enumerate(level_names)
        ]
        root = Administration.objects.create(
            parent=None, level=levels[0], name=root_name, tenant=tenant
        )
        admin = SystemUser.objects.create_superuser(
            email=f"a@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        return {
            "tenant": tenant, "levels": levels, "root": root, "admin": admin,
        }

    def test_administration_template_carries_only_its_own_levels(self):
        filepath = generate_administration_excel(self.acme["admin"])
        headers = list(pd.read_excel(filepath, sheet_name="data"))

        joined = " ".join(headers)
        self.assertIn("Country", joined)
        self.assertIn("Province", joined)
        self.assertNotIn("State", joined)
        self.assertNotIn("City", joined)
        # Two columns per level — the name and its code.
        self.assertEqual(len(headers), 4)

    def test_the_template_ships_with_no_data_rows(self):
        # Deliberately empty, including the level-0 column. Writing the
        # root into it would only reach the single row the blank
        # template carries, leaving every row the operator adds below it
        # blank there — and a blank level-0 cell already means the root.
        # It would also put a NaN row under every attribute column,
        # turning integer attributes into "1.0" on upload.
        filepath = generate_administration_excel(self.acme["admin"])
        df = pd.read_excel(filepath, sheet_name="data")
        self.assertEqual(df.shape[0], 0)

    def test_each_tenant_gets_its_own_template(self):
        beta_headers = list(
            pd.read_excel(
                generate_administration_excel(self.beta["admin"]),
                sheet_name="data",
            )
        )
        joined = " ".join(beta_headers)
        self.assertIn("State", joined)
        self.assertNotIn("Country", joined)

    def test_entities_template_carries_only_its_own_levels(self):
        Entity.objects.create(name="School")
        filepath = generate_entities_data_excel(self.acme["admin"])
        headers = list(pd.read_excel(filepath, sheet_name="School"))

        self.assertEqual(headers, ["Name", "Code", "Country", "Province"])
