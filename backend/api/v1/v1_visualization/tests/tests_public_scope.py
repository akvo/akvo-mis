from django.http import Http404
from django.test import TestCase, RequestFactory
from django.test.utils import override_settings
from rest_framework.request import Request

from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
)
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.public_scope import (
    ALLOW_ANY,
    Allowlist,
    allowlist_from,
    check_ids,
    question_ids_in_columns,
    question_ids_in_criteria,
    question_ids_in_formula,
    resolve_view_scope,
)
from utils.tenant_host import public_tenant


class PublicTenantTestCase(TestCase):
    """Which workspace an anonymous reader is looking at (spec D-4)."""

    def setUp(self):
        self.factory = RequestFactory()
        # Migration 0004_backfill_default_tenant seeds a "default"
        # Tenant row via a data migration, which Django applies to the
        # test database same as any schema migration. Start each test
        # from a known-empty table rather than let that row leak in.
        Tenant.objects.all().delete()

    def anon_request(self, tenant=None):
        request = self.factory.get("/api/v1/dashboards")
        request.tenant = tenant
        return request

    @override_settings(BASE_DOMAIN="app.com")
    def test_the_host_names_the_workspace(self):
        tenant = Tenant.objects.create(subdomain="acme")
        self.assertEqual(public_tenant(self.anon_request(tenant)), tenant)

    @override_settings(BASE_DOMAIN="app.com")
    def test_the_base_domain_names_none(self):
        Tenant.objects.create(subdomain="acme")
        self.assertIsNone(public_tenant(self.anon_request(None)))

    @override_settings(BASE_DOMAIN="")
    def test_single_host_resolves_the_sole_tenant(self):
        tenant = Tenant.objects.create(subdomain="default")
        self.assertEqual(public_tenant(self.anon_request(None)), tenant)

    @override_settings(BASE_DOMAIN="")
    def test_single_host_with_two_tenants_serves_nothing(self):
        Tenant.objects.create(subdomain="one")
        Tenant.objects.create(subdomain="two")
        self.assertIsNone(public_tenant(self.anon_request(None)))

    @override_settings(BASE_DOMAIN="")
    def test_single_host_with_no_tenants_serves_nothing(self):
        self.assertIsNone(public_tenant(self.anon_request(None)))


