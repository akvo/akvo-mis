from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.dashboard_functions import (
    validate_dashboard_payload,
)
from api.v1.v1_visualization.dashboard_snapshot import (
    annotate_broken,
    build_snapshot,
)
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False)
class BuildSnapshotTestCase(TestCase, ProfileTestHelperMixin):
    """What publish freezes, and what it deliberately leaves live."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_snapshot@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.root = Forms.objects.get(pk=6001)
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            created_by=self.user,
            default_filters={"date": {"enabled": True}},
        )

    def widget(self, **overrides):
        fields = {
            "order": 1,
            "type": 1,
            "col_span": 6,
            "form_id": 6001,
            "question_id": 600102,
            "config": {},
        }
        fields.update(overrides)
        return self.dashboard.widgets.create(**fields)

    def test_snapshot_holds_widgets_and_default_filters(self):
        self.widget(title="Operational")
        snapshot = build_snapshot(self.dashboard)
        # Exactly two keys, which is also what pins spec D-1: name,
        # slug and root_form are served live from the row, so a
        # corrected typo must not need a re-publish to reach viewers.
        self.assertEqual(
            sorted(snapshot), ["default_filters", "widgets"]
        )
        self.assertEqual(
            snapshot["default_filters"], {"date": {"enabled": True}}
        )
        self.assertEqual(len(snapshot["widgets"]), 1)
        self.assertEqual(
            snapshot["widgets"][0]["title"], "Operational"
        )
        # The string name, not the integer column — the snapshot is read
        # by a client, and by validate_dashboard_payload.
        self.assertEqual(snapshot["widgets"][0]["type"], "kpi")

    def test_snapshot_orders_widgets_by_order_then_id(self):
        third = self.widget(order=3, title="Third")
        first = self.widget(order=1, title="First")
        second = self.widget(order=2, title="Second")
        snapshot = build_snapshot(self.dashboard)
        self.assertEqual(
            [w["title"] for w in snapshot["widgets"]],
            ["First", "Second", "Third"],
        )
        self.assertEqual(
            [w["id"] for w in snapshot["widgets"]],
            [first.id, second.id, third.id],
        )

    def test_a_dashboard_with_no_widgets_snapshots_empty(self):
        snapshot = build_snapshot(self.dashboard)
        self.assertEqual(snapshot["widgets"], [])
        self.assertEqual(
            snapshot["default_filters"], {"date": {"enabled": True}}
        )

    def test_snapshot_output_is_accepted_by_the_payload_validator(self):
        """Spec D-3: publish revalidates by calling PUT's validator.

        That only works because DashboardWidgetSerializer emits exactly
        the shape validate_dashboard_payload accepts. Nothing enforces
        that symmetry but this test — without it, a field rename on
        either side would surface as a 400 on a user's Publish click.
        """
        self.widget(order=1, title="A")
        self.widget(order=2, form_id=6002, question_id=600203)
        snapshot = build_snapshot(self.dashboard)
        error = validate_dashboard_payload(
            {
                "name": self.dashboard.name,
                "widgets": snapshot["widgets"],
            },
            self.user,
            dashboard=self.dashboard,
        )
        self.assertIsNone(error)


@override_settings(USE_TZ=False)
class AnnotateBrokenTestCase(TestCase, ProfileTestHelperMixin):
    """Widget health, computed against live rows at serve time."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_broken@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=Forms.objects.get(pk=6001),
            created_by=self.user,
        )

    def widgets(self, count, **overrides):
        for index in range(count):
            fields = {
                "order": index + 1,
                "type": 1,
                "col_span": 6,
                "form_id": 6001,
                "question_id": 600102,
                "config": {},
            }
            fields.update(overrides)
            self.dashboard.widgets.create(**fields)
        return build_snapshot(self.dashboard)["widgets"]

    def test_healthy_widgets_carry_is_broken_false(self):
        # False, not absent: VIZ-008 must never have to tell "healthy"
        # apart from "this API version does not annotate".
        rows = annotate_broken(self.widgets(2), self.user.tenant)
        for row in rows:
            self.assertIs(row["is_broken"], False)
            self.assertIsNone(row["broken_reason"])

    def test_only_widgets_using_the_deleted_question_are_flagged(self):
        self.widgets(2)
        self.widgets(3, form_id=6002, question_id=600203)
        rows = build_snapshot(self.dashboard)["widgets"]
        Questions.objects.get(pk=600102).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        flagged = [r for r in annotated if r["is_broken"]]
        healthy = [r for r in annotated if not r["is_broken"]]
        self.assertEqual(len(flagged), 2)
        self.assertEqual(len(healthy), 3)
        for row in flagged:
            self.assertEqual(row["broken_reason"], "question_deleted")

    def test_a_deleted_form_wins_over_its_deleted_question(self):
        # Blaming the question a deleted form took down with it would
        # send the author looking in the wrong place.
        rows = self.widgets(1, form_id=6002, question_id=600203)
        Forms.objects.get(pk=6002).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertEqual(
            annotated[0]["broken_reason"], "form_deleted"
        )

    def test_a_widget_with_no_form_or_question_is_never_broken(self):
        # section_title carries neither.
        rows = self.widgets(1, type=7, form_id=None, question_id=None)
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertIs(annotated[0]["is_broken"], False)

    def test_annotation_does_not_mutate_its_input(self):
        rows = self.widgets(1)
        annotate_broken(rows, self.user.tenant)
        self.assertNotIn("is_broken", rows[0])

    def test_query_count_does_not_grow_with_widget_count(self):
        small_rows = self.widgets(2)
        with CaptureQueriesContext(connection) as small:
            annotate_broken(small_rows, self.user.tenant)
        self.dashboard.widgets.all().delete()
        large_rows = self.widgets(12)
        with CaptureQueriesContext(connection) as large:
            annotate_broken(large_rows, self.user.tenant)
        self.assertEqual(
            len(small.captured_queries), len(large.captured_queries)
        )

    def test_annotating_by_tenant_needs_no_user(self):
        # The fixtures form_seeder builds are tenant-less, so a widget
        # referencing them would read as live under an unscoped filter
        # regardless of which axis annotate_broken checks. Give the
        # form a real tenant so this test can only pass by actually
        # filtering on it, not by coincidence. Questions.TENANT_PATH
        # is "form__tenant", so this covers the question too.
        #
        # A same-tenant widget passing is not, by itself, proof of
        # tenant filtering: deleting the `filter(**{TENANT_PATH:
        # tenant})` line in annotate_broken would leave both forms
        # live and this half of the assertion still true. Form 6002 on
        # a DIFFERENT tenant is what makes that regression fail — it
        # must read as broken precisely because it is excluded by
        # tenant, not by being deleted or missing.
        tenant = Tenant.objects.create(subdomain="viz-annotate")
        other_tenant = Tenant.objects.create(
            subdomain="viz-annotate-other"
        )
        Forms.objects.filter(pk=6001).update(tenant=tenant)
        Forms.objects.filter(pk=6002).update(tenant=other_tenant)
        widgets = [
            {"form": 6001, "question": 600102},
            {"form": 6002, "question": 600203},
        ]
        annotated = annotate_broken(widgets, tenant)
        self.assertFalse(annotated[0]["is_broken"])
        self.assertIsNone(annotated[0]["broken_reason"])
        self.assertTrue(annotated[1]["is_broken"])
        self.assertEqual(annotated[1]["broken_reason"], "form_deleted")

    # ── config.stack_question (VIZ-015) ──

    def test_a_deleted_stack_question_breaks_its_widget(self):
        # Without this the widget keeps rendering and the viewer gets a
        # 400 from /values with no explanation — the failure this
        # function exists to turn into a visible broken widget.
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={"stack_by": "option", "stack_question": 600204},
        )
        Questions.objects.get(pk=600204).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertIs(annotated[0]["is_broken"], True)
        self.assertEqual(
            annotated[0]["broken_reason"], "stack_question_deleted"
        )

    def test_a_live_stack_question_leaves_the_widget_healthy(self):
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={"stack_by": "option", "stack_question": 600204},
        )
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertIs(annotated[0]["is_broken"], False)
        self.assertIsNone(annotated[0]["broken_reason"])

    def test_the_measured_question_wins_over_the_stack_question(self):
        # Both gone: blaming the stacking question would send the
        # author to the smaller of the two problems.
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={"stack_by": "option", "stack_question": 600204},
        )
        Questions.objects.get(pk=600203).delete()
        Questions.objects.get(pk=600204).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertEqual(
            annotated[0]["broken_reason"], "question_deleted"
        )

    def test_a_deleted_form_wins_over_its_stack_question(self):
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={"stack_by": "option", "stack_question": 600204},
        )
        Forms.objects.get(pk=6002).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertEqual(annotated[0]["broken_reason"], "form_deleted")

    # ── config.stack_form (VIZ-015.a) ──

    def test_a_deleted_stack_form_breaks_its_widget(self):
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={
                "stack_by": "option",
                "group_by": "parent_id",
                "stack_form": 6001,
                "stack_question": 600102,
            },
        )
        Forms.objects.get(pk=6001).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertIs(annotated[0]["is_broken"], True)
        self.assertEqual(
            annotated[0]["broken_reason"], "stack_form_deleted"
        )

    def test_a_deleted_stack_form_wins_over_its_own_question(self):
        # Widest cause first: blaming the question a deleted form took
        # down with it sends the author to the smaller problem.
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={
                "stack_by": "option",
                "group_by": "parent_id",
                "stack_form": 6001,
                "stack_question": 600102,
            },
        )
        Questions.objects.get(pk=600102).delete()
        Forms.objects.get(pk=6001).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertEqual(
            annotated[0]["broken_reason"], "stack_form_deleted"
        )

    def test_the_widgets_own_form_still_wins_over_the_stack_form(self):
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={
                "stack_by": "option",
                "group_by": "parent_id",
                "stack_form": 6001,
                "stack_question": 600102,
            },
        )
        Forms.objects.get(pk=6002).delete()
        Forms.objects.get(pk=6001).delete()
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertEqual(annotated[0]["broken_reason"], "form_deleted")

    def test_a_live_cross_form_widget_is_not_broken(self):
        rows = self.widgets(
            1,
            type=2,
            form_id=6002,
            question_id=600203,
            config={
                "stack_by": "option",
                "group_by": "parent_id",
                "stack_form": 6001,
                "stack_question": 600102,
            },
        )
        annotated = annotate_broken(rows, self.user.tenant)
        self.assertIs(annotated[0]["is_broken"], False)
