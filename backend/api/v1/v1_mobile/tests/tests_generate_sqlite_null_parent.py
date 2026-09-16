"""A workspace whose only Administration is its root.

`generate_sqlite` guarded its parent column with `int(x) if x == x else 0`
-- a NaN check. pandas types a column of [None, 1] as float64/NaN, which
that idiom handles, but a column of [None] alone stays `object` and keeps
the real None: `None == None` is True, so int(None) raises. The command
iterates Tenant.objects.all(), so one root-only workspace aborted the step
for every workspace after it -- and it is seeder.sh's penultimate line.

A workspace registered through the free-tier flow and never given a
hierarchy is exactly that shape, which is why this needed a
multi-workspace database to surface.
"""
import os
import sqlite3
import tempfile
from contextlib import redirect_stdout
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import Tenant
from utils.custom_generator import generate_sqlite


@override_settings(USE_TZ=False, TEST_ENV=True)
class GenerateSqliteNullParentTest(TestCase):
    def setUp(self):
        self.storage = tempfile.mkdtemp()

    def read_nodes(self, path):
        conn = sqlite3.connect(path)
        try:
            return conn.execute("SELECT id, parent FROM nodes").fetchall()
        finally:
            conn.close()

    def make_workspace(self, subdomain, with_child=False):
        tenant = Tenant.objects.create(subdomain=subdomain)
        level = Levels.objects.create(name="National", level=0, tenant=tenant)
        root = Administration.objects.create(
            parent=None, level=level, name=subdomain.title(), tenant=tenant
        )
        if with_child:
            child_level = Levels.objects.create(
                name="Province", level=1, tenant=tenant
            )
            Administration.objects.create(
                parent=root, level=child_level, name="Province 1",
                tenant=tenant,
            )
        return tenant

    def test_root_only_workspace_writes_parent_zero(self):
        """The regression. A single all-None column, not a mixed one.

        A second row with a real parent makes pandas produce float64/NaN,
        which the old guard handled -- so a two-row fixture passes against
        the bug and proves nothing.
        """
        tenant = self.make_workspace("rootonly")

        path = generate_sqlite(Administration, tenant=tenant, test=True)

        rows = self.read_nodes(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], 0)

    def test_mixed_parent_column_still_works(self):
        tenant = self.make_workspace("mixed", with_child=True)

        path = generate_sqlite(Administration, tenant=tenant, test=True)

        rows = dict(self.read_nodes(path))
        roots = [pk for pk, parent in rows.items() if parent == 0]
        self.assertEqual(len(roots), 1)
        self.assertEqual(sorted(rows.values()), [0, roots[0]])

    def test_every_workspace_gets_a_file_despite_a_root_only_one(self):
        """One bad workspace used to abort the loop for all the others."""
        first = self.make_workspace("aaa")
        second = self.make_workspace("bbb", with_child=True)

        paths = [
            generate_sqlite(Administration, tenant=t, test=True)
            for t in (first, second)
        ]

        for path in paths:
            self.assertTrue(os.path.exists(path))


@override_settings(USE_TZ=False, TEST_ENV=True)
class GenerateSqliteCommandTenantTest(TestCase):
    """`generate_sqlite` the command, not the helper.

    It walked Tenant.objects.all() unconditionally, so
    `./seeder.sh --tenant=acme` rebuilt every workspace on the database --
    eight directories of byte-identical output, with the one directory
    that actually changed buried in the middle of it.
    """

    def make_workspace(self, subdomain):
        tenant = Tenant.objects.create(subdomain=subdomain)
        level = Levels.objects.create(name="National", level=0, tenant=tenant)
        Administration.objects.create(
            parent=None, level=level, name=subdomain.title(), tenant=tenant
        )
        return tenant

    def run_command(self, *args, **kwargs):
        buffer = StringIO()
        with redirect_stdout(buffer):
            call_command("generate_sqlite", *args, **kwargs)
        return buffer.getvalue()

    def test_named_workspace_is_the_only_one_rebuilt(self):
        self.make_workspace("acme")
        self.make_workspace("other")

        output = self.run_command(tenant="acme")

        self.assertIn("/acme/", output)
        self.assertNotIn("/other/", output)

    def test_named_workspace_skips_the_tenant_less_files(self):
        """The root files belong to the tenant-less space, which a
        --tenant run did not touch and must not rewrite."""
        self.make_workspace("acme")

        output = self.run_command(tenant="acme")

        for line in output.splitlines():
            if "Generated Successfully" in line:
                self.assertIn("/acme/", line)

    def test_without_tenant_rebuilds_everything(self):
        """run-prod.sh calls it bare at boot and wants every workspace."""
        self.make_workspace("acme")
        self.make_workspace("other")

        output = self.run_command()

        self.assertIn("/acme/", output)
        self.assertIn("/other/", output)
        # The tenant-less pass writes into MASTER_DATA itself, so its
        # lines carry the model name with no subdomain directory.
        root_lines = [
            line
            for line in output.splitlines()
            if "Generated Successfully" in line
            and "/acme/" not in line
            and "/other/" not in line
        ]
        self.assertTrue(root_lines)

    def test_unknown_subdomain_is_rejected(self):
        self.make_workspace("acme")

        with self.assertRaises(CommandError) as ctx:
            self.run_command(tenant="acmee")

        message = str(ctx.exception)
        self.assertIn("No workspace with subdomain 'acmee'", message)
