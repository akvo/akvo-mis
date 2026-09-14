from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesStackByAdministrationTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """Test stack_by=administration parameter for line charts.

    Test data (from mixin setUp):
    - reg1 (adm_parent, level 0):
        - mon1a (Jan 2025): measurement_value=10.0
        - mon1b (Mar 2025): measurement_value=20.0
    - reg2 (adm_child, level 1):
        - mon2a (Jan 2025): measurement_value=30.0
        - mon2b (Mar 2025): measurement_value=40.0

    Administration hierarchy:
    - adm_parent (level 0): path=None
    - adm_child (level 1): path="{adm_parent.id}."
    """

    def test_number_admin_level_0_group_by_month(self):
        """admin_level=0: all data grouped under root admin.

        adm_parent is level 0 → exact match.
        adm_child is level 1 → path ancestor at index 0 = adm_parent.
        Both map to adm_parent → single line.

        Jan: avg(10, 30) = 20.0
        Mar: avg(20, 40) = 30.0
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=0&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("data", data)
        self.assertIn("labels", data)
        self.assertIn("stack_labels", data)

        # All data merges into one admin group
        self.assertEqual(len(data["stack_labels"]), 1)
        self.assertEqual(
            data["stack_labels"][0], self.adm_parent.name
        )

        self.assertEqual(len(data["data"]), 2)
        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        # avg(10, 30) = 20.0
        self.assertEqual(jan[self.adm_parent.name], 20.0)
        # avg(20, 40) = 30.0
        self.assertEqual(mar[self.adm_parent.name], 30.0)

    def test_number_admin_level_1_group_by_month(self):
        """admin_level=1: only adm_child data appears.

        adm_parent is level 0 → level < target_level → dropped.
        adm_child is level 1 → exact match → own group.

        Jan: 30.0 (mon2a only)
        Mar: 40.0 (mon2b only)
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=1&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["stack_labels"]), 1)
        self.assertEqual(
            data["stack_labels"][0], self.adm_child.name
        )

        self.assertEqual(len(data["data"]), 2)
        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan[self.adm_child.name], 30.0)
        self.assertEqual(mar[self.adm_child.name], 40.0)

    def test_number_admin_level_too_high_returns_empty(self):
        """admin_level=5: no admin at that depth → empty result."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=5&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["data"], [])
        self.assertEqual(data["stack_labels"], [])

    def test_number_admin_monitoring_latest(self):
        """stack_by=administration with monitoring=latest.

        Latest per parent: reg1→mon1b (Mar, 20.0), reg2→mon2b (Mar, 40.0).
        admin_level=0 → both map to adm_parent.
        Mar: avg(20, 40) = 30.0
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=0&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 1)
        mar = data["data"][0]
        self.assertEqual(mar["group"], "2025-03")
        self.assertEqual(mar[self.adm_parent.name], 30.0)

    def test_number_admin_group_by_date(self):
        """stack_by=administration with group_by=date.

        admin_level=0 → all under adm_parent.
        4 monitoring records on 4 different dates.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=date&stack_by=administration"
            "&admin_level=0&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["stack_labels"]), 1)
        # 4 distinct dates
        self.assertEqual(len(data["data"]), 4)

        rows_by_group = {d["group"]: d for d in data["data"]}
        self.assertEqual(
            rows_by_group["2025-01-15"][self.adm_parent.name], 10.0
        )
        self.assertEqual(
            rows_by_group["2025-01-20"][self.adm_parent.name], 30.0
        )
        self.assertEqual(
            rows_by_group["2025-03-10"][self.adm_parent.name], 20.0
        )
        self.assertEqual(
            rows_by_group["2025-03-15"][self.adm_parent.name], 40.0
        )

    def test_number_admin_with_repeat_agg_sum(self):
        """stack_by=administration with repeat_agg=sum.

        admin_level=1 → only adm_child data (reg2).
        mon2a Jan: 30.0, mon2b Mar: 40.0 (single answers, sum=value)
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=1&repeat_agg=sum&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan[self.adm_child.name], 30.0)
        self.assertEqual(mar[self.adm_child.name], 40.0)

    def test_option_admin_group_by_month(self):
        """Option question + stack_by=administration + group_by=month.

        admin_level=0 → all under adm_parent.
        Counts submissions per admin per month.
        Jan: 2 submissions (mon1a + mon2a)
        Mar: 2 submissions (mon1b + mon2b)
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=0&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("stack_labels", data)
        self.assertEqual(len(data["stack_labels"]), 1)
        self.assertEqual(
            data["stack_labels"][0], self.adm_parent.name
        )

        self.assertEqual(len(data["data"]), 2)
        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan[self.adm_parent.name], 2)
        self.assertEqual(mar[self.adm_parent.name], 2)

    def test_option_admin_level_1_group_by_month(self):
        """Option + admin_level=1 → only adm_child data.

        Jan: 1 (mon2a), Mar: 1 (mon2b)
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=1&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["stack_labels"]), 1)
        rows_by_group = {d["group"]: d for d in data["data"]}
        self.assertEqual(
            rows_by_group["2025-01"][self.adm_child.name], 1
        )
        self.assertEqual(
            rows_by_group["2025-03"][self.adm_child.name], 1
        )

    def test_option_admin_group_by_date(self):
        """Option + stack_by=administration + group_by=date.

        admin_level=0, each date has 1 submission.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=date&stack_by=administration"
            "&admin_level=0&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 4)
        for row in data["data"]:
            self.assertEqual(row[self.adm_parent.name], 1)

    def test_admin_default_level_is_1(self):
        """Omitting admin_level defaults to 1.

        Same result as explicit admin_level=1.
        """
        response_default = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&monitoring=all"
        )
        response_explicit = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=administration"
            "&admin_level=1&monitoring=all"
        )
        self.assertEqual(response_default.status_code, 200)
        self.assertEqual(response_explicit.status_code, 200)
        self.assertEqual(
            response_default.json(), response_explicit.json()
        )
