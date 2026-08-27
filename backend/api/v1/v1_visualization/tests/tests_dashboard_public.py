from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import (
    DashboardStatus,
    DashboardVisibility,
)
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)

PUBLIC = "/api/v1/public/dashboards"

# BASE_DOMAIN is forced empty under `manage.py test`, so host routing is
# inert unless a test opts in. Everything here depends on it.
HOST_SETTINGS = dict(USE_TZ=False, TEST_ENV=True, BASE_DOMAIN="app.com")


@override_settings(**HOST_SETTINGS)
class PublicDashboardTestCase(
    VisualizationValuesTestMixin, APITestCase
):
    """The only anonymous surface in the app, and why it is safe.

    VIZ-010 D-2: the tenant comes from the host, so a public dashboard is
    reachable on its workspace's subdomain and nowhere else.
    """

    ACME = "acme.app.com"
    OTHER = "other.app.com"
    BASE = "app.com"

    def setUp(self):
        super().setUp()
        self.acme = Tenant.objects.create(subdomain="acme")
        self.other = Tenant.objects.create(subdomain="other")
        self.registration.tenant = self.acme
        self.registration.save()
        self.monitoring.tenant = self.acme
        self.monitoring.save()

        self.dashboard = self.publish(
            slug="water-points", visibility=DashboardVisibility.public
        )

    def publish(
        self,
        slug,
        visibility=DashboardVisibility.public,
        status=DashboardStatus.published,
        tenant=None,
    ):
        dashboard = Dashboard.objects.create(
            name=slug.replace("-", " ").title(),
            slug=slug,
            root_form=self.registration,
            tenant=tenant or self.acme,
            status=status,
            visibility=visibility,
        )
        dashboard.published_config = {
            "default_filters": {},
            "widgets": [
                {
                    "id": 1,
                    "type": "kpi",
                    "col_span": 6,
                    "title": "Sites",
                    "form": self.MONITORING_FORM_ID,
                    "question": None,
                    "config": {"measure": "current_state"},
                }
            ],
        }
        dashboard.save()
        return dashboard

    def get(self, url, host=None, **params):
        return self.client.get(
            url, params, HTTP_HOST=host or self.ACME
        )

    # ── the matrix ───────────────────────────────────────────────────

    def test_public_and_published_on_its_own_host_is_served(self):
        response = self.get(PUBLIC)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [d["slug"] for d in response.json()], ["water-points"]
        )

    def test_internal_is_not_listed_or_fetchable(self):
        self.publish(
            slug="internal-only",
            visibility=DashboardVisibility.internal,
        )
        listing = self.get(PUBLIC).json()
        self.assertNotIn("internal-only", [d["slug"] for d in listing])
        # 404, never 403 — a 403 confirms the slug exists.
        self.assertEqual(
            self.get(f"{PUBLIC}/internal-only").status_code, 404
        )

    def test_a_public_draft_is_visible_to_nobody(self):
        """Visibility and publication are independent (D-5)."""
        self.publish(
            slug="not-yet",
            visibility=DashboardVisibility.public,
            status=DashboardStatus.draft,
        )
        self.assertEqual(self.get(f"{PUBLIC}/not-yet").status_code, 404)

    def test_another_workspaces_host_cannot_see_it(self):
        self.assertEqual(
            self.get(PUBLIC, host=self.OTHER).json(), []
        )
        self.assertEqual(
            self.get(
                f"{PUBLIC}/water-points", host=self.OTHER
            ).status_code,
            404,
        )

    def test_the_base_domain_serves_nothing(self):
        """A workspace's dashboards are not the signup page's to serve."""
        self.assertEqual(self.get(PUBLIC, host=self.BASE).json(), [])
        self.assertEqual(
            self.get(
                f"{PUBLIC}/water-points", host=self.BASE
            ).status_code,
            404,
        )

    def test_an_unknown_host_is_refused_before_the_view(self):
        # TenantMiddleware answers this one; asserted here because the
        # public namespace depends on it having done so.
        self.assertEqual(
            self.get(PUBLIC, host="nope.app.com").status_code, 404
        )

    # ── no login required, and none accepted as a substitute ─────────

    def test_it_needs_no_authentication(self):
        response = self.get(f"{PUBLIC}/water-points")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "water-points")
        self.assertEqual(len(response.json()["widgets"]), 1)

    # ── widget data ──────────────────────────────────────────────────

    def test_widget_data_is_served_by_id(self):
        response = self.get(f"{PUBLIC}/water-points/widgets/1/data")
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

    def test_a_widget_from_another_dashboard_is_not_found(self):
        other = self.publish(slug="elsewhere")
        other.published_config["widgets"][0]["id"] = 99
        other.save()
        self.assertEqual(
            self.get(
                f"{PUBLIC}/water-points/widgets/99/data"
            ).status_code,
            404,
        )

    def test_a_nonexistent_widget_answers_identically(self):
        """Indistinguishable from one that belongs to someone else."""
        missing = self.get(f"{PUBLIC}/water-points/widgets/12345/data")
        self.assertEqual(missing.status_code, 404)

    def test_the_wire_carries_no_query_grammar(self):
        """D-3, the decision the whole surface rests on.

        Smuggling the parameters /visualization/values would accept must
        change nothing, because none of them are read.
        """
        clean = self.get(f"{PUBLIC}/water-points/widgets/1/data").json()
        smuggled = self.get(
            f"{PUBLIC}/water-points/widgets/1/data",
            form_id=self.REGISTRATION_FORM_ID,
            question_id=self.Q_OPTION_ID,
            monitoring="all",
            group_by="option",
        ).json()
        self.assertEqual(clean, smuggled)

    # ── the authenticated twin agrees ────────────────────────────────

    def test_both_paths_answer_the_same_widget_identically(self):
        """One resolver, two doors (D-4).

        If these diverged, a dashboard would show one number to a
        colleague and another to the public, and neither would look
        wrong.
        """
        anonymous = self.get(
            f"{PUBLIC}/water-points/widgets/1/data"
        ).json()

        self.user.tenant = self.acme
        self.user.save()
        self.client.force_authenticate(user=self.user)
        authenticated = self.client.get(
            "/api/v1/dashboards/water-points/widgets/1/data",
            HTTP_HOST=self.ACME,
        )
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(authenticated.json(), anonymous)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PublicDashboardWithoutBaseDomainTestCase(
    VisualizationValuesTestMixin, APITestCase
):
    """BASE_DOMAIN unset: a single-host deployment is unaffected."""

    def test_the_namespace_serves_nothing(self):
        dashboard = Dashboard.objects.create(
            name="Water points",
            slug="water-points",
            root_form=self.registration,
            status=DashboardStatus.published,
            visibility=DashboardVisibility.public,
        )
        dashboard.published_config = {
            "default_filters": {},
            "widgets": [],
        }
        dashboard.save()

        # Every host is the base domain, so nothing resolves to a tenant
        # and the public surface is inert rather than open.
        self.assertEqual(self.client.get(PUBLIC).json(), [])
        self.assertEqual(
            self.client.get(f"{PUBLIC}/water-points").status_code, 404
        )
