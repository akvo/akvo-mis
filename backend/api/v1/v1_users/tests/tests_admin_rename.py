import json
import os

from django.test import TestCase, override_settings

from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser
from utils.custom_generator import sqlite_path
from utils.tenant_host import resolve_tenant_from_host

ADMIN_HOST = "admin.app.com"


@override_settings(BASE_DOMAIN="app.com")
class AdminRenameTestCase(TestCase, TenantTestHelperMixin):
    """Renaming changes the workspace's address, and says what breaks.

    There is no alias table, so the old address stops working at once.
    The mitigation is that the operator is told, in counts taken from
    this workspace rather than in a generic warning.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.auth = self.bearer(self.operator)
        MobileAssignment.objects.create_assignment(
            user=self.acme.admin, name="device-1"
        )

    def base(self):
        return f"/api/v1/admin/tenants/{self.acme.tenant.pk}"

    def rename(self, subdomain):
        return self.client.post(
            f"{self.base()}/rename",
            json.dumps({"subdomain": subdomain}),
            content_type="application/json",
            HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )

    def test_impact_counts_this_workspace(self):
        response = self.client.get(
            f"{self.base()}/rename-impact", HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mobile_devices"], 1)

    def test_rename_moves_the_address(self):
        self.assertEqual(self.rename("moh-hss").status_code, 200)
        self.acme.tenant.refresh_from_db()
        self.assertEqual(self.acme.tenant.subdomain, "moh-hss")
        self.assertIsNotNone(resolve_tenant_from_host("moh-hss.app.com"))
        # No alias table: the old address is gone immediately.
        self.assertIsNone(resolve_tenant_from_host("acme.app.com"))

    def test_refuses_a_taken_subdomain(self):
        self.create_tenant("beta", ["Country"], "Uganda")
        self.assertEqual(self.rename("beta").status_code, 400)

    def test_refuses_the_reserved_subdomain(self):
        self.assertEqual(self.rename("admin").status_code, 400)

    def test_refuses_a_malformed_subdomain(self):
        self.assertEqual(self.rename("-nope-").status_code, 400)
        self.assertEqual(self.rename("Not Valid").status_code, 400)

    def test_moves_the_master_data_directory(self):
        from api.v1.v1_profile.models import Administration

        old = sqlite_path(Administration, tenant=self.acme.tenant)
        os.makedirs(os.path.dirname(old), exist_ok=True)
        with open(old, "w") as handle:
            handle.write("x")
        self.rename("moh-hss")
        self.acme.tenant.refresh_from_db()
        new = sqlite_path(Administration, tenant=self.acme.tenant)
        self.assertTrue(os.path.exists(new))
        self.assertFalse(os.path.exists(old))

    def test_rename_survives_a_directory_move_failure(self):
        # The files regenerate lazily on the next device sync, so a
        # failed move must not fail the rename -- leaving a workspace
        # half-renamed would be far worse than a slow first sync.
        from unittest import mock

        with mock.patch(
            "api.v1.v1_users.admin_views.os.rename",
            side_effect=OSError("nope"),
        ):
            self.assertEqual(self.rename("moh-hss").status_code, 200)
        self.acme.tenant.refresh_from_db()
        self.assertEqual(self.acme.tenant.subdomain, "moh-hss")
