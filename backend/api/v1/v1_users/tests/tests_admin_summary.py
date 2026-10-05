from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser, Tenant

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

    def rows(self, query=""):
        response = self.client.get(
            SUMMARY + query, HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 200)
        return {row["subdomain"]: row for row in response.json()["data"]}

    def test_the_response_is_the_house_envelope(self):
        # The same four keys every other paginated table in the
        # application reads. A console with a shape of its own would be
        # a second thing to learn for no gain.
        #
        # Counted from the table rather than written as a literal.
        # 0004_backfill_default_tenant puts a `default` workspace in
        # every database, the test one included, so setUp's two are
        # never the whole of it -- and an assertion against the table is
        # the stronger one anyway: it fails if the endpoint drops a row
        # as well as if it invents one.
        expected = Tenant.objects.count()
        body = self.client.get(
            SUMMARY, HTTP_HOST=ADMIN_HOST, **self.auth
        ).json()
        self.assertEqual(body["current"], 1)
        self.assertEqual(body["total"], expected)
        self.assertEqual(body["total_page"], 1)
        self.assertEqual(len(body["data"]), expected)

    def test_a_second_page_holds_the_workspaces_the_first_did_not(self):
        # Enough workspaces for one full page and a short one. The
        # assertion that matters is not "there are two pages" but "the
        # two pages partition the set" -- a paginator that silently
        # repeats rows still reports two pages.
        for index in range(26):
            self.create_tenant(
                "w{0:02d}".format(index), ["Country", "D"],
                "Root {0}".format(index),
            )
        expected = Tenant.objects.count()
        self.assertGreater(expected, 25)
        first = self.client.get(
            SUMMARY, HTTP_HOST=ADMIN_HOST, **self.auth
        ).json()
        second = self.client.get(
            SUMMARY + "?page=2", HTTP_HOST=ADMIN_HOST, **self.auth
        ).json()
        self.assertEqual(first["total"], expected)
        self.assertEqual(first["total_page"], 2)
        self.assertEqual(len(first["data"]), 25)
        self.assertEqual(len(second["data"]), expected - 25)
        on_first = set(row["subdomain"] for row in first["data"])
        on_second = set(row["subdomain"] for row in second["data"])
        self.assertEqual(on_first & on_second, set())
        self.assertEqual(len(on_first | on_second), expected)

    def test_a_page_past_the_end_is_refused(self):
        # DRF's own behaviour, pinned because the console has to cope
        # with it: a workspace deleted between two requests can shrink
        # the result out from under the page an operator is standing on.
        response = self.client.get(
            SUMMARY + "?page=99", HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 404)

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

    def test_search_matches_the_subdomain(self):
        self.assertEqual(list(self.rows("?search=acm")), ["acme"])

    def test_search_matches_the_workspace_name(self):
        # The name is the root administration unit's, not a column on
        # Tenant -- see TenantListSerializer.get_name. An operator
        # looking for a workspace knows the organisation, not the
        # address, and the console has always searched both. Moving the
        # filter to the server must not quietly narrow it to subdomains.
        self.assertEqual(list(self.rows("?search=keny")), ["acme"])

    def test_a_whitespace_only_search_is_no_search(self):
        # What a cleared search box can send. Treated as a filter it
        # matches nothing, and the console tells an operator who just
        # cleared a box that the deployment is empty.
        self.assertEqual(
            len(self.rows("?search=%20%20")), Tenant.objects.count()
        )

    def test_an_unconfigured_workspace_lists_and_is_still_searchable(self):
        # A subdomain claimed by /register phase 1 and never configured
        # owns no Administration at all, so its name is "" and the name
        # half of the search can never match it. It must still appear --
        # the console is the only place its state can be explained --
        # and its address must still find it.
        Tenant.objects.create(subdomain="claimed")
        self.assertIn("claimed", self.rows())
        found = self.rows("?search=claim")
        self.assertEqual(list(found), ["claimed"])
        self.assertEqual(found["claimed"]["name"], "")

    def test_state_narrows_the_page_and_the_total(self):
        self.beta.tenant.is_active = False
        self.beta.tenant.save(update_fields=["is_active"])
        body = self.client.get(
            SUMMARY + "?state=suspended", HTTP_HOST=ADMIN_HOST, **self.auth
        ).json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(
            [row["subdomain"] for row in body["data"]], ["beta"]
        )

    def test_an_unknown_state_is_refused_rather_than_ignored(self):
        # Returning everything for a typo would read to an operator as
        # "this deployment has no suspended workspaces", which is a lie
        # that looks like an answer.
        response = self.client.get(
            SUMMARY + "?state=suspdended", HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown state", response.json()["message"])

    def test_the_default_order_is_by_subdomain(self):
        # Asserted against the table rather than a fixed list, per the
        # same reasoning as the envelope test: the migration's `default`
        # workspace is in every database and is not this test's subject.
        self.assertEqual(
            list(self.rows()),
            sorted(Tenant.objects.values_list("subdomain", flat=True)),
        )

    def test_ordering_by_a_count_descends(self):
        # acme holds 3 datapoints, beta 1, and `default` none. Asserted
        # as a monotonic sequence rather than a fixed list of
        # subdomains, so the test says what it means -- the server
        # ordered by the column it was asked for -- and does not have to
        # be rewritten every time a fixture gains a workspace.
        descending = self.rows("?ordering=-datapoints")
        self.assertEqual(list(descending)[0], "acme")
        counts = [row["datapoints"] for row in descending.values()]
        self.assertEqual(counts, sorted(counts, reverse=True))

        ascending = self.rows("?ordering=datapoints")
        self.assertEqual(list(ascending)[-1], "acme")
        counts = [row["datapoints"] for row in ascending.values()]
        self.assertEqual(counts, sorted(counts))

    def test_an_unknown_ordering_is_refused(self):
        response = self.client.get(
            SUMMARY + "?ordering=datapoint", HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown ordering", response.json()["message"])

    def test_tied_counts_still_page_deterministically(self):
        # Every workspace here holds zero dashboards, so ordering by
        # that column is not a total order and PostgreSQL may return
        # tied rows in any order it likes -- differently for OFFSET 0
        # than for OFFSET 25. Without the pk tiebreaker the symptom is a
        # workspace appearing on both pages while another appears on
        # neither, intermittently, which is about as unpleasant a bug as
        # this feature can produce.
        for index in range(30):
            self.create_tenant(
                "w{0:02d}".format(index), ["Country", "D"],
                "Root {0}".format(index),
            )
        expected = Tenant.objects.count()
        self.assertGreater(expected, 25)
        seen = []
        for page in (1, 2):
            body = self.client.get(
                "{0}?ordering=dashboards&page={1}".format(SUMMARY, page),
                HTTP_HOST=ADMIN_HOST, **self.auth,
            ).json()
            seen.extend(row["subdomain"] for row in body["data"])
        self.assertEqual(len(seen), expected)
        self.assertEqual(len(set(seen)), expected)

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
