from django.test.utils import override_settings
from rest_framework.test import APITestCase
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesNumberTestCases(VisualizationValuesTestMixin, APITestCase):
    """Test number question handling for /visualization/values.

    Test data (from mixin setUp):
    - reg1 (Site Alpha):
        - mon1a (Jan): number=10, repeatable=[5, 15]
        - mon1b (Mar, latest): number=20, repeatable=[8, 12, 4]
    - reg2 (Site Beta):
        - mon2a (Jan): number=30, repeatable=[10, 20]
        - mon2b (Mar, latest): number=40, repeatable=[25, 35]
    """

    def test_number_no_grouping(self):
        """Number question without group_by — single aggregate of all.

        All 4 monitoring values: 10, 20, 30, 40.
        Default aggregate (no group_by) returns single value.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 1)
        # Single aggregate — could be sum or average depending on impl
        self.assertIsNotNone(data["data"][0]["value"])

    def test_number_group_by_parent_id_latest(self):
        """Number question grouped by parent, latest monitoring only.

        Latest for reg1: mon1b → number=20
        Latest for reg2: mon2b → number=40
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=parent_id&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)

        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_label["Site Alpha"], 20.0)
        self.assertEqual(values_by_label["Site Beta"], 40.0)

    def test_number_group_by_parent_id_all(self):
        """Number question grouped by parent, all monitoring.

        reg1: mon1a=10, mon1b=20 → depends on aggregation
        reg2: mon2a=30, mon2b=40 → depends on aggregation
        Should return all values (4 total).
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=parent_id&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # With monitoring=all, values should be aggregated per parent
        self.assertEqual(len(data["data"]), 2)

    def test_number_group_by_month(self):
        """Number question grouped by month.

        Jan 2025: mon1a=10, mon2a=30
        Mar 2025: mon1b=20, mon2b=40
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=month&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)
        groups = {d["group"] for d in data["data"]}
        self.assertIn("2025-01", groups)
        self.assertIn("2025-03", groups)

    def test_number_repeat_agg_average(self):
        """Repeatable number question — average aggregation (default).

        Latest for reg1 (mon1b): repeatable=[8, 12, 4] → avg=8.0
        Latest for reg2 (mon2b): repeatable=[25, 35] → avg=30.0
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number_repeat.id}"
            "&group_by=parent_id&monitoring=latest&repeat_agg=average"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)

        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_label["Site Alpha"], 8.0)
        self.assertEqual(values_by_label["Site Beta"], 30.0)

    def test_number_repeat_agg_sum(self):
        """Repeatable number question — sum aggregation.

        Latest for reg1 (mon1b): [8, 12, 4] → sum=24.0
        Latest for reg2 (mon2b): [25, 35] → sum=60.0
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number_repeat.id}"
            "&group_by=parent_id&monitoring=latest&repeat_agg=sum"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_label["Site Alpha"], 24.0)
        self.assertEqual(values_by_label["Site Beta"], 60.0)

    def test_number_repeat_agg_max(self):
        """Repeatable number question — max aggregation.

        Latest for reg1 (mon1b): [8, 12, 4] → max=12.0
        Latest for reg2 (mon2b): [25, 35] → max=35.0
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number_repeat.id}"
            "&group_by=parent_id&monitoring=latest&repeat_agg=max"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_label["Site Alpha"], 12.0)
        self.assertEqual(values_by_label["Site Beta"], 35.0)

    def test_number_repeat_agg_min(self):
        """Repeatable number question — min aggregation.

        Latest for reg1 (mon1b): [8, 12, 4] → min=4.0
        Latest for reg2 (mon2b): [25, 35] → min=25.0
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number_repeat.id}"
            "&group_by=parent_id&monitoring=latest&repeat_agg=min"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_label["Site Alpha"], 4.0)
        self.assertEqual(values_by_label["Site Beta"], 25.0)

    def test_number_percentage_group_by_parent(self):
        """Number question with value_type=percentage, grouped by parent.

        Covers: "what percentage does each site contribute to the total?"

        Latest monitoring values:
        - reg1 (mon1b): measurement_value = 20.0
        - reg2 (mon2b): measurement_value = 40.0
        Total = 60.0

        Expected: Site Alpha = 33.33%, Site Beta = 66.67%.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=parent_id&monitoring=latest"
            "&value_type=percentage"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)

        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertAlmostEqual(
            values_by_label["Site Alpha"], 33.33, places=2
        )
        self.assertAlmostEqual(
            values_by_label["Site Beta"], 66.67, places=2
        )

    def test_number_percentage_repeat_agg_average(self):
        """Repeatable number percentage with average aggregation.

        Covers: "what percentage does each site's average test result
        contribute to the total?"

        Latest monitoring repeatable values:
        - reg1 (mon1b): [8, 12, 4] → avg = 8.0
        - reg2 (mon2b): [25, 35] → avg = 30.0
        Total = 38.0

        Expected: Site Alpha = 21.05%, Site Beta = 78.95%.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number_repeat.id}"
            "&group_by=parent_id&monitoring=latest"
            "&repeat_agg=average&value_type=percentage"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)

        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertAlmostEqual(
            values_by_label["Site Alpha"], 21.05, places=2
        )
        self.assertAlmostEqual(
            values_by_label["Site Beta"], 78.95, places=2
        )

    def test_number_group_by_month_fills_gaps_with_date_range(self):
        """Gap-fill empty months for number aggregate time series.

        Number values exist in Jan + Mar 2025 only. Requesting
        Jan..Jun returns 6 rows: Jan and Mar carry averaged values,
        Feb/Apr/May/Jun are filled with value=0 and labeled so the
        line chart keeps its x-axis.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=month&monitoring=all"
            "&from_date=2025-01-01&to_date=2025-06-30"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 6)
        groups_in_order = [d["group"] for d in data["data"]]
        self.assertEqual(
            groups_in_order,
            [
                "2025-01", "2025-02", "2025-03",
                "2025-04", "2025-05", "2025-06",
            ],
        )
        values = {d["group"]: d["value"] for d in data["data"]}
        # Jan avg(10, 30) = 20.0; Mar avg(20, 40) = 30.0
        self.assertEqual(values["2025-01"], 20.0)
        self.assertEqual(values["2025-03"], 30.0)
        self.assertEqual(values["2025-02"], 0)
        self.assertEqual(values["2025-04"], 0)
        self.assertEqual(values["2025-05"], 0)
        self.assertEqual(values["2025-06"], 0)

    def test_number_percentage_group_by_month(self):
        """Number question percentage grouped by month.

        All monitoring values by month:
        - Jan 2025: mon1a=10, mon2a=30 → total 40
        - Mar 2025: mon1b=20, mon2b=40 → total 60
        Grand total = 100.

        Expected: Jan=40%, Mar=60%.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=month&monitoring=all&value_type=percentage"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)

        values_by_group = {d["group"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_group["2025-01"], 40.0)
        self.assertEqual(values_by_group["2025-03"], 60.0)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesNumberGroupByIdTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """group_by=id for a number question (#382).

    The map widget keys its points on the REGISTRATION datapoint id, and
    a number question asked at registration has no parent to group by --
    `data__parent_id` is NULL on every row, so group_by=parent_id
    collapses the whole form into a single `group: "None"`. group_by=id
    is the path that answers "this datapoint's own number", and until
    now only count mode implemented it (_count_group_by_id); a number
    question fell through to the ungrouped "Total" aggregate.
    """

    def setUp(self):
        super().setUp()
        # A number question on the registration form. The seeded
        # example-vis-6 registration form has none -- its only number
        # lives on the monitoring child -- and adding one to the shared
        # fixture would change every test that reads /sources.
        self.q_reg_number = Questions.objects.create(
            id=600105,
            form=self.registration,
            question_group=self.q_reg_option.question_group,
            order=5,
            label="Population served",
            name="population_served",
            type=QuestionTypes.number,
        )
        Answers.objects.create(
            data=self.reg1,
            question=self.q_reg_number,
            value=100,
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.reg2,
            question=self.q_reg_number,
            value=250,
            created_by=self.user,
        )

    def test_registration_number_group_by_id(self):
        """One row per registration datapoint, keyed by its own id."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.registration.id}"
            f"&question_id={self.q_reg_number.id}"
            "&group_by=id"
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        self.assertEqual(len(rows), 2)

        by_group = {r["group"]: r for r in rows}
        self.assertEqual(
            by_group[str(self.reg1.id)]["value"], 100.0
        )
        self.assertEqual(
            by_group[str(self.reg1.id)]["label"], "Site Alpha"
        )
        self.assertEqual(
            by_group[str(self.reg2.id)]["value"], 250.0
        )
        self.assertEqual(
            by_group[str(self.reg2.id)]["label"], "Site Beta"
        )

    def test_registration_number_group_by_parent_id_is_unusable(self):
        """Why group_by=id exists: parent_id cannot answer this.

        Regression guard, not an endorsement -- a registration form has
        no parents, so this collapses to one unjoinable row. If it ever
        starts returning per-datapoint rows, the map should use it and
        this test should be the thing that says so.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.registration.id}"
            f"&question_id={self.q_reg_number.id}"
            "&group_by=parent_id"
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["group"], "None")

    def test_registration_number_group_by_id_skips_unanswered(self):
        """A datapoint with no answer is absent, not zero.

        The renderer decides what a missing number means -- akvo-charts
        draws a zero-value point as a small circle rather than dropping
        it -- and a row invented here would be indistinguishable from a
        real zero.
        """
        FormData.objects.create(
            id=7202,
            name="Site Gamma",
            form=self.registration,
            administration=self.adm_parent,
            geo=[-18.11, 178.44],
            created_by=self.user,
        )
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.registration.id}"
            f"&question_id={self.q_reg_number.id}"
            "&group_by=id"
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        self.assertEqual(len(rows), 2)
        self.assertNotIn("7202", [r["group"] for r in rows])

    def test_registration_number_group_by_id_percentage(self):
        """value_type=percentage shares the group_by=parent_id rule."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.registration.id}"
            f"&question_id={self.q_reg_number.id}"
            "&group_by=id&value_type=percentage"
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        by_group = {r["group"]: r["value"] for r in rows}
        # 100 / 350 and 250 / 350
        self.assertEqual(by_group[str(self.reg1.id)], 28.57)
        self.assertEqual(by_group[str(self.reg2.id)], 71.43)

    def test_monitoring_number_group_by_id(self):
        """On a monitoring form the key is the submission, not the site.

        Consistent with _count_group_by_id, which keys the latest
        monitoring submission's own id. The map does not use this path
        -- it has parent_id for monitoring forms -- but the grammar has
        to mean one thing.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_number.id}"
            "&group_by=id&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        self.assertEqual(len(rows), 2)
        by_group = {r["group"]: r["value"] for r in rows}
        self.assertEqual(by_group[str(self.mon1b.id)], 20.0)
        self.assertEqual(by_group[str(self.mon2b.id)], 40.0)
