import json

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
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

    def test_list_needs_dashboard_view(self):
        self.assertEqual(self.call("get", BASE_URL).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_view)
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

    def test_retrieve_needs_dashboard_view(self):
        url = "{0}/{1}".format(BASE_URL, self.dashboard.id)
        self.assertEqual(self.call("get", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("get", url).status_code, 200)

    def test_delete_needs_dashboard_delete_not_view(self):
        url = "{0}/{1}".format(BASE_URL, self.dashboard.id)
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(self.call("delete", url).status_code, 403)
        self.grant(FeatureAccessTypes.dashboard_delete)
        self.assertEqual(self.call("delete", url).status_code, 204)
