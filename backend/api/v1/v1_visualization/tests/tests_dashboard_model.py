from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_visualization.constants import DashboardKind, WidgetTypes
from api.v1.v1_visualization.models import Dashboard, DashboardWidget


@override_settings(USE_TZ=False)
class DashboardModelTestCase(TestCase):
    def setUp(self):
        self.acme = Tenant.objects.create(subdomain="acme")
        self.beta = Tenant.objects.create(subdomain="beta")
        self.acme_user = SystemUser.objects.create_user(
            email="acme@akvo.org",
            password="Secret#Pass123",
            first_name="Ac",
            last_name="Me",
            tenant=self.acme,
        )
        self.acme_form = Forms.objects.create(
            name="Water Points",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        self.beta_form = Forms.objects.create(
            name="Beta Sites",
            type=FormTypes.registration,
            tenant=self.beta,
        )
        group = QuestionGroup.objects.create(
            form=self.acme_form, name="general"
        )
        self.question = Questions.objects.create(
            form=self.acme_form,
            question_group=group,
            name="status",
            label="Status",
            type=QuestionTypes.option,
        )

    def make_dashboard(self, tenant=None, form=None, slug="overview"):
        return Dashboard.objects.create(
            tenant=tenant or self.acme,
            root_form=form or self.acme_form,
            name="Overview",
            slug=slug,
        )

    def make_widget(self, dashboard, order=0, question=None, form=None):
        return DashboardWidget.objects.create(
            dashboard=dashboard,
            order=order,
            type=WidgetTypes.kpi,
            form=form or dashboard.root_form,
            question=question,
        )

    # ---- ordering -------------------------------------------------

    def test_widgets_order_within_a_dashboard(self):
        dashboard = self.make_dashboard()
        self.make_widget(dashboard, order=2)
        self.make_widget(dashboard, order=1)
        orders = list(
            DashboardWidget.objects.filter(
                dashboard=dashboard
            ).values_list("order", flat=True)
        )
        self.assertEqual(orders, [1, 2])

    # ---- soft delete ----------------------------------------------

    def test_soft_delete_hides_the_dashboard_but_keeps_widgets(self):
        dashboard = self.make_dashboard()
        widget = self.make_widget(dashboard)
        dashboard.soft_delete()

        self.assertFalse(Dashboard.objects.filter(pk=dashboard.pk).exists())
        self.assertTrue(
            Dashboard.objects_deleted.filter(pk=dashboard.pk).exists()
        )
        # Widgets are not soft-deleted with their dashboard; they are
        # replaced wholesale on save (VIZ-005) and cascade on hard delete.
        self.assertTrue(
            DashboardWidget.objects.filter(pk=widget.pk).exists()
        )

    def test_hard_delete_cascades_to_widgets(self):
        dashboard = self.make_dashboard()
        widget = self.make_widget(dashboard)
        dashboard.hard_delete()
        self.assertFalse(
            DashboardWidget.objects.filter(pk=widget.pk).exists()
        )

    # ---- slug constraint ------------------------------------------

    def test_duplicate_live_slug_rejected_within_tenant(self):
        self.make_dashboard(slug="overview")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_dashboard(slug="overview")

    def test_same_slug_allowed_across_tenants(self):
        self.make_dashboard(slug="overview")
        self.make_dashboard(
            tenant=self.beta, form=self.beta_form, slug="overview"
        )
        self.assertEqual(
            Dashboard.objects.filter(slug="overview").count(), 2
        )

    def test_slug_of_a_soft_deleted_dashboard_can_be_reused(self):
        first = self.make_dashboard(slug="overview")
        first.soft_delete()
        second = self.make_dashboard(slug="overview")
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Dashboard.objects.filter(slug="overview").count(), 1)

    # ---- tenant scoping -------------------------------------------

    def test_for_user_scopes_dashboards(self):
        mine = self.make_dashboard()
        self.make_dashboard(
            tenant=self.beta, form=self.beta_form, slug="beta-overview"
        )
        visible = Dashboard.objects.for_user(self.acme_user)
        self.assertEqual(list(visible), [mine])

    def test_for_user_scopes_widgets_through_the_derived_path(self):
        mine = self.make_widget(self.make_dashboard())
        self.make_widget(
            self.make_dashboard(
                tenant=self.beta, form=self.beta_form, slug="beta-overview"
            )
        )
        visible = DashboardWidget.objects.for_user(self.acme_user)
        self.assertEqual(list(visible), [mine])

    # ---- foreign keys ---------------------------------------------

    def test_root_form_is_protected_against_hard_delete(self):
        self.make_dashboard()
        # Forms inherits SoftDeletes, so a plain delete() only stamps
        # deleted_at and never reaches the database's referential check.
        # Only a hard delete can trip PROTECT.
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.acme_form.hard_delete()

    def test_widget_form_is_protected_against_hard_delete(self):
        # The widget's form must be a *different* Forms row from the
        # dashboard's root_form: Dashboard.root_form is itself PROTECT,
        # and Django's deletion Collector raises ProtectedError as soon
        # as it finds any protected relation, regardless of which one.
        # Pointing the widget at root_form would let root_form's PROTECT
        # mask DashboardWidget.form's own, making the test pass even if
        # the widget's PROTECT were loosened. Use a monitoring form
        # (parent=root_form) instead, so only the widget's FK is tripped.
        monitoring_form = Forms.objects.create(
            name="Water Points Monitoring",
            type=FormTypes.monitoring,
            parent=self.acme_form,
            tenant=self.acme,
        )
        self.make_widget(self.make_dashboard(), form=monitoring_form)
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                monitoring_form.hard_delete()

    def test_question_is_protected_against_hard_delete(self):
        self.make_widget(self.make_dashboard(), question=self.question)
        # Same reasoning as test_root_form_is_protected_against_hard_delete:
        # only a hard delete reaches the database's referential check.
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.question.hard_delete()

    def test_soft_deleting_a_question_leaves_the_widget_intact(self):
        widget = self.make_widget(
            self.make_dashboard(), question=self.question
        )
        self.question.soft_delete()

        widget.refresh_from_db()
        self.assertEqual(widget.question_id, self.question.pk)
        # This is what VIZ-007's broken-widget annotation depends on:
        # the row survives and the reason is discoverable through the FK.
        self.assertIsNotNone(
            Questions.objects_deleted.get(pk=self.question.pk).deleted_at
        )

    def test_a_new_dashboard_is_private(self):
        dashboard = Dashboard.objects.create(
            name="Coverage",
            slug="coverage",
            root_form=self.acme_form,
        )
        self.assertFalse(dashboard.is_public)


