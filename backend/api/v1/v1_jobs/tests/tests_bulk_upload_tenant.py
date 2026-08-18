from django.test.utils import override_settings

from api.v1.v1_jobs.administrations_bulk_upload import seed_administrations
from api.v1.v1_profile.models import Administration, Levels
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class BulkUploadTenantTestCase(TenantIsolationTestCase):
    """Spreadsheet onboarding is the largest data-entry path.

    Rows created there must belong to the uploader's tenant, or the whole
    onboarding flow produces data nobody can see.
    """

    def test_bulk_created_administrations_carry_the_tenant(self):
        # A real upload names the tenant's existing root in its first
        # column; the seeder matches it and builds the subtree beneath.
        created = seed_administrations(
            [
                (self.a["level"], self.a["root"].name, None),
                (self.a["child_level"], "District One", "D1"),
            ],
            tenant=self.a["tenant"],
        )
        self.assertEqual(created.name, "District One")
        self.assertEqual(created.parent, self.a["root"])
        self.assertEqual(created.tenant, self.a["tenant"])

    def test_bulk_upload_does_not_reuse_another_tenants_unit(self):
        # The existing-row lookup matches on name within the tenant. An
        # unscoped match would silently attach B's subtree to A's upload.
        for t in (self.a, self.b):
            seed_administrations(
                [
                    (t["level"], t["root"].name, None),
                    (t["child_level"], "Shared Name", "S1"),
                ],
                tenant=t["tenant"],
            )
        rows = Administration.objects.filter(name="Shared Name")
        self.assertEqual(rows.count(), 2)
        self.assertEqual(
            set(rows.values_list("tenant__subdomain", flat=True)),
            {"acme", "beta"},
        )

    def test_tenantless_upload_still_produces_tenantless_rows(self):
        # The seeders call this with no tenant; that path must not change.
        level = Levels.objects.create(name="legacy", level=0)
        seed_administrations([(level, "Legacy Unit", "L1")])
        self.assertIsNone(
            Administration.objects.get(name="Legacy Unit").tenant
        )
