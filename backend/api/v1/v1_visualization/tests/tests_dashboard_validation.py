from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_visualization.constants import (
    DashboardKind,
    EMBED_SNIPPET_MAX,
)
from api.v1.v1_visualization.dashboard_functions import (
    SLUG_PATTERN,
    validate_dashboard_payload,
)
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False)
class DashboardValidationTestCase(TestCase, ProfileTestHelperMixin):
    """Every VIZ-001 §4.5 rule, asserted through the validator.

    These are function-level tests on purpose: the rules are the
    product of this slice and they are far cheaper to pin down here
    than through 30 HTTP round trips. The view's job — turning the
    returned dict into a 400 — is covered once, in the CRUD tests.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_validation@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.root = Forms.objects.get(pk=6001)
        self.monitoring = Forms.objects.get(pk=6002)
        self.q_option = Questions.objects.get(pk=600203)
        self.q_text = Questions.objects.get(pk=600205)
        self.q_reg_option = Questions.objects.get(pk=600102)

        # A second family, so "outside the family" has something to
        # point at that is still inside the tenant.
        self.other_root = Forms.objects.create(
            name="Other registration",
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        self.other_monitoring = Forms.objects.create(
            name="Other monitoring",
            type=FormTypes.monitoring,
            parent=self.other_root,
            status=FormStatus.published,
        )

        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            created_by=self.user,
        )

    # ── helpers ──

    def widget(self, **overrides):
        payload = {
            "id": None,
            "order": 1,
            "type": "kpi",
            "col_span": 6,
            "title": "Operational",
            "color": "#64A73B",
            "form": self.monitoring.id,
            "question": self.q_option.id,
            "config": {"measure": "current_state"},
        }
        payload.update(overrides)
        return payload

    def check(self, *widgets, **kwargs):
        data = {
            "name": kwargs.get("name", "Water Points"),
            "widgets": list(widgets),
        }
        if "root_form" in kwargs:
            data["root_form"] = kwargs["root_form"]
        return validate_dashboard_payload(
            data, self.user, dashboard=kwargs.get(
                "dashboard", self.dashboard
            )
        )

    # ── the happy path, so every failing test below means something ──

    def test_a_valid_widget_returns_none(self):
        self.assertIsNone(self.check(self.widget()))

    # ── §4.5: root_form ──

    def test_root_form_must_be_a_registration_form(self):
        err = validate_dashboard_payload(
            {"name": "X", "root_form": self.monitoring.id, "widgets": []},
            self.user,
        )
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "root_form")
        self.assertNotIn("widget_index", err)

    def test_root_form_must_have_no_parent(self):
        child = Forms.objects.create(
            name="Registration with a parent",
            type=FormTypes.registration,
            parent=self.root,
            status=FormStatus.published,
        )
        err = validate_dashboard_payload(
            {"name": "X", "root_form": child.id, "widgets": []},
            self.user,
        )
        self.assertEqual(err["field"], "root_form")

    def test_root_form_is_immutable_after_create(self):
        err = self.check(root_form=self.other_root.id)
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "root_form")
        # Dashboard-level failures carry no index: the builder shows a
        # global message rather than highlighting a widget.
        self.assertNotIn("widget_index", err)

    def test_resending_the_same_root_form_on_update_is_fine(self):
        self.assertIsNone(self.check(root_form=self.root.id))

    # ── §4.5: the family rule, all four cases ──

    def test_widget_on_the_root_form_is_allowed(self):
        self.assertIsNone(
            self.check(
                self.widget(
                    form=self.root.id,
                    question=self.q_reg_option.id,
                    config={},
                )
            )
        )

    def test_widget_on_a_monitoring_child_is_allowed(self):
        self.assertIsNone(self.check(self.widget()))

    def test_widget_on_a_monitoring_form_of_another_parent_is_rejected(
        self,
    ):
        err = self.check(
            self.widget(form=self.other_monitoring.id, question=None)
        )
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "form")

    def test_widget_on_an_unrelated_registration_form_is_rejected(self):
        err = self.check(
            self.widget(form=self.other_root.id, question=None)
        )
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "form")

    def test_the_offending_index_is_the_widget_index_not_the_first(self):
        # The builder highlights widgets[widget_index]; an off-by-one
        # here points the user at an innocent widget.
        err = self.check(
            self.widget(),
            self.widget(),
            self.widget(form=self.other_root.id, question=None),
        )
        self.assertEqual(err["widget_index"], 2)

    # ── §4.5: question ──

    def test_question_must_belong_to_the_widget_form(self):
        err = self.check(
            self.widget(
                form=self.monitoring.id, question=self.q_reg_option.id
            )
        )
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "question")

    def test_question_type_must_be_aggregatable(self):
        err = self.check(self.widget(question=self.q_text.id))
        self.assertEqual(err["field"], "question")

    # ── §4.5: measure, stack_by, col_span ──

    def test_current_state_requires_a_monitoring_form(self):
        err = self.check(
            self.widget(
                form=self.root.id,
                question=self.q_reg_option.id,
                config={"measure": "current_state"},
            )
        )
        self.assertEqual(err["field"], "config.measure")

    def test_an_unknown_measure_is_rejected(self):
        err = self.check(self.widget(config={"measure": "whatever"}))
        self.assertEqual(err["field"], "config.measure")

    def test_stack_by_requires_group_by_and_question(self):
        err = self.check(
            self.widget(
                type="bar",
                config={"measure": "current_state", "stack_by": "option"},
            )
        )
        self.assertEqual(err["field"], "config.stack_by")

    def test_stack_by_with_group_by_and_question_is_allowed(self):
        self.assertIsNone(
            self.check(
                self.widget(
                    type="bar",
                    config={
                        "measure": "current_state",
                        "group_by": "option",
                        "stack_by": "option",
                    },
                )
            )
        )

    def test_col_span_out_of_range_is_rejected(self):
        for bad in (0, 25, -1):
            err = self.check(self.widget(col_span=bad))
            self.assertEqual(err["field"], "col_span", bad)

    def test_an_unknown_widget_type_is_rejected(self):
        err = self.check(self.widget(type="sparkline"))
        self.assertEqual(err["field"], "type")

    # ── config vocabularies (spec D-5) ──

    def test_group_by_outside_the_shared_vocabulary_is_rejected(self):
        # "administration" reads plausibly and is not a group_by the
        # values endpoint knows. Saving it would 400 at render time.
        err = self.check(
            self.widget(
                type="bar",
                config={
                    "measure": "current_state",
                    "group_by": "administration",
                },
            )
        )
        self.assertEqual(err["field"], "config.group_by")

    def test_value_type_and_repeat_agg_are_checked(self):
        err = self.check(self.widget(config={"value_type": "ratio"}))
        self.assertEqual(err["field"], "config.value_type")
        err = self.check(self.widget(config={"repeat_agg": "median"}))
        self.assertEqual(err["field"], "config.repeat_agg")

    def test_table_column_sources_and_criteria_types_are_checked(self):
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={"columns": [{"key": "a", "source": "magic"}]},
            )
        )
        self.assertEqual(err["field"], "config.columns")
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={
                    "criteria": [{"type": "vibes", "question": 1}],
                },
            )
        )
        self.assertEqual(err["field"], "config.criteria")

    def test_unknown_config_keys_are_left_alone(self):
        # VIZ-008 owns config expansion; this slice must not become a
        # schema language.
        self.assertIsNone(
            self.check(
                self.widget(
                    config={
                        "measure": "current_state",
                        "something_viz_008_adds": True,
                    }
                )
            )
        )

    # ── widget ids ──

    def test_a_widget_id_from_another_dashboard_is_rejected(self):
        other = Dashboard.objects.create(
            name="Other", slug="other", root_form=self.root,
        )
        stolen = other.widgets.create(
            order=1, type=1, col_span=6, config={},
        )
        err = self.check(self.widget(id=stolen.id))
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "id")

    def test_two_widgets_sharing_one_id_are_rejected(self):
        # Not reachable from today's builder, but VIZ-007's "duplicate
        # dashboard" is exactly the feature that would introduce it:
        # both ids are live, so nothing else here would catch it, and
        # apply_widgets would silently collapse the pair to one row.
        live = self.dashboard.widgets.create(
            order=1, type=1, col_span=6, config={}
        )
        err = self.check(
            self.widget(id=live.id), self.widget(id=live.id)
        )
        self.assertEqual(err["widget_index"], 1)
        self.assertEqual(err["field"], "id")

    # ── F1: shapes and lengths, so ordinary input 400s instead of
    # raising ──

    def test_a_non_dict_payload_is_rejected(self):
        err = validate_dashboard_payload(["not", "a", "dict"], self.user)
        self.assertIsNotNone(err)
        self.assertNotIn("widget_index", err)

    def test_a_numeric_name_is_rejected(self):
        err = self.check(self.widget(), name=12345)
        self.assertEqual(err["field"], "name")

    def test_a_300_character_name_is_rejected(self):
        err = self.check(self.widget(), name="A" * 300)
        self.assertEqual(err["field"], "name")

    def test_a_non_string_description_is_rejected(self):
        err = validate_dashboard_payload(
            {"name": "X", "description": 123, "widgets": []},
            self.user,
            dashboard=self.dashboard,
        )
        self.assertEqual(err["field"], "description")

    def test_widgets_that_is_not_a_list_is_rejected(self):
        err = validate_dashboard_payload(
            {"name": "X", "widgets": "not-a-list"},
            self.user,
            dashboard=self.dashboard,
        )
        self.assertIsNotNone(err)
        self.assertNotIn("widget_index", err)

    def test_a_non_dict_widget_is_rejected(self):
        err = self.check("not-a-widget")
        self.assertEqual(err["widget_index"], 0)

    def test_a_non_dict_config_is_rejected(self):
        err = self.check(self.widget(config=["measure"]))
        self.assertEqual(err["field"], "config")

    def test_a_title_over_255_characters_is_rejected(self):
        err = self.check(self.widget(title="A" * 256))
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "title")

    def test_a_color_over_32_characters_is_rejected(self):
        err = self.check(self.widget(color="A" * 33))
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "color")

    def test_a_null_order_is_rejected(self):
        # The column is NOT NULL; apply_widgets only defaults `order`
        # when the key is absent, not when it is explicitly null.
        err = self.check(self.widget(order=None))
        self.assertEqual(err["field"], "order")

    def test_columns_that_is_not_a_list_is_rejected(self):
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={"columns": {"a": 1}},
            )
        )
        self.assertEqual(err["field"], "config.columns")

    def test_a_criteria_entry_that_is_not_a_dict_is_rejected(self):
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={"criteria": ["not-a-dict"]},
            )
        )
        self.assertEqual(err["field"], "config.criteria")

    def test_slug_pattern_rejects_a_trailing_newline(self):
        # $ (without re.MULTILINE) matches just before a trailing "\n",
        # so the naive pattern would accept "water-points\n" and let it
        # through to storage with an embedded newline no URL can reach.
        self.assertIsNone(SLUG_PATTERN.match("water-points\n"))

    # ── F9: section_title is the one widget type with no form/question
    # ──

    def test_a_section_title_widget_with_no_form_or_question_is_valid(
        self,
    ):
        self.assertIsNone(
            self.check(
                self.widget(
                    type="section_title",
                    form=None,
                    question=None,
                    config={},
                )
            )
        )


SNIPPET = (
    "<script type=\"module\" "
    "src=\"https://public.tableau.com/javascripts/api/"
    "tableau.embedding.3.latest.min.js\"></script>\n"
    "<tableau-viz id='tableauViz' "
    "src='https://public.tableau.com/views/Superstore/Overview' "
    "toolbar=\"bottom\" hide-tabs></tableau-viz>"
)


class EmbedValidationTestCase(TestCase, ProfileTestHelperMixin):
    """The embed arm of validate_dashboard_payload (spec D-3, D-4)."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_embed_validation@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.root = Forms.objects.get(pk=6001)

    def check(self, data, dashboard=None):
        return validate_dashboard_payload(data, self.user, dashboard)

    # ── the snippet is stored verbatim, never inspected ──

    def test_a_snippet_with_a_script_tag_is_accepted(self):
        # Spec D-4: content is never inspected. A <script> tag, single
        # quotes and a custom element are all ordinary input here.
        self.assertIsNone(
            self.check(
                {"name": "Sales", "kind": "embed", "embed_snippet": SNIPPET}
            )
        )

    def test_a_javascript_url_in_the_snippet_is_accepted(self):
        # Deliberately not refused. We never build an element from an
        # author-supplied URL, and anything inside the snippet runs in
        # the opaque origin of the srcdoc sandbox (D-4a/D-4b). The
        # sandbox is the boundary, not a validator.
        self.assertIsNone(
            self.check(
                {
                    "name": "Odd",
                    "kind": "embed",
                    "embed_snippet": "<a href='javascript:alert(1)'>x</a>",
                }
            )
        )

    # ── the only two bounds ──

    def test_a_missing_snippet_is_refused(self):
        error = self.check({"name": "Sales", "kind": "embed"})
        self.assertEqual(error["field"], "embed_snippet")

    def test_a_blank_snippet_is_refused(self):
        error = self.check(
            {"name": "Sales", "kind": "embed", "embed_snippet": "   "}
        )
        self.assertEqual(error["field"], "embed_snippet")

    def test_a_non_string_snippet_is_refused(self):
        error = self.check(
            {"name": "Sales", "kind": "embed", "embed_snippet": 12}
        )
        self.assertEqual(error["field"], "embed_snippet")

    def test_an_oversized_snippet_is_refused(self):
        error = self.check(
            {
                "name": "Sales",
                "kind": "embed",
                "embed_snippet": "x" * (EMBED_SNIPPET_MAX + 1),
            }
        )
        self.assertEqual(error["field"], "embed_snippet")

    def test_a_snippet_at_the_limit_is_accepted(self):
        self.assertIsNone(
            self.check(
                {
                    "name": "Sales",
                    "kind": "embed",
                    "embed_snippet": "x" * EMBED_SNIPPET_MAX,
                }
            )
        )

    # ── an embed has no forms and no widgets ──

    def test_an_embed_with_a_root_form_is_refused(self):
        error = self.check(
            {
                "name": "Sales",
                "kind": "embed",
                "embed_snippet": SNIPPET,
                "root_form": self.root.id,
            }
        )
        self.assertEqual(error["field"], "root_form")

    def test_an_embed_with_widgets_is_refused(self):
        error = self.check(
            {
                "name": "Sales",
                "kind": "embed",
                "embed_snippet": SNIPPET,
                "widgets": [{"type": "kpi"}],
            }
        )
        self.assertEqual(error["field"], "widgets")

    # ── kind ──

    def test_an_unknown_kind_is_refused(self):
        error = self.check({"name": "Sales", "kind": "spreadsheet"})
        self.assertEqual(error["field"], "kind")

    def test_a_non_string_kind_is_refused_rather_than_crashing(self):
        # A list is unhashable, so an unguarded `raw not in KIND_IDS`
        # raises TypeError and the request 500s. Ordinary bad input has
        # to come back as the same 400 shape as any other bad field.
        for raw in ([], {}, 7):
            error = self.check({"name": "Sales", "kind": raw})
            self.assertEqual(error["field"], "kind", raw)

    def test_kind_defaults_to_widgets_when_absent(self):
        # The widgets arm still demands a root_form, which is how we
        # know the default was applied rather than the embed arm taken.
        error = self.check({"name": "Sales"})
        self.assertEqual(error["field"], "root_form")

    def test_kind_cannot_be_changed_on_update(self):
        dashboard = Dashboard.objects.create(
            name="Sales",
            slug="sales",
            kind=DashboardKind.embed,
            root_form=None,
            embed_snippet=SNIPPET,
        )
        error = self.check(
            {"name": "Sales", "kind": "widgets"}, dashboard=dashboard
        )
        self.assertEqual(error["field"], "kind")

    def test_an_update_omitting_the_snippet_keeps_the_stored_one(self):
        dashboard = Dashboard.objects.create(
            name="Sales",
            slug="sales-2",
            kind=DashboardKind.embed,
            root_form=None,
            embed_snippet=SNIPPET,
        )
        self.assertIsNone(
            self.check({"name": "Renamed"}, dashboard=dashboard)
        )

    def test_the_widgets_arm_is_unchanged(self):
        self.assertIsNone(
            self.check({"name": "Sales", "root_form": self.root.id})
        )
