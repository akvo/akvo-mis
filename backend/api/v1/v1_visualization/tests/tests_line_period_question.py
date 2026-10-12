from datetime import datetime

from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_visualization.tests.global_filter_mixin import (
    GlobalFilterTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class LinePeriodQuestionTestCase(GlobalFilterTestMixin, APITestCase):
    """A line's X-axis date and the dashboard's date filter are apart.

    `date_question_id` is the dashboard's range, as on every widget
    (D-18); `period_question_id` is the date a line groups its points
    by. Before, one parameter did both, so a line kept filtering by its
    own date question whatever the dashboard chose.

    Site 1's visit is entered on 03-05 but dated "Date of visit" 02-15.
    """

    def setUp(self):
        super().setUp()
        visit = self.site[1].children.get(form_id=self.VISIT_ID)
        self._stamp(visit, datetime(2025, 3, 5))

    def months(self, **params):
        response = self.values(
            form_id=self.VISIT_ID, group_by="month", **params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return {
            row["group"]: row["value"]
            for row in response.json()["data"] if row["value"]
        }

    def test_the_range_follows_the_dashboard_and_the_axis_the_line(self):
        # Entered in March (the dashboard's submission-date range), drawn
        # in February (the line's own date question).
        self.assertEqual(
            self.months(
                from_date="2025-03-01",
                period_question_id=self.Q_VISIT_DATE,
            ),
            {"2025-02": 1},
        )

    def test_without_a_period_question_the_date_question_does_both(self):
        # Callers that send only date_question_id keep today's meaning.
        self.assertEqual(
            self.months(
                from_date="2025-03-01",
                date_question_id=self.Q_VISIT_DATE,
            ),
            {},
        )
