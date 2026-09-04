"""The embed document and the origin it is served from (VIZ-019 D-4a).

The snippet runs on EMBED_HOST rather than in this application's origin,
because it can run in neither our origin (cross-site scripting, with a
JavaScript-readable AUTH_TOKEN cookie to steal) nor an opaque one
(measured: Tableau's CORS refuses `Origin: null`, and Power BI cannot
reach its storage through an inherited sandbox).
"""

import json

from django.core import signing
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
)
from api.v1.v1_visualization.embed_views import SALT
from api.v1.v1_visualization.models import Dashboard
from rest_framework_simplejwt.tokens import RefreshToken

EMBED_ORIGIN = "http://embed.example.com"
EMBED_HOSTNAME = "embed.example.com"
PUBLISHED = "<iframe src='https://app.powerbi.com/view?r=published'></iframe>"
EDITED = "<iframe src='https://app.powerbi.com/view?r=edited'></iframe>"


@override_settings(USE_TZ=False, EMBED_HOST=EMBED_ORIGIN)
class EmbedDocumentTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_embed_doc@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.user.tenant = Tenant.objects.get()
        self.user.save()
        self.dashboard = Dashboard.objects.create(
            name="Sales",
            slug="sales",
            kind=DashboardKind.embed,
            root_form=None,
            # Live row deliberately differs from the snapshot.
            embed_snippet=EDITED,
            tenant=self.user.tenant,
            created_by=self.user,
            status=DashboardStatus.published,
            is_public=True,
            published_config={"embed_snippet": PUBLISHED},
        )

    def url(self, dashboard=None):
        res = self.client.get(
            "/api/v1/dashboards/{0}".format(
                (dashboard or self.dashboard).slug
            )
        )
        return res.json()["embed_url"]

    def fetch(self, url, host=EMBED_HOSTNAME):
        return self.client.get(
            url.replace(EMBED_ORIGIN, ""), HTTP_HOST=host
        )

    # ── what it serves ──

    def test_serves_the_snapshot_markup_not_the_live_row(self):
        res = self.fetch(self.url())
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn(PUBLISHED, body)
        self.assertNotIn(EDITED, body)

    def test_the_document_centres_the_content_safely(self):
        # Layout inside a cross-origin frame is unreachable from the
        # framing page, so this document is the only place that can
        # centre a vendor's fixed-width report.
        #
        # `safe` is the load-bearing half. Plain centring overflows a
        # too-narrow frame on both sides and the left half cannot be
        # scrolled to, which is how a wide report loses its left edge.
        body = self.fetch(self.url()).content.decode()
        self.assertIn("justify-content:safe center", body)
        self.assertNotIn("justify-content:center", body)

    def test_it_may_be_framed(self):
        # XFrameOptionsMiddleware would otherwise send SAMEORIGIN and the
        # browser would refuse to frame the one document that exists to
        # be framed.
        res = self.fetch(self.url())
        self.assertIsNone(res.headers.get("X-Frame-Options"))

    def test_it_is_not_stored_by_shared_caches(self):
        res = self.fetch(self.url())
        self.assertEqual(res.headers.get("Cache-Control"), "no-store")

    # ── the origin check ──

    def test_the_application_host_will_not_serve_it(self):
        # The load-bearing check: on this application's own host the same
        # URL must refuse, or the snippet would run exactly where the
        # separate origin exists to stop it running.
        res = self.fetch(self.url(), host="testserver")
        self.assertEqual(res.status_code, 404)

    @override_settings(EMBED_HOST="")
    def test_unconfigured_serves_nothing_anywhere(self):
        token = signing.dumps({"d": self.dashboard.id}, salt=SALT)
        res = self.client.get(
            "/api/v1/embed/{0}".format(token), HTTP_HOST=EMBED_HOSTNAME
        )
        self.assertEqual(res.status_code, 404)

    @override_settings(BASE_DOMAIN="example.com")
    def test_the_tenant_middleware_does_not_refuse_the_embed_host(self):
        # embed.example.com names no workspace, so without the EXEMPT_PATHS
        # entry the middleware's "Workspace not found" would 404 every
        # embed before its view ran.
        #
        # The token is minted directly rather than through the read API:
        # with BASE_DOMAIN set, that API call would itself have to arrive
        # on a workspace host, which is a different thing than the one
        # this test is about.
        token = signing.dumps({"d": self.dashboard.id}, salt=SALT)
        res = self.client.get(
            "/api/v1/embed/{0}".format(token), HTTP_HOST=EMBED_HOSTNAME
        )
        self.assertEqual(res.status_code, 200)

    # ── tokens ──

    def test_a_forged_token_is_refused(self):
        res = self.fetch("{0}/api/v1/embed/not-a-token".format(EMBED_ORIGIN))
        self.assertEqual(res.status_code, 404)

    def test_a_token_signed_with_another_salt_is_refused(self):
        token = signing.dumps({"d": self.dashboard.id}, salt="wrong")
        res = self.client.get(
            "/api/v1/embed/{0}".format(token), HTTP_HOST=EMBED_HOSTNAME
        )
        self.assertEqual(res.status_code, 404)

    def test_an_unpublished_dashboard_stops_serving(self):
        # Re-checked at serve time, so unpublishing takes effect at once
        # rather than waiting out the token's lifetime.
        url = self.url()
        self.dashboard.status = DashboardStatus.draft
        self.dashboard.save()
        self.assertEqual(self.fetch(url).status_code, 404)

    def test_a_widgets_dashboard_has_no_embed_url(self):
        widgets = Dashboard.objects.create(
            name="Coverage", slug="coverage",
            kind=DashboardKind.widgets,
            root_form=Forms.objects.get(pk=6001),
            tenant=self.user.tenant, created_by=self.user,
            status=DashboardStatus.published, is_public=True,
            published_config={"default_filters": {}, "widgets": []},
        )
        self.assertIsNone(self.url(widgets))


