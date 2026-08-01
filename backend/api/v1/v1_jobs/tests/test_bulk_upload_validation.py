from io import BytesIO

import pandas as pd
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_jobs.administrations_bulk_upload import (
    seed_administration_data,
    validate_administrations_bulk_upload,
)
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


def write_excel(columns, rows) -> BytesIO:
    iofile = BytesIO()
    writer = pd.ExcelWriter(iofile, engine="xlsxwriter")
    pd.DataFrame(rows, columns=columns).to_excel(
        writer, sheet_name="data", index=False
    )
    writer.save()
    return iofile


@override_settings(USE_TZ=False, TEST_ENV=True)
class BulkUploadValidationTestCase(TestCase):
    """Two configured tenants, each with a named root and one tier below.

    Both use the same unit name, "Nairobi", because that is the case the
    tenant filter exists for: without it the name alone decided which
    row an upload attached to.
    """

    def setUp(self):
        self.acme = self._tenant("acme", ["Country", "Province"], "Kenya")
        self.beta = self._tenant("beta", ["State", "City"], "Uganda")
        # Tenant B already owns a unit whose name A is about to upload.
        self.beta_nairobi = Administration.objects.create(
            parent=self.beta["root"], level=self.beta["levels"][1],
            name="Nairobi", tenant=self.beta["tenant"],
        )

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

    def _columns(self, fixture):
        return [
            col
            for lvl in fixture["levels"]
            for col in [f"{lvl.id}|{lvl.name}", f"{lvl.id}|{lvl.name} Code"]
        ]

    def _acme_file(self, rows):
        columns = self._columns(self.acme)
        named = []
        for root, child in rows:
            named.append({columns[0]: root, columns[2]: child})
        return write_excel(columns, named)

    def _acme_units(self):
        return Administration.objects.filter(tenant=self.acme["tenant"])

    def _validate(self, iofile):
        return validate_administrations_bulk_upload(
            iofile, tenant=self.acme["tenant"]
        )

    def test_a_valid_file_validates_clean(self):
        # Paired with the rejections below: without this, each of them
        # would pass just as well against a validator that refused
        # everything.
        errors = self._validate(self._acme_file([("Kenya", "Nairobi")]))
        self.assertEqual(errors, [])

    def test_blank_row_is_rejected_and_names_the_row(self):
        iofile = self._acme_file(
            [("Kenya", "Nairobi"), (None, None), ("Kenya", "Mombasa")]
        )
        errors = self._validate(iofile)
        self.assertTrue(errors)
        self.assertTrue(
            any("3" in str(e.get("cell", "")) for e in errors),
            f"no error named row 3: {errors}",
        )

    def test_a_blank_root_cell_means_the_root(self):
        # The template does not pre-fill the level-0 column, so this is
        # the ordinary shape of an uploaded row: the operator fills only
        # the tiers below the root.
        iofile = self._acme_file([(None, "Nairobi")])
        self.assertEqual(self._validate(iofile), [])

        seed_administration_data(iofile, tenant=self.acme["tenant"])
        child = self._acme_units().get(name="Nairobi")
        self.assertEqual(child.parent, self.acme["root"])
        self.assertEqual(
            self._acme_units().filter(parent__isnull=True).count(), 1
        )

    def test_root_mismatch_is_rejected(self):
        errors = self._validate(self._acme_file([("Wrongland", "Nairobi")]))
        self.assertTrue(errors)
        self.assertTrue(
            any("Kenya" in e.get("error_message", "") for e in errors),
            f"the error should name the expected root: {errors}",
        )

    def test_valid_file_builds_under_the_existing_root(self):
        seed_administration_data(
            self._acme_file([("Kenya", "Nairobi")]),
            tenant=self.acme["tenant"],
        )
        roots = self._acme_units().filter(parent__isnull=True)
        self.assertEqual(roots.count(), 1)
        self.assertEqual(roots.first().pk, self.acme["root"].pk)
        child = self._acme_units().get(name="Nairobi")
        self.assertEqual(child.parent, self.acme["root"])

    def test_an_upload_never_attaches_to_another_tenants_unit(self):
        seed_administration_data(
            self._acme_file([("Kenya", "Nairobi")]),
            tenant=self.acme["tenant"],
        )
        acme_nairobi = self._acme_units().get(name="Nairobi")
        self.assertNotEqual(acme_nairobi.pk, self.beta_nairobi.pk)
        self.beta_nairobi.refresh_from_db()
        self.assertEqual(self.beta_nairobi.parent, self.beta["root"])

    def test_a_blank_row_no_longer_truncates_the_rest(self):
        # The backstop behind the validator: seeding a file with a blank
        # middle row used to break the record loop, silently dropping
        # every row after it and reporting success.
        seed_administration_data(
            self._acme_file(
                [("Kenya", "Nairobi"), (None, None), ("Kenya", "Mombasa")]
            ),
            tenant=self.acme["tenant"],
        )
        self.assertTrue(self._acme_units().filter(name="Mombasa").exists())

    def test_another_tenants_levels_do_not_shift_the_columns(self):
        # The validator counted levels across every tenant, so it split
        # the spreadsheet's columns at the wrong index and compared each
        # header against the wrong level.
        errors = self._validate(self._acme_file([("Kenya", "Nairobi")]))
        self.assertEqual(errors, [])
        self.assertEqual(
            Levels.objects.filter(tenant=self.acme["tenant"]).count(), 2
        )
        self.assertEqual(Levels.objects.count(), 4)
