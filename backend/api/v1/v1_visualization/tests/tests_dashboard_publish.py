import json
from datetime import datetime
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms, Questions
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
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.dashboard_builder_views import (
    DashboardBuilderViewSet,
)
from api.v1.v1_visualization.models import Dashboard
from utils.tenant_test_case import TenantIsolationTestCase

BASE_URL = "/api/v1/manage/dashboards"


def auth(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}


@override_settings(USE_TZ=False)
class DashboardPublishTestCase(TestCase, ProfileTestHelperMixin):
    """Publish snapshots; editing afterwards does not reach viewers."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_publish@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.header = auth(self.user)
        self.root = Forms.objects.get(pk=6001)
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            created_by=self.user,
            default_filters={"date": {"enabled": True}},
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
        self.url = "{0}/{1}".format(BASE_URL, self.dashboard.id)

    def publish(self):
        return self.client.post(
            "{0}/publish".format(self.url), **self.header
        )

    def unpublish(self):
        return self.client.post(
            "{0}/unpublish".format(self.url), **self.header
        )

    def put(self, widgets, **overrides):
        payload = {
            "name": "Water Points",
            "description": None,
            "default_filters": {"date": {"enabled": True}},
            "widgets": widgets,
        }
        payload.update(overrides)
        return self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            **self.header
        )

    def widget_payload(self, **overrides):
        payload = {
            "id": None,
            "order": 1,
            "type": "kpi",
            "col_span": 6,
            "title": None,
            "color": None,
            "form": 6001,
            "question": 600102,
            "config": {},
        }
        payload.update(overrides)
        return payload

    # ── publish ──

    def test_publish_snapshots_and_flips_status(self):
        res = self.publish()
        self.assertEqual(res.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.status, DashboardStatus.published
        )
        self.assertIsNotNone(self.dashboard.published_at)
        config = self.dashboard.published_config
        self.assertEqual(
            config["default_filters"], {"date": {"enabled": True}}
        )
        self.assertEqual(len(config["widgets"]), 1)
        self.assertEqual(config["widgets"][0]["title"], "Original")
        self.assertEqual(res.json()["status"], "published")

    def test_editing_after_publish_leaves_the_snapshot_alone(self):
        """Spec D-1, the row-level half of the acceptance test.

        The end-to-end half — that GET /dashboards/{slug} returns the
        old response — lives in tests_dashboard_read.py.
        """
        self.publish()
        res = self.put(
            [self.widget_payload(id=self.widget.id, title="Edited")]
        )
        self.assertEqual(res.status_code, 200)
        self.widget.refresh_from_db()
        self.assertEqual(self.widget.title, "Edited")
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.published_config["widgets"][0]["title"],
            "Original",
        )

    def test_republishing_re_snapshots(self):
        self.publish()
        self.put(
            [self.widget_payload(id=self.widget.id, title="Edited")]
        )
        self.publish()
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.published_config["widgets"][0]["title"],
            "Edited",
        )

    def test_republishing_moves_published_at(self):
        # Spec D-2: unlike Forms.published_at, a dashboard's date is
        # "how fresh is this view", so every publish rewrites it. Set an
        # old value explicitly rather than comparing two now() calls,
        # which can land in the same microsecond.
        self.publish()
        Dashboard.objects.filter(pk=self.dashboard.pk).update(
            published_at=datetime(2020, 1, 1)
        )
        self.publish()
        self.dashboard.refresh_from_db()
        self.assertNotEqual(self.dashboard.published_at.year, 2020)

    def test_publishing_a_dashboard_with_no_widgets_is_allowed(self):
        self.dashboard.widgets.all().delete()
        self.assertEqual(self.publish().status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.published_config["widgets"], [])

    def test_publishing_a_broken_dashboard_is_400_and_writes_nothing(
        self,
    ):
        """Spec D-4.

        A widget pointing at a deleted question cannot be saved either —
        VIZ-005's PUT refuses it — so this state is only reachable when
        the question is deleted after the fact. Publish must not
        propagate it into `published_config`, which nothing revalidates
        downstream.
        """
        Questions.objects.get(pk=600102).delete()
        res = self.publish()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["widget_index"], 0)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.status, DashboardStatus.draft)
        self.assertIsNone(self.dashboard.published_config)
        self.assertIsNone(self.dashboard.published_at)

    def test_a_failed_republish_keeps_the_previous_snapshot(self):
        self.publish()
        Questions.objects.get(pk=600102).delete()
        self.assertEqual(self.publish().status_code, 400)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.published_config["widgets"][0]["title"],
            "Original",
        )
        self.assertEqual(
            self.dashboard.status, DashboardStatus.published
        )

    # ── unpublish ──

    def test_unpublish_drafts_the_dashboard_and_keeps_the_snapshot(
        self,
    ):
        self.publish()
        res = self.unpublish()
        self.assertEqual(res.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.status, DashboardStatus.draft)
        # Left alone on purpose: it records what was last live, and the
        # read namespace filters on status, so clearing it would destroy
        # information without changing what anyone can see.
        self.assertIsNotNone(self.dashboard.published_config)
        self.assertIsNotNone(self.dashboard.published_at)

    def test_unpublishing_a_draft_is_400(self):
        res = self.unpublish()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.json()["message"], "Dashboard is not published"
        )

    def test_an_unpublished_dashboard_is_still_editable(self):
        self.publish()
        self.unpublish()
        res = self.put(
            [self.widget_payload(id=self.widget.id, title="Still edits")]
        )
        self.assertEqual(res.status_code, 200)

    def test_publish_after_unpublish_works(self):
        self.publish()
        self.unpublish()
        self.assertEqual(self.publish().status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.status, DashboardStatus.published
        )

    def test_publishing_an_unknown_id_is_404(self):
        res = self.client.post(
            "{0}/99999/publish".format(BASE_URL), **self.header
        )
        self.assertEqual(res.status_code, 404)


@override_settings(USE_TZ=False)
class DashboardPublishPermissionTestCase(TestCase):
    """publish and unpublish are gated on dashboard_publish.

    The user is deliberately not a superuser: DashboardAccess
    short-circuits to True for those, so a superuser fixture asserts
    nothing.
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
            email="publisher@akvo.org",
            password="Secret#Pass123",
            first_name="Pub",
            last_name="Lisher",
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
        self.url = "{0}/{1}".format(BASE_URL, self.dashboard.id)

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

    def test_publish_needs_dashboard_publish_not_edit(self):
        url = "{0}/publish".format(self.url)
        self.grant(FeatureAccessTypes.dashboard_edit)
        self.assertEqual(
            self.client.post(url, **auth(self.user)).status_code, 403
        )
        self.grant(FeatureAccessTypes.dashboard_publish)
        self.assertEqual(
            self.client.post(url, **auth(self.user)).status_code, 200
        )

    def test_unpublish_needs_dashboard_publish(self):
        url = "{0}/unpublish".format(self.url)
        self.assertEqual(
            self.client.post(url, **auth(self.user)).status_code, 403
        )
        self.grant(FeatureAccessTypes.dashboard_publish)
        # 400, not 403: permission passed, the dashboard is a draft.
        self.assertEqual(
            self.client.post(url, **auth(self.user)).status_code, 400
        )


