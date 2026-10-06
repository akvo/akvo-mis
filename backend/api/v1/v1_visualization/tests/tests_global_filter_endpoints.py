import json

from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import FormData
from api.v1.v1_visualization.tests.global_filter_mixin import (
    BROKEN,
    GROUND,
    NO,
    GlobalFilterTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilterOutNonOperationalOnOtherWidgetsTestCase(
    GlobalFilterTestMixin, APITestCase
):
    """Map, table, status colours (formula) and scatter build their own
    queries (§7), so each needs its own test.

    Filter: "Is the infrastructure operational?" -> filter out
            Non-operational.
    Expect: water points 4, 5 and 6 disappear from each widget, exactly
            as they do from the charts.
    """

    KEPT_VISITED = {1, 2, 3, 7, 8, 9}

    def setUp(self):
        super().setUp()
        self.no_broken = self.filter_out(self.Q_STATUS, BROKEN)
        self.number_by_id = {site.id: n for n, site in self.site.items()}

    def map_sites(self, form_id, **params):
        response = self.client.get(
            f"/api/v1/maps/geolocation/{form_id}", params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(row["name"] for row in response.json())

    def colour_sites(self, form_id, question_id, op, value, **params):
        """Water points that get a colour from /values/formula."""
        formula = {
            "buckets": [{
                "value": "hit",
                "label": "Hit",
                "all_of": [
                    {"question_id": question_id, "op": op, "value": value},
                ],
            }],
            "default": {"value": "miss", "label": "Miss"},
        }
        response = self.client.get(
            "/api/v1/visualization/values/formula",
            {
                "form_id": form_id,
                "group_by": "parent_id",
                "formula": json.dumps(formula),
                **params,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        return {
            self.number_by_id[row["group"]]
            for row in response.json()["data"]
        }

    def table_sites(self, **params):
        response = self.client.get(
            f"/api/v1/visualization/escalation/{self.REG_ID}",
            {
                "monitoring_form_id": self.VISIT_ID,
                "columns": "name:parent_name",
                "page_size": 100,
                **params,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        return {
            self.number_by_id[row["id"]]
            for row in response.json()["results"]
        }

    def scatter_sites(self, **params):
        # Households on both axes: one point per visited water point.
        response = self.values(
            form_id=self.VISIT_ID, mode="scatter",
            question_id=self.Q_HOUSEHOLDS, question_y=self.Q_HOUSEHOLDS,
            **params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(point["name"] for point in response.json())

    # ── map (D-12) ──

    def test_map_of_water_points(self):
        # Without the filter: all 10 pins. With it: 4, 5, 6 removed.
        self.assertEqual(self.map_sites(self.REG_ID), set(range(1, 11)))
        self.assertEqual(
            self.map_sites(self.REG_ID, global_criteria=self.no_broken),
            {1, 2, 3, 7, 8, 9, 10},
        )

    def test_map_of_visits_filters_by_their_water_point(self):
        # Pins are visits here, so the filter follows each visit's
        # water point (parent), not the visit's own id.
        FormData.objects.filter(form=self.visit_form).update(
            geo=[-18.0, 178.0],
        )
        self.assertEqual(
            self.map_sites(self.VISIT_ID, global_criteria=self.no_broken),
            self.KEPT_VISITED,
        )

    # ── table ──

    def test_table_of_water_points(self):
        self.assertEqual(self.table_sites(), set(range(1, 10)))
        self.assertEqual(
            self.table_sites(global_criteria=self.no_broken),
            self.KEPT_VISITED,
        )

    # ── map status colours (formula, D-12) ──

    def test_colours_from_a_visit_question(self):
        # "Households >= 0" is true for every visit; only the filter
        # decides who is coloured.
        self.assertEqual(
            self.colour_sites(self.VISIT_ID, self.Q_HOUSEHOLDS, ">=", 0),
            set(range(1, 10)),
        )
        self.assertEqual(
            self.colour_sites(
                self.VISIT_ID, self.Q_HOUSEHOLDS, ">=", 0,
                global_criteria=self.no_broken,
            ),
            self.KEPT_VISITED,
        )

    def test_colours_from_a_registration_question(self):
        # Coloured by "Water source = Ground water"; site 10 (no answer)
        # still gets the default colour, so it is listed.
        self.assertEqual(
            self.colour_sites(
                self.REG_ID, self.Q_SOURCE, "option_equals", GROUND,
                global_criteria=self.no_broken,
            ),
            {1, 2, 3, 7, 8, 9, 10},
        )

    # ── scatter ──

    def test_scatter_of_households(self):
        self.assertEqual(self.scatter_sites(), set(range(1, 10)))
        self.assertEqual(
            self.scatter_sites(global_criteria=self.no_broken),
            self.KEPT_VISITED,
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class OtherWidgetsValidationTestCase(GlobalFilterTestMixin, APITestCase):
    """Map, table and status colours refuse a bad `global_criteria` with
    400 too (D-6, D-11). The map answers its other bad parameters with an
    empty 200, but not this one."""

    def requests(self, value):
        formula = json.dumps({
            "buckets": [{
                "value": "hit",
                "label": "Hit",
                "all_of": [
                    {"question_id": self.Q_HOUSEHOLDS, "op": ">=", "value": 0},
                ],
            }],
            "default": {"value": "miss", "label": "Miss"},
        })
        return {
            "map": self.client.get(
                f"/api/v1/maps/geolocation/{self.REG_ID}",
                {"global_criteria": value},
            ),
            "table": self.client.get(
                f"/api/v1/visualization/escalation/{self.REG_ID}",
                {
                    "monitoring_form_id": self.VISIT_ID,
                    "columns": "name:parent_name",
                    "global_criteria": value,
                },
            ),
            "status colours": self.client.get(
                "/api/v1/visualization/values/formula",
                {
                    "form_id": self.VISIT_ID,
                    "group_by": "parent_id",
                    "formula": formula,
                    "global_criteria": value,
                },
            ),
        }

    def assert_all_status(self, value, expected):
        # One assertion over {widget: status}, not subTest: the parallel
        # runner pickles a failing subTest together with the test case,
        # whose client is not picklable, and the whole run crashes.
        statuses = {
            name: response.status_code
            for name, response in self.requests(value).items()
        }
        self.assertEqual(statuses, dict.fromkeys(statuses, expected))

    def assert_all_400(self, value):
        self.assert_all_status(value, 400)

    def test_question_id_is_not_a_number(self):
        self.assert_all_400(f"option_not_in:abc:{BROKEN}")

    def test_empty_option_list(self):
        self.assert_all_400(f"option_not_in:{self.Q_STATUS}:")

    def test_question_from_another_form_family(self):
        self.assert_all_400(self.filter_out(self.Q_TOILET, NO))

    def test_question_without_options(self):
        self.assert_all_400(self.filter_out(self.Q_HOUSEHOLDS, "10"))

    def test_a_valid_filter_is_accepted(self):
        self.assert_all_status(self.filter_out(self.Q_STATUS, BROKEN), 200)
