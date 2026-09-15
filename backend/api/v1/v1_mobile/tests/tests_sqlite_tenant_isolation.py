import os
import shutil
import sqlite3

import pandas as pd
from django.core.management import call_command
from django.test.utils import override_settings

from api.v1.v1_mobile.authentication import MobileAssignmentToken
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration, Entity, EntityData
from api.v1.v1_profile.serializers import AdministrationSerializer
from api.v1.v1_users.models import Organisation
from mis.settings import MASTER_DATA
from utils.custom_generator import generate_sqlite, sqlite_path
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False, TEST_ENV=True)
class SQLiteTenantIsolationTestCase(TenantIsolationTestCase):
    """Offline master data must never cross a tenant boundary.

    generate_sqlite used to dump model.objects.all() into one global file
    and download_sqlite_file served it to anyone, so a device held every
    tenant's administrative hierarchy offline.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        Organisation.objects.create(name=f"{sub}-org", tenant=tenant["tenant"])
        entity = Entity.objects.create(
            name=f"{sub}-entity", tenant=tenant["tenant"]
        )
        EntityData.objects.create(
            name=f"{sub}-school",
            entity=entity,
            administration=tenant["child"],
        )
        tenant["entity"] = entity
        assignment = MobileAssignment.objects.create_assignment(
            user=tenant["user"], name=f"{sub}-device"
        )
        assignment.administrations.add(tenant["child"])
        assignment.forms.add(tenant["form"])
        tenant["assignment"] = assignment
        return tenant

    def device_auth(self, tenant):
        token = MobileAssignmentToken.for_assignment(tenant["assignment"])
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def tearDown(self):
        for sub in ["acme", "beta"]:
            shutil.rmtree(f"{MASTER_DATA}/{sub}", ignore_errors=True)

    def read_names(self, file_name):
        conn = sqlite3.connect(file_name)
        try:
            return list(pd.read_sql_query("SELECT * FROM nodes", conn)["name"])
        finally:
            conn.close()

    def test_generate_writes_only_own_tenant_rows(self):
        file_name = generate_sqlite(
            Administration, tenant=self.a["tenant"]
        )
        names = self.read_names(file_name)
        self.assertIn("acme", names)
        self.assertNotIn("beta", names)
        self.assertNotIn("beta-d", names)

    def test_generate_writes_into_per_tenant_directory(self):
        file_name = generate_sqlite(Administration, tenant=self.a["tenant"])
        self.assertTrue(file_name.startswith(f"{MASTER_DATA}/acme/"))
        self.assertTrue(os.path.exists(file_name))

    def test_generate_without_tenant_keeps_root_location(self):
        file_name = generate_sqlite(Administration)
        self.addCleanup(os.remove, file_name)
        self.assertEqual(
            file_name, f"{MASTER_DATA}/test_administrator.sqlite"
        )

    def test_generate_scopes_organisation_by_tenant(self):
        file_name = generate_sqlite(Organisation, tenant=self.a["tenant"])
        names = self.read_names(file_name)
        self.assertIn("acme-org", names)
        self.assertNotIn("beta-org", names)

    def test_command_generates_a_file_per_tenant(self):
        call_command("generate_sqlite", "--test", True)
        for sub in ["acme", "beta"]:
            path = f"{MASTER_DATA}/{sub}/test_administrator.sqlite"
            self.assertTrue(os.path.exists(path), f"missing {path}")
        names = self.read_names(
            f"{MASTER_DATA}/acme/test_administrator.sqlite"
        )
        self.assertIn("acme", names)
        self.assertNotIn("beta", names)

    def test_command_still_writes_the_tenantless_artifacts(self):
        call_command("generate_sqlite", "--test", True)
        root = f"{MASTER_DATA}/test_administrator.sqlite"
        self.addCleanup(os.remove, root)
        self.assertTrue(os.path.exists(root))

    def test_administration_serializer_writes_into_its_tenants_file(self):
        # The serializer is where a single new row reaches sqlite; if it
        # keeps writing to the root file, per-tenant generation silently
        # drifts out of date the moment anyone adds an administration.
        generate_sqlite(Administration, tenant=self.a["tenant"])
        serializer = AdministrationSerializer(
            data={
                "name": "acme-village",
                "parent": self.a["root"].id,
                "code": "acme-village",
            },
            context={"user": self.a["user"]},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        names = self.read_names(
            sqlite_path(Administration, tenant=self.a["tenant"], test=True)
        )
        self.assertIn("acme-village", names)

    def test_generate_scopes_entity_by_tenant(self):
        file_name = generate_sqlite(Entity, tenant=self.a["tenant"])
        names = self.read_names(file_name)
        self.assertIn("acme-entity", names)
        self.assertNotIn("beta-entity", names)

    def test_generate_scopes_entity_data_through_its_entity(self):
        # EntityData reaches its tenant by join (entity__tenant) rather than
        # a local column, so it is the scoping most likely to silently
        # return everything.
        file_name = generate_sqlite(EntityData, tenant=self.a["tenant"])
        names = self.read_names(file_name)
        self.assertIn("acme-school", names)
        self.assertNotIn("beta-school", names)

    def test_download_serves_the_callers_tenant_file(self):
        generate_sqlite(Administration, tenant=self.a["tenant"])
        generate_sqlite(Administration, tenant=self.b["tenant"])
        res = self.client.get(
            "/api/v1/device/sqlite/administrator.sqlite",
            **self.device_auth(self.a),
        )
        self.assertEqual(res.status_code, 200)
        served = f"{MASTER_DATA}/served.sqlite"
        self.addCleanup(os.remove, served)
        with open(served, "wb") as f:
            f.write(res.content)
        names = self.read_names(served)
        self.assertIn("acme", names)
        self.assertNotIn("beta", names)

    def test_download_generates_the_file_when_absent(self):
        path = sqlite_path(Administration, tenant=self.a["tenant"], test=True)
        self.assertFalse(os.path.exists(path))
        res = self.client.get(
            "/api/v1/device/sqlite/administrator.sqlite",
            **self.device_auth(self.a),
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(os.path.exists(path))

    def test_download_serves_a_valid_file_when_the_tenant_has_no_rows(self):
        # A tenant with no entities still has a cascade question pointing at
        # entity_data.sqlite; serving nothing would break the form rather
        # than render an empty dropdown.
        EntityData.objects.filter(entity__tenant=self.a["tenant"]).delete()
        res = self.client.get(
            "/api/v1/device/sqlite/entity_data.sqlite",
            **self.device_auth(self.a),
        )
        self.assertEqual(res.status_code, 200)
        served = f"{MASTER_DATA}/served_empty.sqlite"
        self.addCleanup(os.remove, served)
        with open(served, "wb") as f:
            f.write(res.content)
        self.assertEqual(self.read_names(served), [])

    def test_download_requires_a_mobile_token(self):
        generate_sqlite(Administration, tenant=self.a["tenant"])
        res = self.client.get("/api/v1/device/sqlite/administrator.sqlite")
        self.assertEqual(res.status_code, 401)

    def test_download_rejects_a_web_token(self):
        generate_sqlite(Administration, tenant=self.a["tenant"])
        res = self.client.get(
            "/api/v1/device/sqlite/administrator.sqlite",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 403)

    def test_download_rejects_an_unknown_file_name(self):
        res = self.client.get(
            "/api/v1/device/sqlite/system_user.sqlite",
            **self.device_auth(self.a),
        )
        self.assertEqual(res.status_code, 404)

    def test_download_rejects_a_traversing_file_name(self):
        res = self.client.get(
            "/api/v1/device/sqlite/../../mis/settings.py",
            **self.device_auth(self.a),
        )
        self.assertIn(res.status_code, [400, 404])