@override_settings(USE_TZ=False, EMBED_HOST=EMBED_ORIGIN)
class EmbedPreviewTestCase(TestCase, ProfileTestHelperMixin):
    """Preview must show what a viewer sees, including unsaved markup."""

    def setUp(self):
        cache.clear()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_embed_preview@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        token = RefreshToken.for_user(self.user).access_token
        self.header = {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}
        self.embed = Dashboard.objects.create(
            name="Draft", slug="draft", kind=DashboardKind.embed,
            root_form=None, embed_snippet="<iframe src='https://x/'></iframe>",
            tenant=getattr(self.user, "tenant", None), created_by=self.user,
        )

    def preview(self, dashboard, snippet):
        return self.client.post(
            "/api/v1/manage/dashboards/{0}/embed-preview".format(
                dashboard.id
            ),
            json.dumps({"embed_snippet": snippet}),
            content_type="application/json",
            **self.header
        )

    def test_it_serves_the_unsaved_markup(self):
        draft = "<iframe src='https://public.tableau.com/unsaved'></iframe>"
        res = self.preview(self.embed, draft)
        self.assertEqual(res.status_code, 200, res.content)
        url = res.json()["embed_url"]
        doc = self.client.get(
            url.replace(EMBED_ORIGIN, ""), HTTP_HOST=EMBED_HOSTNAME
        )
        self.assertEqual(doc.status_code, 200)
        self.assertIn(draft, doc.content.decode())

    def test_an_empty_snippet_is_refused(self):
        res = self.preview(self.embed, "   ")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "embed_snippet")

    def test_a_widgets_dashboard_is_refused(self):
        widgets = Dashboard.objects.create(
            name="Coverage", slug="coverage-2",
            kind=DashboardKind.widgets,
            root_form=Forms.objects.get(pk=6001),
            tenant=getattr(self.user, "tenant", None), created_by=self.user,
        )
        res = self.preview(widgets, "<iframe></iframe>")
        self.assertEqual(res.status_code, 400)

    @override_settings(EMBED_HOST="")
    def test_unconfigured_reports_service_unavailable(self):
        res = self.preview(self.embed, "<iframe src='https://x/'></iframe>")
        self.assertEqual(res.status_code, 503)

    def test_an_account_without_dashboard_edit_is_refused(self):
        # Minting a preview URL is an edit-level action: it puts arbitrary
        # markup on the embed origin, briefly, under this deployment's
        # name.
        consumer = self.create_user(
            email="viz_embed_consumer@akvo.org", role_level=self.IS_ADMIN
        )
        token = RefreshToken.for_user(consumer).access_token
        res = self.client.post(
            "/api/v1/manage/dashboards/{0}/embed-preview".format(
                self.embed.id
            ),
            json.dumps(
                {"embed_snippet": "<iframe src='https://x/'></iframe>"}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer {0}".format(token),
        )
        self.assertEqual(res.status_code, 403)


@override_settings(
    USE_TZ=False,
    EMBED_HOST="http://embed-proxy.mis.example.org",
    BASE_DOMAIN="mis.example.org",
)
class EmbedSubdomainReservationTestCase(TestCase):
    """A workspace must not be registrable at the embed host.

    The only thing keeping author-pasted markup away from this
    application is that the two sit on different origins. A workspace at
    the embed host would put them back on the same one, where a snippet
    could read the `AUTH_TOKEN` cookie of anyone signed in there.
    """

    def register(self, subdomain):
        return self.client.post(
            "/api/v1/register",
            json.dumps({
                "email": "someone@example.org",
                "password": "Secret#Pass123",
                "subdomain": subdomain,
            }),
            content_type="application/json",
            HTTP_HOST="mis.example.org",
        )

    def test_the_embed_subdomain_is_refused(self):
        res = self.register("embed-proxy")
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn("subdomain", res.json()["details"])

    def test_an_ordinary_subdomain_is_unaffected(self):
        # Only the exact collision is refused; nothing else changes.
        # Asserted as a success rather than "not 400", which would also
        # pass on a 404 and prove nothing.
        res = self.register("acme")
        self.assertLess(res.status_code, 300, res.content)

    @override_settings(EMBED_HOST="")
    def test_the_rule_is_inert_when_embedding_is_unconfigured(self):
        res = self.register("embed-proxy")
        self.assertLess(res.status_code, 300, res.content)