class DashboardKindConstraintTestCase(TestCase):
    """`dashboard_kind_matches_source` — spec D-2.

    The constraint is in the database rather than only in
    validate_dashboard_payload because the validator guards one path:
    duplicate() writes rows without it, and so does a shell session.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.root = Forms.objects.get(pk=6001)

    def create(self, **kwargs):
        fields = {"name": "D", "slug": "d"}
        fields.update(kwargs)
        with transaction.atomic():
            return Dashboard.objects.create(**fields)

    def test_a_widgets_dashboard_needs_a_root_form(self):
        with self.assertRaises(IntegrityError):
            self.create(kind=DashboardKind.widgets, root_form=None)

    def test_a_widgets_dashboard_may_not_carry_a_snippet(self):
        with self.assertRaises(IntegrityError):
            self.create(
                kind=DashboardKind.widgets,
                root_form=self.root,
                embed_snippet="<iframe src='https://x/'></iframe>",
            )

    def test_an_embed_may_not_carry_a_root_form(self):
        with self.assertRaises(IntegrityError):
            self.create(
                kind=DashboardKind.embed,
                root_form=self.root,
                embed_snippet="<iframe src='https://x/'></iframe>",
            )

    def test_an_embed_needs_a_snippet(self):
        with self.assertRaises(IntegrityError):
            self.create(
                kind=DashboardKind.embed,
                root_form=None,
                embed_snippet=None,
            )

    def test_an_embed_may_not_carry_an_empty_snippet(self):
        # TextField accepts '' happily, and an embed holding one renders
        # as an empty frame with nothing wrong in any log. NOT NULL
        # alone does not exclude it.
        with self.assertRaises(IntegrityError):
            self.create(
                kind=DashboardKind.embed,
                root_form=None,
                embed_snippet="",
            )

    def test_both_valid_arms_are_writable(self):
        widgets = self.create(
            slug="w", kind=DashboardKind.widgets, root_form=self.root
        )
        embed = self.create(
            slug="e",
            kind=DashboardKind.embed,
            root_form=None,
            embed_snippet="<iframe src='https://x/'></iframe>",
        )
        self.assertEqual(widgets.kind, DashboardKind.widgets)
        self.assertEqual(embed.kind, DashboardKind.embed)

    def test_kind_defaults_to_widgets(self):
        self.assertEqual(
            self.create(root_form=self.root).kind, DashboardKind.widgets
        )
