from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_visualization.dashboard_widget_data import (
    resolve_widget_data,
)
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ResolveWidgetDataTestCase(
    VisualizationValuesTestMixin, APITestCase
):
    """The resolver answers exactly what /visualization/* answers.

    This is the property the whole design rests on (VIZ-010 D-3/D-4): the
    public path reads a widget the server already holds instead of taking
    a `form_id` from the wire, and the authenticated viewer moves to the
    same resolver. If the two ever disagreed, a dashboard would show one
    number to a colleague and another to the public, and neither would
    look wrong.
    """

    def setUp(self):
        super().setUp()
        self.dashboard = Dashboard.objects.create(
            name="Water points",
            slug="water-points",
            root_form=self.registration,
        )

    def widget(self, **overrides):
        base = {
            "id": 1,
            "type": "bar",
            "form": self.MONITORING_FORM_ID,
            "question": self.Q_OPTION_ID,
            "config": {"measure": "current_state", "group_by": "option"},
        }
        base.update(overrides)
        return base

    def endpoint(self, params):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.BASE_URL, params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    # ── parity with the endpoint it replaces ─────────────────────────

    def test_an_option_chart_matches_the_endpoint(self):
        widget = self.widget()
        self.assertEqual(
            resolve_widget_data(self.dashboard, widget),
            self.endpoint(
                {
                    "form_id": self.MONITORING_FORM_ID,
                    "question_id": self.Q_OPTION_ID,
                    "group_by": "option",
                    "monitoring": "latest",
                    "sum_by": "parent_id",
                }
            ),
        )

    def test_a_number_chart_matches_the_endpoint(self):
        widget = self.widget(
            question=self.Q_NUMBER_ID,
            config={
                "measure": "all_submissions",
                "group_by": "month",
                "repeat_agg": "sum",
            },
        )
        self.assertEqual(
            resolve_widget_data(self.dashboard, widget),
            self.endpoint(
                {
                    "form_id": self.MONITORING_FORM_ID,
                    "question_id": self.Q_NUMBER_ID,
                    "group_by": "month",
                    "repeat_agg": "sum",
                    "monitoring": "all",
                }
            ),
        )

    def test_a_count_only_kpi_matches_the_endpoint(self):
        widget = self.widget(type="kpi", question=None, config={})
        self.assertEqual(
            resolve_widget_data(self.dashboard, widget),
            self.endpoint(
                {
                    "form_id": self.MONITORING_FORM_ID,
                    "monitoring": "latest",
                }
            ),
        )

    # ── the measure reaches the aggregation ──────────────────────────

    def test_current_state_and_all_submissions_differ(self):
        """The distinction the expansion exists to protect.

        current_state counts sites; all_submissions counts submissions.
        The fixture has 2 registrations and 4 monitoring records, so if
        these ever come out equal the expansion has stopped reaching the
        aggregation.
        """
        current = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="kpi",
                question=None,
                config={"measure": "current_state"},
            ),
        )
        every = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="kpi",
                question=None,
                config={"measure": "all_submissions"},
            ),
        )
        self.assertNotEqual(current["data"], every["data"])

    # ── widgets that ask for nothing ─────────────────────────────────

    def test_a_section_title_resolves_to_nothing(self):
        self.assertIsNone(
            resolve_widget_data(
                self.dashboard,
                self.widget(type="section_title", config={"text": "Hi"}),
            )
        )

    def test_a_broken_widget_resolves_to_nothing(self):
        self.assertIsNone(
            resolve_widget_data(
                self.dashboard, self.widget(is_broken=True)
            )
        )

    def test_a_chart_with_no_form_resolves_to_nothing(self):
        self.assertIsNone(
            resolve_widget_data(self.dashboard, self.widget(form=None))
        )

    # ── table ────────────────────────────────────────────────────────

    def test_a_table_returns_the_escalation_page(self):
        result = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="table",
                question=None,
                config={
                    "columns": [
                        {"key": "site", "source": "parent_name"},
                    ],
                    "criteria": [],
                    "page_size": 1,
                },
            ),
        )
        # Criteria are optional (VIZ-009): no conditions is every
        # datapoint, paged.
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["results"]), 1)

    def test_a_table_with_no_usable_column_asks_for_nothing(self):
        result = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="table",
                question=None,
                # latest_date without a question id is dropped, exactly as
                # the frontend serializer drops it.
                config={
                    "columns": [
                        {"key": "d", "source": "latest_date"},
                    ]
                },
            ),
        )
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["results"], [])

    def test_a_table_pages(self):
        first = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="table",
                question=None,
                config={
                    "columns": [{"key": "site", "source": "parent_name"}],
                    "page_size": 1,
                },
            ),
            {"page": 2},
        )
        self.assertEqual(first["count"], 2)

    # ── map ──────────────────────────────────────────────────────────

    def test_a_map_returns_registration_points(self):
        points = resolve_widget_data(
            self.dashboard,
            self.widget(type="map", question=self.Q_OPTION_ID, config={}),
        )
        self.assertTrue(points)
        for point in points:
            self.assertIn("geo", point)
            self.assertIn("name", point)

    def test_a_map_reads_the_registration_form_not_the_widgets(self):
        """`geo` is captured once, at registration.

        A monitoring form carries none, so sourcing the widget's own form
        would return an empty list every time.
        """
        on_monitoring = resolve_widget_data(
            self.dashboard,
            self.widget(type="map", config={}),
        )
        on_registration = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="map", form=self.REGISTRATION_FORM_ID, config={}
            ),
        )
        self.assertEqual(
            [p["id"] for p in on_monitoring],
            [p["id"] for p in on_registration],
        )

    # ── only dashboard-level filters are honoured ────────────────────

    def test_a_caller_cannot_smuggle_a_form_id(self):
        """Everything but §4.4's filters comes from the stored widget.

        The filters dict is the entire public input surface, so a key it
        does not recognise must not reach the aggregation.
        """
        smuggled = resolve_widget_data(
            self.dashboard,
            self.widget(),
            {"form_id": 999999, "question_id": 999999, "monitoring": "all"},
        )
        self.assertEqual(smuggled, resolve_widget_data(
            self.dashboard, self.widget()
        ))

    def test_a_map_joins_each_point_to_its_status_bucket(self):
        """Pin colour is a second source, resolved here.

        This ran in the browser as a separate /values/formula request. It
        moved server-side with everything else, because an anonymous
        caller cannot be trusted to author a formula — and a map whose
        pins are all one colour is a wrong answer that looks like a
        design choice.
        """
        points = resolve_widget_data(
            self.dashboard,
            self.widget(
                type="map",
                question=self.Q_OPTION_ID,
                config={
                    "status_colors": {
                        "active": "#64A73B",
                        "pending": "#F5A623",
                    }
                },
            ),
        )
        self.assertTrue(points)
        for point in points:
            self.assertIn("status", point)
        self.assertTrue(
            any(p["status"] in ("active", "pending") for p in points)
        )

    def test_an_uncoloured_map_leaves_the_points_alone(self):
        # validate_shape rejects an empty bucket list, and every pin then
        # takes the widget's own accent colour.
        points = resolve_widget_data(
            self.dashboard,
            self.widget(type="map", question=self.Q_OPTION_ID, config={}),
        )
        self.assertTrue(points)
        for point in points:
            self.assertNotIn("status", point)
