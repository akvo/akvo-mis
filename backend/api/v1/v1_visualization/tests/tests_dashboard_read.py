import json
from datetime import datetime

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import SystemUser
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.models import Dashboard
from utils.tenant_test_case import TenantIsolationTestCase

MANAGE_URL = "/api/v1/manage/dashboards"
READ_URL = "/api/v1/dashboards"


def auth(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}


def snapshot(widgets, default_filters=None):
    """A published_config as publish would have written it."""
    return {
        "default_filters": default_filters or {},
        "widgets": widgets,
    }


def widget(**overrides):
    row = {
        "id": 1,
        "order": 1,
        "type": "kpi",
        "col_span": 6,
        "title": "Operational",
        "color": None,
        "form": 6001,
        "question": 600102,
        "config": {},
    }
    row.update(overrides)
    return row


@override_settings(USE_TZ=False)
class DashboardReadTestCase(TestCase, ProfileTestHelperMixin):
    """What a viewer can see, and what is invisible to them."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_read@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.header = auth(self.user)
        self.root = Forms.objects.get(pk=6001)

    def make(self, slug, status=DashboardStatus.published, **overrides):
        fields = {
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "root_form": self.root,
            "created_by": self.user,
            "status": status,
            "published_config": snapshot([widget()]),
        }
        fields.update(overrides)
        return Dashboard.objects.create(**fields)

    def test_list_returns_a_bare_array_of_published_dashboards(self):
        self.make("alpha")
        self.make("beta")
        res = self.client.get(READ_URL, **self.header)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        # Not an envelope, for the same reason as the builder list: the
        # merged client does Array.isArray(res.data) ? res.data : [].
        self.assertIsInstance(body, list)
        self.assertEqual(
            sorted(d["slug"] for d in body), ["alpha", "beta"]
        )

    def test_list_hides_drafts(self):
        self.make("published-one")
        self.make("draft-one", status=DashboardStatus.draft)
        body = self.client.get(READ_URL, **self.header).json()
        self.assertEqual([d["slug"] for d in body], ["published-one"])

    def test_list_hides_soft_deleted_dashboards(self):
        self.make("gone").delete()
        self.assertEqual(
            self.client.get(READ_URL, **self.header).json(), []
        )

    def test_list_rows_carry_widget_stubs(self):
        self.make(
            "alpha",
            published_config=snapshot(
                [widget(), widget(id=2, type="table", col_span=24)]
            ),
        )
        body = self.client.get(READ_URL, **self.header).json()
        self.assertEqual(
            body[0]["widgets"],
            [
                {"type": "kpi", "col_span": 6},
                {"type": "table", "col_span": 24},
            ],
        )

    def test_detail_serves_the_snapshot(self):
        self.make("alpha", default_filters={"date": {"enabled": False}})
        res = self.client.get(
            "{0}/alpha".format(READ_URL), **self.header
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["slug"], "alpha")
        self.assertEqual(body["root_form"]["id"], self.root.id)
        self.assertEqual(len(body["widgets"]), 1)
        self.assertEqual(body["widgets"][0]["title"], "Operational")

    def test_detail_serves_the_snapshots_filters_not_the_rows(self):
        # default_filters is inside the snapshot (D-1), so the live
        # column can disagree with it until the next publish.
        self.make(
            "alpha",
            default_filters={"date": {"enabled": False}},
            published_config=snapshot(
                [widget()], {"date": {"enabled": True}}
            ),
        )
        body = self.client.get(
            "{0}/alpha".format(READ_URL), **self.header
        ).json()
        self.assertEqual(
            body["default_filters"], {"date": {"enabled": True}}
        )

    def test_published_at_matches_the_builder_endpoints_format(self):
        # One field, two endpoints. VIZ-008 must not have to parse two
        # formats depending on where it read the dashboard from.
        dashboard = self.make("alpha")
        Dashboard.objects.filter(pk=dashboard.pk).update(
            published_at=datetime(2026, 8, 25, 10, 30, 0)
        )
        body = self.client.get(
            "{0}/alpha".format(READ_URL), **self.header
        ).json()
        self.assertEqual(body["published_at"], "25-08-2026 10:30:00")

    def test_a_draft_slug_is_404(self):
        self.make("secret", status=DashboardStatus.draft)
        res = self.client.get(
            "{0}/secret".format(READ_URL), **self.header
        )
        # Indistinguishable from nonexistent, on purpose: a draft is not
        # a viewer's to know about.
        self.assertEqual(res.status_code, 404)

    def test_an_unknown_slug_is_404(self):
        res = self.client.get(
            "{0}/nothing-here".format(READ_URL), **self.header
        )
        self.assertEqual(res.status_code, 404)

    def test_an_anonymous_caller_is_refused(self):
        self.make("alpha")
        self.assertEqual(self.client.get(READ_URL).status_code, 401)
        self.assertEqual(
            self.client.get("{0}/alpha".format(READ_URL)).status_code,
            401,
        )

    def test_a_null_snapshot_degrades_to_an_empty_dashboard(self):
        # Unreachable through the API — publish writes status and
        # published_config together — but a 500 in the viewer would be a
        # worse answer than an empty page.
        self.make("alpha", published_config=None)
        res = self.client.get(
            "{0}/alpha".format(READ_URL), **self.header
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["widgets"], [])
        self.assertEqual(res.json()["default_filters"], {})

    def test_broken_widgets_are_annotated_and_the_rest_are_not(self):
        self.make(
            "alpha",
            published_config=snapshot(
                [
                    widget(id=1),
                    widget(id=2),
                    widget(id=3, form=6002, question=600203),
                    widget(id=4, form=6002, question=600203),
                    widget(id=5, form=6002, question=600203),
                ]
            ),
        )
        Questions.objects.get(pk=600102).delete()
        body = self.client.get(
            "{0}/alpha".format(READ_URL), **self.header
        ).json()
        self.assertEqual(len(body["widgets"]), 5)
        flagged = [w for w in body["widgets"] if w["is_broken"]]
        self.assertEqual([w["id"] for w in flagged], [1, 2])
        for row in flagged:
            self.assertEqual(row["broken_reason"], "question_deleted")
        for row in body["widgets"][2:]:
            self.assertIs(row["is_broken"], False)

    def test_detail_query_count_does_not_grow_with_widget_count(self):
        self.make(
            "small",
            published_config=snapshot(
                [widget(id=i) for i in range(2)]
            ),
        )
        self.make(
            "large",
            published_config=snapshot(
                [widget(id=i) for i in range(12)]
            ),
        )
        with CaptureQueriesContext(connection) as small:
            self.client.get(
                "{0}/small".format(READ_URL), **self.header
            )
        with CaptureQueriesContext(connection) as large:
            self.client.get(
                "{0}/large".format(READ_URL), **self.header
            )
        self.assertEqual(
            len(small.captured_queries), len(large.captured_queries)
        )

    def test_list_query_count_does_not_grow_with_dashboard_count(self):
        self.make("one")
        with CaptureQueriesContext(connection) as small:
            self.client.get(READ_URL, **self.header)
        self.make("two")
        self.make("three")
        with CaptureQueriesContext(connection) as large:
            self.client.get(READ_URL, **self.header)
        self.assertEqual(
            len(small.captured_queries), len(large.captured_queries)
        )


@override_settings(USE_TZ=False)
class DashboardReadAcceptanceTestCase(TestCase, ProfileTestHelperMixin):
    """Spec D-1, end to end: editing must not leak to viewers."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_accept@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.header = auth(self.user)
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=Forms.objects.get(pk=6001),
            created_by=self.user,
        )
        self.widget = self.dashboard.widgets.create(
            order=1,
            type=1,
            col_span=6,
            title="Original",
            form_id=6001,
            question_id=600102,
            config={},
        )
        self.manage = "{0}/{1}".format(MANAGE_URL, self.dashboard.id)

    def read(self):
        return self.client.get(
            "{0}/water-points".format(READ_URL), **self.header
        ).json()

    def test_the_snapshot_only_moves_when_publish_is_called(self):
        self.client.post(
            "{0}/publish".format(self.manage), **self.header
        )
        self.assertEqual(self.read()["widgets"][0]["title"], "Original")

        res = self.client.put(
            self.manage,
            json.dumps(
                {
                    "name": "Water Points",
                    "description": None,
                    "default_filters": {},
                    "widgets": [
                        {
                            "id": self.widget.id,
                            "order": 1,
                            "type": "kpi",
                            "col_span": 6,
                            "title": "Edited",
                            "color": None,
                            "form": 6001,
                            "question": 600102,
                            "config": {},
                        }
                    ],
                }
            ),
            content_type="application/json",
            **self.header
        )
        self.assertEqual(res.status_code, 200)
        # The edit is saved, and invisible to viewers.
        self.assertEqual(self.read()["widgets"][0]["title"], "Original")

        self.client.post(
            "{0}/publish".format(self.manage), **self.header
        )
        self.assertEqual(self.read()["widgets"][0]["title"], "Edited")

    def test_unpublishing_hides_the_slug_but_keeps_the_dashboard(self):
        self.client.post(
            "{0}/publish".format(self.manage), **self.header
        )
        self.client.post(
            "{0}/unpublish".format(self.manage), **self.header
        )
        self.assertEqual(
            self.client.get(
                "{0}/water-points".format(READ_URL), **self.header
            ).status_code,
            404,
        )
        # Still the author's to edit, and the snapshot survives.
        self.assertEqual(
            self.client.get(self.manage, **self.header).status_code, 200
        )
        self.dashboard.refresh_from_db()
        self.assertIsNotNone(self.dashboard.published_config)


