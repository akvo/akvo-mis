import json
from datetime import datetime

from rest_framework.test import APITestCase
from django.test.utils import override_settings

from api.v1.v1_visualization.tests.global_filter_mixin import (
    GROUND,
    OPERATIONAL,
    RAIN,
    SURFACE,
    GlobalFilterTestMixin,
)

MARCH_20 = datetime(2025, 3, 20)


@override_settings(USE_TZ=False, TEST_ENV=True)
class RegistrationActiveInRangeTestCase(GlobalFilterTestMixin, APITestCase):
    """VIZ-027 D-23: a registration widget's date range keeps the water
    points with activity in it: registered in it, or monitored in it.

    Water points are registered in January (site 8 in December 2024).
    Checks on 03-10 reach sites 1, 2, 3, 4, 6, 7, 8 and 9; site 5 was
    last seen in February, site 10 never.
    """

    MARCH = {"from_date": "2025-03-01", "to_date": "2025-03-31"}
    MONITORED_IN_MARCH = {1, 2, 3, 4, 6, 7, 8, 9}

    def map_sites(self, **params):
        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.REG_ID}", params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(row["name"] for row in response.json())

    def test_a_chart_keeps_the_sites_monitored_in_the_range(self):
        self.assertEqual(
            self.sites_on_registration(**self.MARCH),
            self.MONITORED_IN_MARCH,
        )

    def test_the_map_keeps_the_sites_monitored_in_the_range(self):
        self.assertEqual(
            self.map_sites(**self.MARCH), self.MONITORED_IN_MARCH,
        )

    def test_the_status_colours_keep_them_too(self):
        formula = json.dumps({
            "buckets": [{
                "value": "any",
                "label": "Any",
                "all_of": [{
                    "question_id": self.Q_SOURCE,
                    "op": "option_in",
                    "values": [GROUND, SURFACE, RAIN],
                }],
            }],
            "default": {"value": "none", "label": "None"},
        })
        response = self.client.get(
            "/api/v1/visualization/values/formula",
            {
                "form_id": self.REG_ID,
                "group_by": "parent_id",
                "formula": formula,
                **self.MARCH,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        ids = {row["group"] for row in response.json()["data"]}
        self.assertEqual(
            ids, {self.site[n].id for n in self.MONITORED_IN_MARCH},
        )

    def test_registered_in_the_range_still_counts(self):
        # Registered 2025-01-01: every site but 8, monitored or not. The
        # range starts a day early: the fixture stamps created in Fiji
        # time (UTC+12), which reads as 12-31 here.
        self.assertEqual(
            self.sites_on_registration(
                from_date="2024-12-31", to_date="2025-01-01",
            ),
            {1, 2, 3, 4, 5, 6, 7, 9, 10},
        )

    def test_a_monitoring_submission_is_dated_by_the_date_question(self):
        # Only site 4's second visit is dated 02-20. The check form does
        # not ask "Date of visit", so its checks use their created date:
        # none falls in 02-16..02-28.
        self.assertEqual(
            self.sites_on_registration(
                from_date="2025-02-16",
                to_date="2025-02-28",
                date_question_id=self.Q_VISIT_DATE,
            ),
            {4},
        )

    def test_pending_and_draft_monitoring_do_not_count(self):
        check = self._check(5, MARCH_20, [OPERATIONAL])
        check.is_pending = True
        check.save()
        draft = self._check(10, MARCH_20, [OPERATIONAL])
        draft.is_draft = True
        draft.save()
        self.assertEqual(
            self.sites_on_registration(**self.MARCH),
            self.MONITORED_IN_MARCH,
        )
