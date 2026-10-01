from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser

ADMIN_HOST = "admin.app.com"
SUMMARY = "/api/v1/admin/tenants/summary"


@override_settings(BASE_DOMAIN="app.com")
class AdminSummaryTestCase(TestCase, TenantTestHelperMixin):
    """Counts only. No workspace content crosses this boundary."""

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country", "D"], "Kenya")
        self.beta = self.create_tenant("beta", ["Country", "D"], "Uganda")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.auth = self.bearer(self.operator)
        self.seed(self.acme, forms=2, datapoints=3)
        self.seed(self.beta, forms=1, datapoints=1)

    def seed(self, fixture, forms, datapoints):
        child = Administration.objects.create(
            parent=fixture.root, level=fixture.levels[1],
            name=f"{fixture.tenant.subdomain}-d", tenant=fixture.tenant,
        )
        made = [
            Forms.objects.create(
                name=f"{fixture.tenant.subdomain}-{index}",
                tenant=fixture.tenant, status=FormStatus.published,
            )
            for index in range(forms)
        ]
        for index in range(datapoints):
            FormData.objects.create(
                name=f"dp-{index}", form=made[0], administration=child,
                created_by=fixture.admin,
            )
        MobileAssignment.objects.create_assignment(
            user=fixture.admin, name="device-1"
        )

    def rows(self):
        response = self.client.get(
            SUMMARY, HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 200)
        return {row["subdomain"]: row for row in response.json()}

    def test_counts_are_per_workspace(self):
        rows = self.rows()
        self.assertEqual(rows["acme"]["forms"], 2)
        self.assertEqual(rows["acme"]["datapoints"], 3)
        self.assertEqual(rows["beta"]["forms"], 1)
        self.assertEqual(rows["beta"]["datapoints"], 1)

    def test_counts_users_and_devices(self):
        rows = self.rows()
        self.assertEqual(rows["acme"]["users"], 1)
        self.assertEqual(rows["acme"]["devices"], 1)

    def test_soft_deleted_rows_are_excluded(self):
        FormData.objects.filter(
            form__tenant=self.acme.tenant
        ).first().delete()
        self.assertEqual(self.rows()["acme"]["datapoints"], 2)

    def query_count(self):
        with CaptureQueriesContext(connection) as captured:
            self.client.get(SUMMARY, HTTP_HOST=ADMIN_HOST, **self.auth)
        return len(captured)

    def test_the_cost_does_not_grow_with_the_number_of_workspaces(self):
        # The invariant worth pinning, rather than an absolute count.
        # A request to this endpoint pays for host resolution, JWT
        # authentication and the last_login stamp before the view is
        # even entered, so the absolute number says more about the
        # middleware stack than about this query -- while "adding a
        # workspace costs nothing" is exactly the property that a later
        # "just one more count" would break.
        before = self.query_count()
        self.create_tenant("gamma", ["Country", "D"], "Tanzania")
        self.assertEqual(self.query_count(), before)

    def counted(self, response):
        """The five numbers the console's stat tiles are made of."""
        body = response.json()
        self.assertEqual(response.status_code, 200)
        return {key: body.get(key) for key in (
            "users", "forms", "dashboards", "datapoints", "devices",
        )}

    def test_every_mutation_answers_with_the_counts_intact(self):
        # The console assigns each of these responses straight over the
        # workspace it is displaying, so a body without the counts does
        # not merely omit them -- it blanks five stat tiles that were on
        # screen a moment ago, next to a Delete button. One endpoint
        # carrying them is not enough; every path that returns a
        # workspace has to.
        tenant_id = self.acme.tenant.id
        base = f"/api/v1/admin/tenants/{tenant_id}"
        # The GET is the baseline and is itself the assertion that the
        # detail endpoint carries the counts at all: served from the
        # plain list serializer it renders every tile as zero, and no
        # frontend test catches that, because the frontend mocks the
        # shape it expects rather than the shape the endpoint sends.
        expected = self.counted(
            self.client.get(base, HTTP_HOST=ADMIN_HOST, **self.auth)
        )
        self.assertEqual(
            expected,
            {"users": 1, "forms": 2, "dashboards": 0,
             "datapoints": 3, "devices": 1},
        )

        mutations = [
            ("put", f"{base}/features", {"embedded_dashboard": True}),
            ("post", f"{base}/deactivate", None),
            ("post", f"{base}/activate", None),
            ("post", f"{base}/rename", {"subdomain": "acme-renamed"}),
        ]
        for method, url, payload in mutations:
            with self.subTest(url=url):
                call = getattr(self.client, method)
                response = (
                    call(url, payload, content_type="application/json",
                         HTTP_HOST=ADMIN_HOST, **self.auth)
                    if payload is not None
                    else call(url, HTTP_HOST=ADMIN_HOST, **self.auth)
                )
                self.assertEqual(self.counted(response), expected)
