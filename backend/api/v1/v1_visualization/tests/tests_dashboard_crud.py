import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.constants import (
    FeatureAccessTypes,
    FeatureTypes,
)
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    RoleFeatureAccess,
    UserRole,
)
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_visualization.constants import DashboardKind, DashboardStatus
from api.v1.v1_visualization.models import Dashboard
from utils.tenant_test_case import TenantIsolationTestCase

BASE_URL = "/api/v1/manage/dashboards"


def auth(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}


@override_settings(USE_TZ=False)
class DashboardCrudTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_crud@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.header = auth(self.user)
        self.root = Forms.objects.get(pk=6001)

    def post(self, payload):
        return self.client.post(
            BASE_URL,
            json.dumps(payload),
            content_type="application/json",
            **self.header
        )

    # ── create ──

    def test_create_returns_a_draft_with_a_derived_slug(self):
        res = self.post(
            {"name": "Water Points Overview", "root_form": self.root.id}
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["slug"], "water-points-overview")
        self.assertEqual(body["status"], "draft")
        self.assertEqual(body["root_form"]["id"], self.root.id)
        self.assertEqual(body["root_form"]["name"], self.root.name)
        self.assertEqual(body["created_by"]["id"], self.user.id)
        self.assertEqual(body["widgets"], [])

    def test_create_ignores_a_tenant_in_the_payload(self):
        other = Tenant.objects.create(subdomain="elsewhere")
        res = self.post(
            {
                "name": "Planted",
                "root_form": self.root.id,
                "tenant": other.id,
            }
        )
        self.assertEqual(res.status_code, 201)
        dashboard = Dashboard.objects.get(pk=res.json()["id"])
        self.assertEqual(dashboard.tenant, self.user.tenant)

    def test_create_rejects_a_monitoring_root_form(self):
        res = self.post({"name": "Nope", "root_form": 6002})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "root_form")

    def test_create_rejects_a_name_with_no_slug_characters(self):
        res = self.post({"name": "###", "root_form": self.root.id})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "name")

    def test_a_client_supplied_slug_that_fails_the_pattern_reports_slug(
        self,
    ):
        # The value is a client-supplied "slug", not a derived "name",
        # even though a bad name is what usually trips this check.
        res = self.post(
            {
                "name": "Water Points",
                "root_form": self.root.id,
                "slug": "Not A Valid Slug!!",
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "slug")

    def test_a_300_character_name_is_400_not_500(self):
        # This is the user-reachable one: BuilderInspector and
        # CreateDashboardModal render the name input with no
        # maxLength, so a pasted long name must not 500.
        res = self.post({"name": "A" * 300, "root_form": self.root.id})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "name")

    # ── slug collisions ──

    def test_a_duplicate_slug_is_a_409_with_a_usable_suggestion(self):
        self.post({"name": "Water Points", "root_form": self.root.id})
        res = self.post(
            {"name": "Water Points", "root_form": self.root.id}
        )
        self.assertEqual(res.status_code, 409)
        suggested = res.json()["suggested_slug"]
        self.assertEqual(suggested, "water-points-2")
        # The merged CreateDashboardModal retries with exactly this.
        retry = self.post(
            {
                "name": "Water Points",
                "root_form": self.root.id,
                "slug": suggested,
            }
        )
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(retry.json()["slug"], "water-points-2")

    def test_a_soft_deleted_dashboard_frees_its_slug(self):
        first = self.post(
            {"name": "Water Points", "root_form": self.root.id}
        ).json()
        self.client.delete(
            "{0}/{1}".format(BASE_URL, first["id"]), **self.header
        )
        res = self.post(
            {"name": "Water Points", "root_form": self.root.id}
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["slug"], "water-points")

    # ── list and retrieve ──

    def test_list_returns_a_bare_array_including_drafts(self):
        self.post({"name": "One", "root_form": self.root.id})
        self.post({"name": "Two", "root_form": self.root.id})
        res = self.client.get(BASE_URL, **self.header)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        # Not an envelope. DashboardList and DashboardBuilder both do
        # Array.isArray(res.data) ? res.data : [], so a paginated
        # response would render an empty list, silently.
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 2)
        self.assertEqual(
            sorted(d["name"] for d in body), ["One", "Two"]
        )

    def test_list_rows_carry_the_widget_stubs_the_thumbnail_needs(self):
        created = self.post(
            {"name": "One", "root_form": self.root.id}
        ).json()
        dashboard = Dashboard.objects.get(pk=created["id"])
        dashboard.widgets.create(
            order=1, type=1, col_span=6, config={}
        )
        res = self.client.get(BASE_URL, **self.header)
        self.assertEqual(
            res.json()[0]["widgets"], [{"type": "kpi", "col_span": 6}]
        )

    def test_list_query_count_does_not_grow_with_dashboard_count(self):
        # Without select_related/prefetch_related, root_form,
        # created_by and widgets are each a fresh query per row: five
        # dashboards would cost roughly 1 + 5*3 queries. The exact
        # count is not the point (JWT auth adds its own queries) — the
        # point is that it stays flat as N grows.
        def make(n):
            for i in range(n):
                d = Dashboard.objects.create(
                    name="D{0}".format(i),
                    slug="d{0}".format(i),
                    root_form=self.root,
                    created_by=self.user,
                )
                d.widgets.create(order=1, type=1, col_span=6, config={})

        make(2)
        with CaptureQueriesContext(connection) as small:
            self.client.get(BASE_URL, **self.header)
        make(3)
        with CaptureQueriesContext(connection) as large:
            self.client.get(BASE_URL, **self.header)
        self.assertEqual(
            len(small.captured_queries), len(large.captured_queries)
        )

    def test_retrieve_returns_the_detail_shape(self):
        created = self.post(
            {"name": "One", "root_form": self.root.id}
        ).json()
        res = self.client.get(
            "{0}/{1}".format(BASE_URL, created["id"]), **self.header
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        for key in (
            "default_filters",
            "published_at",
            "widgets",
            "root_form",
            "created_by",
        ):
            self.assertIn(key, body)

    def test_retrieve_of_an_unknown_id_is_404(self):
        res = self.client.get(
            "{0}/99999".format(BASE_URL), **self.header
        )
        self.assertEqual(res.status_code, 404)

    # ── destroy ──

    def test_destroy_soft_deletes(self):
        created = self.post(
            {"name": "One", "root_form": self.root.id}
        ).json()
        res = self.client.delete(
            "{0}/{1}".format(BASE_URL, created["id"]), **self.header
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            Dashboard.objects.filter(pk=created["id"]).exists()
        )
        self.assertTrue(
            Dashboard.objects_deleted.filter(pk=created["id"]).exists()
        )


@override_settings(USE_TZ=False)
class DashboardTenantIsolationTestCase(TenantIsolationTestCase):
    """A sequential id must not cross a workspace boundary (MT-004)."""

    def setUp(self):
        super().setUp()
        self.b_dashboard = Dashboard.objects.create(
            name="Beta's dashboard",
            slug="betas-dashboard",
            root_form=self.b["form"],
            tenant=self.b["tenant"],
        )

    def test_every_action_on_another_tenants_id_is_404(self):
        url = "{0}/{1}".format(BASE_URL, self.b_dashboard.id)
        header = self.auth(self.a["user"])
        self.assertEqual(self.client.get(url, **header).status_code, 404)
        self.assertEqual(
            self.client.delete(url, **header).status_code, 404
        )
        res = self.client.put(
            url,
            json.dumps({"name": "Mine now", "widgets": []}),
            content_type="application/json",
            **header
        )
        self.assertEqual(res.status_code, 404)

    def test_list_shows_only_the_callers_tenant(self):
        res = self.client.get(BASE_URL, **self.auth(self.a["user"]))
        self.assertEqual(res.json(), [])

    def test_creating_on_another_tenants_root_form_is_400(self):
        res = self.client.post(
            BASE_URL,
            json.dumps(
                {"name": "Borrowed", "root_form": self.b["form"].id}
            ),
            content_type="application/json",
            **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "root_form")


@override_settings(USE_TZ=False)
class DashboardPermissionTestCase(TestCase):
    """Each action is gated by its own access type.

    The users here are deliberately not superusers: DashboardAccess
    short-circuits to True for those, so a superuser fixture would
    assert nothing.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(subdomain="acme")
        self.level = Levels.objects.create(
            name="National", level=0, tenant=self.tenant
        )
        self.administration = Administration.objects.create(
            parent=None,
            level=self.level,
            name="Acme",
            tenant=self.tenant,
        )
        self.user = SystemUser.objects.create_user(
            email="builder@akvo.org",
            password="Secret#Pass123",
            first_name="Build",
            last_name="Er",
            tenant=self.tenant,
        )
        self.form = Forms.objects.create(
            name="acme-form",
            tenant=self.tenant,
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        self.dashboard = Dashboard.objects.create(
            name="Acme dashboard",
            slug="acme-dashboard",
            root_form=self.form,
            tenant=self.tenant,
        )

    def grant(self, access):
        role = Role.objects.create(
            name="Role {0}".format(access),
            administration_level=self.level,
        )
        RoleFeatureAccess.objects.create(
            role=role,
            type=FeatureTypes.dashboard_builder,
            access=access,
        )
        UserRole.objects.create(
            user=self.user,
            role=role,
            administration=self.administration,
        )

    def call(self, method, url, body=None):
        kwargs = dict(auth(self.user))
        if body is not None:
            kwargs["content_type"] = "application/json"
            return getattr(self.client, method)(
                url, json.dumps(body), **kwargs
            )
        return getattr(self.client, method)(url, **kwargs)

    def test_list_needs_a_builder_access_not_view(self):
        # dashboard_view alone no longer opens the builder namespace: a
        # View-only role is a consumer, who reads dashboards through
        # the public/read namespace, not this manage one.
        self.assertEqual(self.call("get", BASE_URL).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("get", BASE_URL).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_edit)
        self.assertEqual(self.call("get", BASE_URL).status_code, 200)

    def test_create_needs_dashboard_create(self):
        body = {"name": "New", "root_form": self.form.id}
        self.assertEqual(
            self.call("post", BASE_URL, body).status_code, 403
        )
        self.grant(FeatureAccessTypes.dashboard_create)
        self.assertEqual(
            self.call("post", BASE_URL, body).status_code, 201
        )

    def test_retrieve_needs_a_builder_access_not_view(self):
        # Same contract change as list above: retrieve is a builder
        # action, so it needs one of the four building accesses.
        url = "{0}/{1}".format(BASE_URL, self.dashboard.id)
        self.assertEqual(self.call("get", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("get", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_edit)
        self.assertEqual(self.call("get", url).status_code, 200)

    def test_delete_needs_dashboard_delete_not_view(self):
        url = "{0}/{1}".format(BASE_URL, self.dashboard.id)
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("delete", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_delete)
        self.assertEqual(self.call("delete", url).status_code, 204)

    def test_update_needs_dashboard_edit_not_view(self):
        url = "{0}/{1}".format(BASE_URL, self.dashboard.id)
        body = {"name": "Renamed", "widgets": []}
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("put", url, body).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_edit)
        self.assertEqual(self.call("put", url, body).status_code, 200)

    def test_sources_needs_a_builder_access_not_view(self):
        # Same contract change as list above: sources is a builder
        # action, so it needs one of the four building accesses.
        url = "{0}/{1}/sources".format(BASE_URL, self.dashboard.id)
        self.assertEqual(self.call("get", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("get", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_edit)
        self.assertEqual(self.call("get", url).status_code, 200)


@override_settings(USE_TZ=False)
class DashboardUpdateTestCase(TestCase, ProfileTestHelperMixin):
    """PUT replaces the widget array wholesale, or changes nothing."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_update@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.header = auth(self.user)
        self.root = Forms.objects.get(pk=6001)
        self.monitoring = Forms.objects.get(pk=6002)
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            created_by=self.user,
        )
        self.url = "{0}/{1}".format(BASE_URL, self.dashboard.id)
        self.kept = self.dashboard.widgets.create(
            order=1, type=1, col_span=6, title="Kept", config={}
        )
        self.dropped = self.dashboard.widgets.create(
            order=2, type=1, col_span=6, title="Dropped", config={}
        )

    def put(self, payload):
        return self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            **self.header
        )

    def body(self, widgets, **overrides):
        payload = {
            "name": "Water Points",
            "description": None,
            "default_filters": {"date": {"enabled": True}},
            "widgets": widgets,
        }
        payload.update(overrides)
        return payload

    def widget(self, **overrides):
        payload = {
            "id": None,
            "order": 1,
            "type": "kpi",
            "col_span": 6,
            "title": None,
            "color": None,
            "form": self.root.id,
            "question": None,
            "config": {},
        }
        payload.update(overrides)
        return payload

    def test_put_updates_creates_and_deletes_in_one_call(self):
        res = self.put(
            self.body(
                [
                    self.widget(
                        id=self.kept.id, order=1, title="Renamed"
                    ),
                    self.widget(order=2, title="Brand new"),
                ]
            )
        )
        self.assertEqual(res.status_code, 200)
        titles = list(
            self.dashboard.widgets.order_by("order").values_list(
                "title", flat=True
            )
        )
        self.assertEqual(titles, ["Renamed", "Brand new"])
        self.kept.refresh_from_db()
        self.assertEqual(self.kept.title, "Renamed")
        self.assertFalse(
            self.dashboard.widgets.filter(pk=self.dropped.id).exists()
        )

    def test_put_returns_the_reserialized_detail(self):
        res = self.put(self.body([self.widget(id=self.kept.id)]))
        body = res.json()
        self.assertEqual(len(body["widgets"]), 1)
        self.assertEqual(body["widgets"][0]["id"], self.kept.id)
        self.assertEqual(body["widgets"][0]["type"], "kpi")

    def test_put_updates_the_dashboard_metadata(self):
        res = self.put(
            self.body([], name="Renamed dashboard", description="Hi")
        )
        self.assertEqual(res.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.name, "Renamed dashboard")
        self.assertEqual(self.dashboard.description, "Hi")
        self.assertIsNotNone(self.dashboard.updated)

    def test_renaming_does_not_change_the_slug(self):
        # The slug is the dashboard's URL. Re-slugging on rename would
        # break every link for a cosmetic edit.
        self.put(self.body([], name="Something else entirely"))
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.slug, "water-points")

    def test_an_explicit_slug_in_the_payload_is_ignored(self):
        # update() never reads request.data["slug"] at all — the
        # rename test above only covers the derived case, this pins
        # the case where a client tries to set one directly.
        self.put(self.body([], slug="hijack"))
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.slug, "water-points")

    def test_omitting_description_clears_the_stored_value(self):
        # This is intended PUT-replace semantics, not a bug: pinned so
        # it cannot drift silently, not because it should change.
        self.dashboard.description = "Existing description"
        self.dashboard.save()
        payload = self.body([])
        del payload["description"]
        res = self.put(payload)
        self.assertEqual(res.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertIsNone(self.dashboard.description)

    def test_changing_root_form_is_400_without_a_widget_index(self):
        other = Forms.objects.create(
            name="Other registration",
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        res = self.put(self.body([], root_form=other.id))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "root_form")
        self.assertNotIn("widget_index", res.json())

    def test_a_failing_last_widget_leaves_the_stored_rows_untouched(
        self,
    ):
        before = list(
            self.dashboard.widgets.order_by("order").values_list(
                "id", "title", "col_span"
            )
        )
        res = self.put(
            self.body(
                [
                    self.widget(id=self.kept.id, title="Renamed"),
                    self.widget(order=2, col_span=99),
                ]
            )
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["widget_index"], 1)
        after = list(
            self.dashboard.widgets.order_by("order").values_list(
                "id", "title", "col_span"
            )
        )
        self.assertEqual(before, after)

    def test_an_empty_widget_array_clears_the_dashboard(self):
        res = self.put(self.body([]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.dashboard.widgets.count(), 0)

    def test_a_widget_id_from_another_dashboard_is_400(self):
        other = Dashboard.objects.create(
            name="Other", slug="other", root_form=self.root
        )
        stolen = other.widgets.create(
            order=1, type=1, col_span=6, config={}
        )
        res = self.put(self.body([self.widget(id=stolen.id)]))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "id")
        # And the victim keeps its row.
        self.assertTrue(other.widgets.filter(pk=stolen.id).exists())

    def test_a_widget_on_another_tenants_form_is_400(self):
        foreign_tenant = Tenant.objects.create(subdomain="beta")
        foreign_form = Forms.objects.create(
            name="beta-form",
            tenant=foreign_tenant,
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        res = self.put(
            self.body([self.widget(form=foreign_form.id)])
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["field"], "form")
        # "not found", not "outside the family": the second message
        # would confirm the id exists in another workspace.
        self.assertIn("not found", res.json()["message"])


# The three things the spec's Testing section names, in one string: a
# <script> tag, single-quoted attributes alongside double-quoted ones,
# and an &amp; entity. Nothing on the write path may normalise any of
# them, so the round-trip assertions below are worth only as much as
# this fixture puts at risk.
EMBED_SNIPPET = (
    "<iframe title=\"Sales\" width=\"800\" height=\"600\" "
    "src=\"https://app.powerbi.com/view?r=abc&amp;def\" "
    "frameborder=\"0\" allowFullScreen=\"true\"></iframe>"
    "<script src='https://app.powerbi.com/embed.js' "
    "data-report='sales&amp;q1'></script>"
)


@override_settings(USE_TZ=False)
class EmbedDashboardCrudTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_embed_crud@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.header = auth(self.user)

    def post(self, payload):
        return self.client.post(
            BASE_URL,
            json.dumps(payload),
            content_type="application/json",
            **self.header
        )

    def put(self, pk, payload):
        return self.client.put(
            "{0}/{1}".format(BASE_URL, pk),
            json.dumps(payload),
            content_type="application/json",
            **self.header
        )

    def create_embed(self, name="Sales", snippet=EMBED_SNIPPET):
        res = self.post(
            {"name": name, "kind": "embed", "embed_snippet": snippet}
        )
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()

    def test_create_stores_the_snippet_byte_for_byte(self):
        body = self.create_embed()
        self.assertEqual(body["kind"], "embed")
        self.assertEqual(body["embed_snippet"], EMBED_SNIPPET)
        self.assertIsNone(body["root_form"])
        self.assertEqual(body["status"], "draft")
        # The &amp; entity, the single/double quote mix and the script
        # tag survive untouched: nothing parses this value.
        stored = Dashboard.objects.get(pk=body["id"])
        self.assertEqual(stored.embed_snippet, EMBED_SNIPPET)

    def test_create_forces_empty_default_filters(self):
        body = self.create_embed()
        stored = Dashboard.objects.get(pk=body["id"])
        self.assertEqual(stored.default_filters, {})

    def test_update_replaces_the_snippet(self):
        body = self.create_embed()
        replacement = "<iframe src='https://public.tableau.com/x'></iframe>"
        res = self.put(
            body["id"],
            {
                "name": "Sales",
                "kind": "embed",
                "embed_snippet": replacement,
            },
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["embed_snippet"], replacement)

    def test_publish_snapshots_the_snippet(self):
        body = self.create_embed()
        res = self.client.post(
            "{0}/{1}/publish".format(BASE_URL, body["id"]), **self.header
        )
        self.assertEqual(res.status_code, 200, res.content)
        stored = Dashboard.objects.get(pk=body["id"])
        self.assertEqual(
            stored.published_config, {"embed_snippet": EMBED_SNIPPET}
        )

    def test_an_edit_after_publish_does_not_change_the_snapshot(self):
        # Spec D-5: content is snapshotted, identity is live.
        body = self.create_embed()
        self.client.post(
            "{0}/{1}/publish".format(BASE_URL, body["id"]), **self.header
        )
        self.put(
            body["id"],
            {
                "name": "Sales",
                "kind": "embed",
                "embed_snippet": "<iframe src='https://later/'></iframe>",
            },
        )
        stored = Dashboard.objects.get(pk=body["id"])
        self.assertEqual(
            stored.published_config["embed_snippet"], EMBED_SNIPPET
        )

    def test_duplicate_copies_kind_and_snippet_as_a_draft(self):
        body = self.create_embed()
        res = self.client.post(
            "{0}/{1}/duplicate".format(BASE_URL, body["id"]), **self.header
        )
        self.assertEqual(res.status_code, 201, res.content)
        clone = Dashboard.objects.get(pk=res.json()["id"])
        self.assertEqual(clone.kind, DashboardKind.embed)
        self.assertEqual(clone.embed_snippet, EMBED_SNIPPET)
        self.assertIsNone(clone.root_form_id)
        self.assertEqual(clone.status, DashboardStatus.draft)
        self.assertEqual(clone.widgets.count(), 0)

    def test_unpublish_and_visibility_are_unchanged_for_an_embed(self):
        body = self.create_embed()
        pk = body["id"]
        self.client.post(
            "{0}/{1}/publish".format(BASE_URL, pk), **self.header
        )
        res = self.client.post(
            "{0}/{1}/visibility".format(BASE_URL, pk),
            json.dumps({"is_public": True}),
            content_type="application/json",
            **self.header
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(Dashboard.objects.get(pk=pk).is_public)
        res = self.client.post(
            "{0}/{1}/unpublish".format(BASE_URL, pk), **self.header
        )
        self.assertEqual(res.status_code, 200, res.content)
        stored = Dashboard.objects.get(pk=pk)
        self.assertEqual(stored.status, DashboardStatus.draft)
        self.assertFalse(stored.is_public)