@override_settings(USE_TZ=False)
class DashboardPublishTenantIsolationTestCase(TenantIsolationTestCase):
    """Publishing is a write; a sequential id must not cross tenants."""

    def setUp(self):
        super().setUp()
        self.b_dashboard = Dashboard.objects.create(
            name="Beta's dashboard",
            slug="betas-dashboard",
            root_form=self.b["form"],
            tenant=self.b["tenant"],
            status=DashboardStatus.published,
            published_config={"default_filters": {}, "widgets": []},
        )

    def test_publish_and_unpublish_on_another_tenants_id_are_404(self):
        header = self.auth(self.a["user"])
        base = "{0}/{1}".format(BASE_URL, self.b_dashboard.id)
        for action in ("publish", "unpublish"):
            res = self.client.post(
                "{0}/{1}".format(base, action), **header
            )
            self.assertEqual(res.status_code, 404)
        self.b_dashboard.refresh_from_db()
        self.assertEqual(
            self.b_dashboard.status, DashboardStatus.published
        )


@override_settings(USE_TZ=False)
class DashboardDuplicateTestCase(TestCase, ProfileTestHelperMixin):
    """A clone is a draft with its own name, slug and history."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_duplicate@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.header = auth(self.user)
        self.root = Forms.objects.get(pk=6001)
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            description="Operational status",
            root_form=self.root,
            created_by=self.user,
            default_filters={"date": {"enabled": True}},
            status=DashboardStatus.published,
            published_config={"default_filters": {}, "widgets": []},
            published_at=datetime(2026, 1, 1),
        )
        self.dashboard.widgets.create(
            order=1,
            type=1,
            col_span=6,
            title="Operational",
            color="#64A73B",
            form_id=6001,
            question_id=600102,
            config={"value_type": "number"},
        )
        self.dashboard.widgets.create(
            order=2,
            type=7,
            col_span=24,
            title="Section",
            config={"text": "Details"},
        )

    def duplicate(self, dashboard_id=None):
        return self.client.post(
            "{0}/{1}/duplicate".format(
                BASE_URL, dashboard_id or self.dashboard.id
            ),
            **self.header
        )

    def test_duplicate_returns_a_draft_with_a_fresh_name_and_slug(self):
        res = self.duplicate()
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["name"], "Water Points (copy)")
        self.assertEqual(body["slug"], "water-points-copy")
        self.assertEqual(body["status"], "draft")
        self.assertNotEqual(body["id"], self.dashboard.id)

    def test_duplicate_returns_the_list_row_shape(self):
        # DashboardList.jsx pushes res.data straight into its table
        # array, so the body has to look like a row from GET
        # /manage/dashboards — widget stubs included.
        body = self.duplicate().json()
        self.assertEqual(
            body["widgets"],
            [
                {"type": "kpi", "col_span": 6},
                {"type": "section_title", "col_span": 24},
            ],
        )
        self.assertEqual(body["root_form"]["id"], self.root.id)
        self.assertEqual(body["created_by"]["id"], self.user.id)

    def test_duplicate_copies_the_widget_rows_in_full(self):
        clone = Dashboard.objects.get(pk=self.duplicate().json()["id"])
        rows = list(clone.widgets.order_by("order"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].title, "Operational")
        self.assertEqual(rows[0].color, "#64A73B")
        self.assertEqual(rows[0].form_id, 6001)
        self.assertEqual(rows[0].question_id, 600102)
        self.assertEqual(rows[0].config, {"value_type": "number"})
        self.assertEqual(rows[1].type, 7)
        self.assertIsNone(rows[1].form_id)

    def test_duplicate_keeps_the_root_form_and_filters(self):
        clone = Dashboard.objects.get(pk=self.duplicate().json()["id"])
        # Same family: a duplicate that could change root_form would
        # contradict D-3, since every widget is bound to that family.
        self.assertEqual(clone.root_form_id, self.root.id)
        self.assertEqual(
            clone.default_filters, {"date": {"enabled": True}}
        )
        self.assertEqual(clone.description, "Operational status")

    def test_duplicate_drops_the_publication_state(self):
        clone = Dashboard.objects.get(pk=self.duplicate().json()["id"])
        self.assertEqual(clone.status, DashboardStatus.draft)
        self.assertIsNone(clone.published_config)
        self.assertIsNone(clone.published_at)

    def test_duplicating_twice_uniquifies_the_slug(self):
        self.assertEqual(
            self.duplicate().json()["slug"], "water-points-copy"
        )
        self.assertEqual(
            self.duplicate().json()["slug"], "water-points-copy-2"
        )

    def test_duplicating_a_duplicate_stacks_the_suffix(self):
        first = self.duplicate().json()
        second = self.duplicate(first["id"]).json()
        self.assertEqual(second["name"], "Water Points (copy) (copy)")
        self.assertEqual(second["slug"], "water-points-copy-copy")

    def test_a_near_limit_name_and_slug_stay_within_their_columns(self):
        # Both columns are varchar(255) and neither input is bounded by
        # the UI. Truncating after appending would either overflow the
        # column or cut the suffix off; truncating the stem first is
        # what keeps "-copy" intact.
        long_dashboard = Dashboard.objects.create(
            name="A" * 255,
            slug="b" * 255,
            root_form=self.root,
            created_by=self.user,
        )
        body = self.duplicate(long_dashboard.id).json()
        self.assertEqual(body["name"][-7:], " (copy)")
        self.assertLessEqual(len(body["name"]), 255)
        self.assertEqual(body["slug"][-5:], "-copy")
        self.assertLessEqual(len(body["slug"]), 255)
        # No trailing hyphen before the suffix: "b...b--copy" would not
        # match SLUG_PATTERN and could never be reached by URL.
        self.assertNotIn("--", body["slug"])

    def test_a_slug_truncated_onto_a_hyphen_does_not_double_it(self):
        # copy_slug keeps slug[:244], so a hyphen at index 243 is the
        # last character retained. Without the rstrip("-") the result
        # would be "b...b--copy", which fails SLUG_PATTERN and could
        # never be reached by URL.
        hyphenated = Dashboard.objects.create(
            name="Hyphen edge",
            slug="{0}-{1}".format("b" * 243, "c" * 11),
            root_form=self.root,
            created_by=self.user,
        )
        body = self.duplicate(hyphenated.id).json()
        self.assertEqual(body["slug"], "{0}-copy".format("b" * 243))
        self.assertNotIn("--", body["slug"])

    def test_a_soft_deleted_copy_frees_its_slug(self):
        first = self.duplicate().json()
        Dashboard.objects.get(pk=first["id"]).delete()
        self.assertEqual(
            self.duplicate().json()["slug"], "water-points-copy"
        )

    def test_duplicating_an_unknown_id_is_404(self):
        self.assertEqual(self.duplicate(99999).status_code, 404)


@override_settings(USE_TZ=False)
class DashboardDuplicatePermissionTestCase(TestCase):
    """duplicate is a create, and is gated as one."""

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
            email="cloner@akvo.org",
            password="Secret#Pass123",
            first_name="Clo",
            last_name="Ner",
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
        self.url = "{0}/{1}/duplicate".format(
            BASE_URL, self.dashboard.id
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

    def test_duplicate_needs_dashboard_create_not_view(self):
        self.grant(FeatureAccessTypes.dashboard_view)
        self.assertEqual(
            self.client.post(self.url, **auth(self.user)).status_code,
            403,
        )
        self.grant(FeatureAccessTypes.dashboard_create)
        self.assertEqual(
            self.client.post(self.url, **auth(self.user)).status_code,
            201,
        )


@override_settings(USE_TZ=False)
class DashboardDuplicateTenantIsolationTestCase(
    TenantIsolationTestCase
):
    """A duplicate must not be able to walk a dashboard across tenants."""

    def setUp(self):
        super().setUp()
        self.b_dashboard = Dashboard.objects.create(
            name="Beta's dashboard",
            slug="betas-dashboard",
            root_form=self.b["form"],
            tenant=self.b["tenant"],
        )

    def test_duplicating_another_tenants_dashboard_is_404(self):
        res = self.client.post(
            "{0}/{1}/duplicate".format(BASE_URL, self.b_dashboard.id),
            **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(Dashboard.objects.count(), 1)

    def test_a_clone_is_stamped_with_the_callers_tenant(self):
        own = Dashboard.objects.create(
            name="Acme's dashboard",
            slug="acmes-dashboard",
            root_form=self.a["form"],
            tenant=self.a["tenant"],
        )
        res = self.client.post(
            "{0}/{1}/duplicate".format(BASE_URL, own.id),
            **self.auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 201)
        clone = Dashboard.objects.get(pk=res.json()["id"])
        self.assertEqual(clone.tenant_id, self.a["tenant"].id)
        self.assertEqual(clone.created_by_id, self.a["user"].id)


@override_settings(USE_TZ=False)
class DashboardActionMapTestCase(TestCase):
    """Every routed action must be in ACCESS_PER_ACTION.

    That map is the only thing standing between an action and
    tenant-wide access. Before this slice a missing entry fell through
    to IsAuthenticated, which for anyone already signed in is
    indistinguishable from a granted permission.
    """

    def test_get_permissions_denies_an_unmapped_action(self):
        # A superuser deliberately: the branch has to refuse the most
        # privileged caller there is, not merely an unprivileged one.
        user = SystemUser.objects.create_superuser(
            email="root@akvo.org",
            password="Secret#Pass123",
            first_name="Ro",
            last_name="Ot",
        )
        view = DashboardBuilderViewSet()
        view.action = "not_a_real_action"
        # SimpleNamespace rather than APIRequestFactory, as in
        # tests_dashboard_permissions: these permission classes read
        # request.user and nothing else, and a bare factory request has
        # no .user attached at all — IsAuthenticated would raise on it
        # instead of returning a verdict.
        request = SimpleNamespace(user=user)
        permissions = view.get_permissions()
        self.assertTrue(permissions)
        self.assertFalse(
            any(
                permission.has_permission(request, view)
                for permission in permissions
            )
        )

    def test_every_routed_action_is_mapped(self):
        self.assertEqual(
            sorted(DashboardBuilderViewSet.ACCESS_PER_ACTION),
            [
                "create",
                "destroy",
                "duplicate",
                "list",
                "publish",
                "retrieve",
                "sources",
                "unpublish",
                "update",
            ],
        )
