import json
import os
import tempfile
from unittest import mock

from django.test import TestCase, override_settings

from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import (
    TenantTestHelperMixin,
    set_embedding,
)
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
        # The master-data root is a real directory shared by every test
        # process and left behind between runs, so a rename test that
        # used it would depend on whether a previous run had already
        # created the destination -- and `_move_master_data` refuses to
        # clobber one that exists.
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        patch = mock.patch("utils.custom_generator.MASTER_DATA", root.name)
        patch.start()
        self.addCleanup(patch.stop)

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

    def test_no_mobile_device_warning(self):
        """Devices are not counted, because a rename does not reach them.

        The app is configured against the deployment's own address, not
        a workspace's: `MobileFormSerializer.get_url` hands back
        `/form/<id>` rather than an absolute host, nothing under
        `v1_mobile` builds a tenant URL, and the shipped build params
        document `serverURL` as `https://<your-domain>/api/v1/device`.
        `test_a_device_on_the_base_domain_survives_a_rename` is the
        proof; this only pins that no number is offered.
        """
        self.assertNotIn("mobile_devices", self.impact())

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
        old = sqlite_path(Administration, tenant=self.acme.tenant)
        os.makedirs(os.path.dirname(old), exist_ok=True)
        with mock.patch(
            "api.v1.v1_users.admin_views.os.rename",
            side_effect=OSError("nope"),
        ):
            self.assertEqual(self.rename("moh-hss").status_code, 200)
        self.acme.tenant.refresh_from_db()
        self.assertEqual(self.acme.tenant.subdomain, "moh-hss")

    def dashboard(self, name, kind, public=False, snippet=None):
        from api.v1.v1_forms.constants import FormStatus
        from api.v1.v1_forms.models import Forms
        from api.v1.v1_visualization.constants import (
            DashboardKind,
            DashboardStatus,
        )
        from api.v1.v1_visualization.models import Dashboard

        form = Forms.objects.create(
            name=f"{name}-form",
            tenant=self.acme.tenant,
            status=FormStatus.published,
        )
        return Dashboard.objects.create(
            tenant=self.acme.tenant,
            name=name,
            slug=name,
            kind=kind,
            root_form=form if kind == DashboardKind.widgets else None,
            embed_snippet=snippet,
            status=DashboardStatus.published,
            is_public=public,
            published_config={"embed_snippet": snippet} if snippet else {},
        )

    def impact(self):
        response = self.client.get(
            f"{self.base()}/rename-impact",
            HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_dashboard_counts_are_disjoint(self):
        # Every published dashboard used to be counted once as a link
        # and, if it carried a snippet, a second time as an embed -- so
        # an operator reading the dialog was told more would break than
        # exists. The two counts now partition the published set.
        from api.v1.v1_visualization.constants import DashboardKind

        set_embedding(self.acme.tenant)
        self.dashboard("internal-a", DashboardKind.widgets)
        self.dashboard("internal-b", DashboardKind.widgets)
        self.dashboard("shared", DashboardKind.widgets, public=True)
        self.dashboard(
            "report", DashboardKind.embed, snippet="<iframe src='x'>"
        )
        impact = self.impact()
        self.assertEqual(impact["published_dashboards"], 3)
        self.assertEqual(impact["public_dashboards"], 1)

    def test_embedded_dashboards_are_not_warned_about(self):
        # The spec asked for this to be confirmed rather than assumed,
        # and it survives: the embed document is served from EMBED_HOST
        # under a signed token carrying a dashboard id, so nothing in
        # its URL is the workspace's address. Warning about it told an
        # operator that a rename breaks something a rename does not
        # touch.
        from api.v1.v1_visualization.constants import DashboardKind
        from api.v1.v1_visualization.embed_views import embed_url_for, SALT
        from django.core import signing

        set_embedding(self.acme.tenant)
        board = self.dashboard(
            "report", DashboardKind.embed, snippet="<iframe src='x'>"
        )
        self.assertNotIn("embedded_dashboards", self.impact())
        with override_settings(EMBED_HOST="https://embed.example.com"):
            before = embed_url_for(board)
            self.assertEqual(self.rename("moh-hss").status_code, 200)
            board.refresh_from_db()
            after = embed_url_for(board)
            prefix = "https://embed.example.com/api/v1/embed/"
            self.assertTrue(after.startswith(prefix))
            before_token = before.rsplit("/", 1)[-1]
            after_token = after.rsplit("/", 1)[-1]
            self.assertEqual(
                signing.loads(after_token, salt=SALT),
                {"d": board.id},
            )
            self.assertEqual(
                signing.loads(after_token, salt=SALT),
                signing.loads(before_token, salt=SALT),
            )

    def test_a_device_on_the_base_domain_survives_a_rename(self):
        """The reason there is no device warning, asserted end to end.

        A device syncs against the base domain, where `request.tenant`
        is None and the middleware's host check is skipped, so what
        partitions the reply is the token's assignment -- and a rename
        does not touch that. The dialog used to say every enrolled
        device would stop syncing and need re-enrolling by hand, which
        described field work that does not exist.
        """
        from api.v1.v1_mobile.authentication import MobileAssignmentToken

        assignment = MobileAssignment.objects.filter(
            user=self.acme.admin
        ).first()
        auth = {
            "HTTP_AUTHORIZATION": "Bearer {0}".format(
                MobileAssignmentToken.for_assignment(assignment)
            )
        }
        url = "/api/v1/device/datapoint-list"
        self.assertEqual(
            self.client.get(url, HTTP_HOST="app.com", **auth).status_code,
            200,
        )
        self.assertEqual(self.rename("moh-hss").status_code, 200)
        self.assertEqual(
            self.client.get(url, HTTP_HOST="app.com", **auth).status_code,
            200,
        )

    def test_a_device_still_sees_only_its_own_workspace(self):
        """Dropping the warning must not quietly drop the partition."""
        from api.v1.v1_forms.constants import FormStatus
        from api.v1.v1_forms.models import Forms
        from api.v1.v1_mobile.authentication import MobileAssignmentToken

        other = self.create_tenant("beta", ["Country"], "Uganda")
        theirs = Forms.objects.create(
            name="theirs", tenant=other.tenant, status=FormStatus.published
        )
        mine = Forms.objects.create(
            name="mine",
            tenant=self.acme.tenant,
            status=FormStatus.published,
        )
        assignment = MobileAssignment.objects.filter(
            user=self.acme.admin
        ).first()
        assignment.forms.add(mine)
        auth = {
            "HTTP_AUTHORIZATION": "Bearer {0}".format(
                MobileAssignmentToken.for_assignment(assignment)
            )
        }
        for form, expected in ((mine, 200), (theirs, 404)):
            response = self.client.get(
                f"/api/v1/device/form/{form.id}",
                HTTP_HOST="app.com",
                **auth,
            )
            self.assertEqual(response.status_code, expected)
