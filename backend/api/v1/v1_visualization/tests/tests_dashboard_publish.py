import json
from datetime import datetime

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