class AllowlistTestCase(TestCase):
    """The published snapshot is the allowlist (spec D-5)."""

    def build(self, widgets, default_filters=None):
        class FakeDashboard:
            # These cases are all about the widgets branch, so the
            # stub has to say so: allowlist_from returns the empty
            # allowlist for an embed before it reads any of this.
            kind = DashboardKind.widgets
            root_form_id = 6001
            published_config = {
                "default_filters": default_filters or {},
                "widgets": widgets,
            }
        return allowlist_from(FakeDashboard())

    def test_the_root_form_is_always_allowed(self):
        allowed = self.build([])
        self.assertEqual(allowed.forms, {6001})
        self.assertEqual(allowed.questions, set())

    def test_a_widget_contributes_its_form_and_question(self):
        allowed = self.build([
            {"form": 6002, "question": 600201, "config": {}},
        ])
        self.assertEqual(allowed.forms, {6001, 6002})
        self.assertEqual(allowed.questions, {600201})

    def test_criteria_question_ids_are_collected(self):
        allowed = self.build([
            {"form": 6001, "question": None, "config": {
                "criteria": [
                    {"type": "option_equals", "question": 600105,
                     "value": "Yes"},
                ],
            }},
        ])
        self.assertEqual(allowed.questions, {600105})

    def test_table_column_question_ids_are_collected(self):
        allowed = self.build([
            {"form": 6002, "question": None, "config": {
                "columns": [
                    {"key": "a", "source": "parent_name"},
                    {"key": "b", "source": "answer", "question": 600203},
                    {"key": "c", "source": "latest_date",
                     "question": 600204},
                ],
            }},
        ])
        self.assertEqual(allowed.questions, {600203, 600204})

    def test_the_date_filter_question_is_collected(self):
        allowed = self.build(
            [], default_filters={"date": {"date_question": 600106}}
        )
        self.assertEqual(allowed.questions, {600106})

    def test_nulls_and_a_missing_config_do_not_crash(self):
        allowed = self.build([
            {"form": None, "question": None, "config": None},
            {"form": 6002},
        ])
        self.assertEqual(allowed.forms, {6001, 6002})
        self.assertEqual(allowed.questions, set())

    def test_allow_any_restricts_nothing(self):
        self.assertIsNone(ALLOW_ANY.forms)
        self.assertIsNone(ALLOW_ANY.questions)

    def test_allow_any_permits_any_id(self):
        # The authenticated path. An inversion here breaks every
        # signed-in user's dashboard while the other tests stay green.
        self.assertTrue(ALLOW_ANY.permits_form(9999))
        self.assertTrue(ALLOW_ANY.permits_question(9999))

    def test_a_restricted_allowlist_permits_only_its_own_ids(self):
        allowed = self.build([
            {"form": 6002, "question": 600201, "config": {}},
        ])
        self.assertTrue(allowed.permits_form(6001))
        self.assertTrue(allowed.permits_form(6002))
        self.assertFalse(allowed.permits_form(9999))
        self.assertTrue(allowed.permits_question(600201))
        self.assertFalse(allowed.permits_question(9999))

    def test_ids_compare_across_string_and_int(self):
        # check_ids (Task 6) passes values straight off the query
        # string, where every id is a string.
        allowed = self.build([
            {"form": 6002, "question": 600201, "config": {}},
        ])
        self.assertTrue(allowed.permits_form("6002"))
        self.assertFalse(allowed.permits_form("9999"))

    def test_unparseable_form_ids_are_refused_not_raised(self):
        # Fix round 1: geolocation passes monitoring_form_id straight
        # off the query string with no int() upstream, so "abc", ""
        # and None must all be refused as ids rather than blow up
        # int() and 500 a public page.
        allowed = self.build([
            {"form": 6002, "question": 600201, "config": {}},
        ])
        self.assertFalse(allowed.permits_form("abc"))
        self.assertFalse(allowed.permits_form(""))
        self.assertFalse(allowed.permits_form(None))
        self.assertTrue(ALLOW_ANY.permits_form("abc"))
        self.assertTrue(ALLOW_ANY.permits_form(""))
        self.assertTrue(ALLOW_ANY.permits_form(None))

    def test_unparseable_question_ids_are_refused_not_raised(self):
        allowed = self.build([
            {"form": 6002, "question": 600201, "config": {}},
        ])
        self.assertFalse(allowed.permits_question("abc"))
        self.assertFalse(allowed.permits_question(""))
        self.assertFalse(allowed.permits_question(None))
        self.assertTrue(ALLOW_ANY.permits_question("abc"))
        self.assertTrue(ALLOW_ANY.permits_question(""))
        self.assertTrue(ALLOW_ANY.permits_question(None))

    def test_a_non_numeric_criterion_question_is_dropped_not_raised(self):
        # allowlist_from itself calls int() while building the
        # allowlist. validate_dashboard_payload never checks that a
        # criterion's question is numeric, so a saved, published
        # widget can carry a garbage one -- it must narrow the
        # allowlist, not 500 every public view of the dashboard.
        allowed = self.build([
            {"form": 6002, "question": None, "config": {
                "criteria": [
                    {"type": "option_equals", "question": "abc",
                     "value": "Yes"},
                ],
            }},
        ])
        self.assertEqual(allowed.questions, set())


