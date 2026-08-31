from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_visualization.constants import WidgetTypes
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