@override_settings(USE_TZ=False)
class DashboardReadTenantIsolationTestCase(TenantIsolationTestCase):
    """Slugs are unique per tenant, so the same slug means two things."""

    def setUp(self):
        super().setUp()
        self.tenants = {"a": self.a, "b": self.b}
        for label, fixture in self.tenants.items():
            Dashboard.objects.create(
                name="{0} dashboard".format(label),
                slug="shared",
                root_form=fixture["form"],
                tenant=fixture["tenant"],
                status=DashboardStatus.published,
                published_config={
                    "default_filters": {},
                    "widgets": [],
                },
            )

    def test_each_tenant_resolves_the_shared_slug_to_its_own(self):
        for label, fixture in self.tenants.items():
            body = self.client.get(
                "/api/v1/dashboards/shared",
                **self.auth(fixture["user"])
            ).json()
            self.assertEqual(
                body["name"], "{0} dashboard".format(label)
            )

    def test_the_list_shows_only_the_callers_tenant(self):
        body = self.client.get(
            "/api/v1/dashboards", **self.auth(self.a["user"])
        ).json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["name"], "a dashboard")


@override_settings(USE_TZ=False)
class DashboardReadPermissionTestCase(TenantIsolationTestCase):
    """Publication is to the tenant: a token is the whole requirement."""

    def test_a_user_with_no_dashboard_access_can_read(self):
        Dashboard.objects.create(
            name="Acme dashboard",
            slug="acme-dashboard",
            root_form=self.a["form"],
            tenant=self.a["tenant"],
            status=DashboardStatus.published,
            published_config={"default_filters": {}, "widgets": []},
        )
        plain = SystemUser.objects.create_user(
            email="reader@acme.org",
            password="Secret#Pass123",
            first_name="Read",
            last_name="Er",
            tenant=self.a["tenant"],
        )
        header = self.auth(plain)
        self.assertEqual(
            self.client.get(
                "/api/v1/dashboards", **header
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/dashboards/acme-dashboard", **header
            ).status_code,
            200,
        )