class IdExtractionTestCase(TestCase):
    """Question ids hide inside three different grammars (spec D-6)."""

    def test_criteria_grammar(self):
        self.assertEqual(
            question_ids_in_criteria(
                "option_equals:600105:Yes,threshold_gt:600107:3"
            ),
            [600105, 600107],
        )

    def test_overdue_criterion_names_two_questions(self):
        self.assertEqual(
            question_ids_in_criteria("overdue:600108:600109"),
            [600108, 600109],
        )

    def test_columns_grammar_skips_sources_with_no_question(self):
        self.assertEqual(
            question_ids_in_columns(
                "a:parent_name,b:answer:600203,c:latest_date:600204"
            ),
            [600203, 600204],
        )

    def test_formula_buckets(self):
        formula = (
            '{"buckets": [{"value": "Yes", "label": "Yes", "all_of": '
            '[{"question_id": 600105, "op": "option_equals", '
            '"value": "Yes"}]}], "default": {"value": "_no_info"}}'
        )
        self.assertEqual(question_ids_in_formula(formula), [600105])

    def test_garbage_yields_no_ids_rather_than_raising(self):
        # A malformed string is the serializer's 400 to give, not this
        # module's crash. Yielding nothing means nothing is smuggled.
        self.assertEqual(question_ids_in_criteria("nonsense"), [])
        self.assertEqual(question_ids_in_columns(""), [])
        self.assertEqual(question_ids_in_formula("{"), [])

    def test_whitespace_cannot_desync_the_criteria_grammar(self):
        # Downstream parsers strip before splitting. If this one does
        # not, " overdue" fails the type test and the deadline question
        # id is never checked while parse_criteria_string still uses it.
        self.assertEqual(
            question_ids_in_criteria("a:1:x, overdue:2:3"),
            [1, 2, 3],
        )

    def test_whitespace_cannot_desync_the_columns_grammar(self):
        self.assertEqual(
            question_ids_in_columns("a:parent_name, b:answer:600203"),
            [600203],
        )


class CheckIdsTestCase(TestCase):
    def setUp(self):
        self.allowed = Allowlist(forms={6001}, questions={600101})

    def test_permitted_ids_pass(self):
        check_ids(self.allowed, form_ids=[6001], question_ids=[600101])

    def test_a_foreign_form_is_404(self):
        with self.assertRaises(Http404):
            check_ids(self.allowed, form_ids=[6002])

    def test_a_foreign_question_is_404(self):
        with self.assertRaises(Http404):
            check_ids(self.allowed, question_ids=[600999])

    def test_nones_are_skipped(self):
        check_ids(self.allowed, form_ids=[None], question_ids=[None])

    def test_allow_any_permits_everything(self):
        check_ids(ALLOW_ANY, form_ids=[999], question_ids=[999])


class ResolveViewScopeTestCase(TestCase):
    """The anonymous path of `resolve_view_scope` (spec D-4/D-5)."""

    def setUp(self):
        self.factory = RequestFactory()
        # Same reasoning as PublicTenantTestCase: start from a known-
        # empty table rather than let the seeded "default" Tenant leak
        # in and turn "single tenant" into "two tenants, serve none".
        Tenant.objects.all().delete()

    def anon_request(self, slug):
        django_request = self.factory.get(
            "/api/v1/visualization/values", {"dashboard_slug": slug}
        )
        # No authenticators are attached, so DRF's Request resolves
        # `.user` to AnonymousUser on its own — exactly the caller
        # resolve_view_scope's anonymous branch must handle.
        return Request(django_request)

    @override_settings(BASE_DOMAIN="")
    def test_a_published_private_dashboard_is_not_publicly_resolvable(self):
        # The is_public filter is what keeps an internal dashboard off
        # the public web. Nothing else in the suite covers it.
        tenant = Tenant.objects.create(subdomain="acme")
        form = Forms.objects.create(name="Water Points", tenant=tenant)
        Dashboard.objects.create(
            name="Internal",
            slug="internal",
            root_form=form,
            tenant=tenant,
            status=DashboardStatus.published,
            is_public=False,
        )
        with self.assertRaises(Http404):
            resolve_view_scope(self.anon_request("internal"))
