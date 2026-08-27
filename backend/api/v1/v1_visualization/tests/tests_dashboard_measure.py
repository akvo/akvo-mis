from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_visualization.dashboard_measure import expand_measure


@override_settings(USE_TZ=False, TEST_ENV=True)
class ExpandMeasureTestCase(TestCase):
    """The one place `monitoring` is written (VIZ-010 D-4).

    Ported from `frontend/src/util/dashboardMeasure.js`, which the public
    path cannot use — there is no client trusted to expand anything. The
    two questions a widget can ask both produce a plausible number:

        current_state    sites, by their most recent submission
        all_submissions  submissions

    Ask the first with the second's parameters and "42" appears where the
    truth is "17", on a widget titled "Operational sites", with nothing on
    screen to suggest otherwise.
    """

    ROOT = 1
    MONITORING = 2

    def test_current_state_reduces_to_the_latest_per_site(self):
        params = expand_measure(
            {"form": self.MONITORING, "config": {"measure": "current_state"}},
            self.ROOT,
        )
        self.assertEqual(params["monitoring"], "latest")
        # Inseparable from monitoring=latest: without it the aggregate
        # counts submissions inside the latest-per-site universe, which
        # means nothing to anyone (VIZ-001 D-4).
        self.assertEqual(params["sum_by"], "parent_id")

    def test_all_submissions_counts_every_submission(self):
        params = expand_measure(
            {
                "form": self.MONITORING,
                "config": {"measure": "all_submissions"},
            },
            self.ROOT,
        )
        self.assertEqual(params["monitoring"], "all")
        self.assertNotIn("sum_by", params)

    def test_a_registration_widget_gets_neither(self):
        # It has no monitoring submissions to reduce over, and §4.5
        # rejects a measure on it at save time.
        params = expand_measure(
            {"form": self.ROOT, "config": {"measure": "current_state"}},
            self.ROOT,
        )
        self.assertNotIn("monitoring", params)
        self.assertNotIn("sum_by", params)

    def test_a_stale_measure_cannot_leak_through_the_form_guard(self):
        """Guarded on the form, not on config.measure.

        A measure left behind by an earlier edit — the widget was on a
        monitoring form, then moved — must not reach the request.
        """
        params = expand_measure(
            {"form": None, "config": {"measure": "current_state"}},
            self.ROOT,
        )
        self.assertEqual(params, {})

    def test_include_unmonitored_maps_to_include_unanswered(self):
        params = expand_measure(
            {
                "form": self.MONITORING,
                "config": {
                    "measure": "current_state",
                    "include_unmonitored": True,
                },
            },
            self.ROOT,
        )
        self.assertTrue(params["include_unanswered"])

    def test_a_false_include_unmonitored_is_absent_not_false(self):
        params = expand_measure(
            {
                "form": self.MONITORING,
                "config": {
                    "measure": "current_state",
                    "include_unmonitored": False,
                },
            },
            self.ROOT,
        )
        self.assertNotIn("include_unanswered", params)

    def test_an_unknown_measure_expands_to_nothing(self):
        params = expand_measure(
            {"form": self.MONITORING, "config": {"measure": "sideways"}},
            self.ROOT,
        )
        self.assertNotIn("monitoring", params)
