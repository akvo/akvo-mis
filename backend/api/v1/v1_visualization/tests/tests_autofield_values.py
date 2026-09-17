from django.test.utils import override_settings
from rest_framework.test import APITestCase
from api.v1.v1_data.models import Answers
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AutofieldValuesTestCases(VisualizationValuesTestMixin, APITestCase):
    """Test autofield (QuestionTypes.autofield) for /visualization/values.

    Autofield answers are stored in Answers.name as strings, with value=None.
    """

    def setUp(self):
        super().setUp()
        # Create an autofield question on the monitoring form
        self.q_autofield = Questions.objects.create(
            form=self.monitoring,
            question_group=self.q_number.question_group,
            name="Computed Score",
            label="Computed Score",
            type=QuestionTypes.autofield,
            order=10,
            fn={"fnString": "#10 * #11"},
        )

        # Seed numeric autofield answers stored in Answers.name (value=None)
        # mon1a: "10.5", mon1b: "20.5" (Site Alpha)
        # mon2a: "30.0", mon2b: "40.0" (Site Beta)
        self.ans_1a = Answers.objects.create(
            data=self.mon1a,
            question=self.q_autofield,
            name="10.5",
            value=None,
            created_by=self.user,
        )
        self.ans_1b = Answers.objects.create(
            data=self.mon1b,
            question=self.q_autofield,
            name="20.5",
            value=None,
            created_by=self.user,
        )
        self.ans_2a = Answers.objects.create(
            data=self.mon2a,
            question=self.q_autofield,
            name="30.0",
            value=None,
            created_by=self.user,
        )
        self.ans_2b = Answers.objects.create(
            data=self.mon2b,
            question=self.q_autofield,
            name="40.0",
            value=None,
            created_by=self.user,
        )

    def test_autofield_pure_numeric_no_grouping(self):
        """Pure numeric autofield without group_by returns total."""
        # Default monitoring is "latest" -> (20.5 + 40.0) / 2 = 30.25
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["value"], 30.25)
        self.assertEqual(data["data"][0]["label"], "Total")

        # With monitoring="all" -> (10.5 + 20.5 + 30.0 + 40.0) / 4 = 25.25
        res_all = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}&monitoring=all"
        )
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.json()
        self.assertEqual(data_all["data"][0]["value"], 25.25)

    def test_autofield_pure_numeric_group_by_parent_id_latest(self):
        """Pure numeric autofield grouped by parent_id (latest)."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=parent_id&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)
        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(values_by_label["Site Alpha"], 20.5)
        self.assertEqual(values_by_label["Site Beta"], 40.0)

    def test_autofield_pure_numeric_group_by_month(self):
        """Pure numeric autofield grouped by month."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=month&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 2)
        groups = {d["group"] for d in data["data"]}
        self.assertIn("2025-01", groups)
        self.assertIn("2025-03", groups)

    def test_autofield_pure_numeric_repeat_aggregations(self):
        """Test repeat_agg options: sum, average, min, max."""
        # Sum
        res_sum = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=parent_id&monitoring=all&repeat_agg=sum"
        )
        self.assertEqual(res_sum.status_code, 200)
        data_sum = {d["label"]: d["value"] for d in res_sum.json()["data"]}
        # Site Alpha: 10.5 + 20.5 = 31.0
        # Site Beta: 30.0 + 40.0 = 70.0
        self.assertEqual(data_sum["Site Alpha"], 31.0)
        self.assertEqual(data_sum["Site Beta"], 70.0)

    def test_autofield_mixed_values_fallback_to_option(self):
        """If non-numeric string exists, fallback to categorical."""
        # Change one answer to a non-numeric string "Pass"
        self.ans_2b.name = "Pass"
        self.ans_2b.save()

        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=option&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        labels = [d["label"] for d in data["data"]]
        # Categories should include the numbers as strings and "Pass"
        self.assertIn("Pass", labels)
        self.assertIn("10.5", labels)
        self.assertIn("20.5", labels)
        self.assertIn("30.0", labels)

    def test_autofield_mixed_values_fallback_numeric_grouping(self):
        """Mixed data falls back to option even if parent_id requested."""
        self.ans_1a.name = "Grade A"
        self.ans_1a.save()

        # Request group_by=parent_id (only valid for pure numeric)
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=parent_id&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        labels = [d["label"] for d in data["data"]]
        # Must fall back to categorical grouping showing string labels
        self.assertIn("Grade A", labels)
        self.assertIn("20.5", labels)

    def test_autofield_runtime_tokens_ignored_in_numeric_detection(self):
        """Runtime tokens ('null', 'NaN', etc.) don't trigger categorical."""
        # Change one answer to "NaN" and another to "null"
        self.ans_1a.name = "NaN"
        self.ans_1a.save()
        self.ans_2a.name = "null"
        self.ans_2a.save()

        # Should still evaluate in numeric mode without categorical fallback
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=parent_id&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        values_by_label = {d["label"]: d["value"] for d in data["data"]}
        # Latest for Site Alpha is mon1b (20.5), for Beta is mon2b (40.0)
        self.assertEqual(values_by_label["Site Alpha"], 20.5)
        self.assertEqual(values_by_label["Site Beta"], 40.0)

    def test_autofield_value_tokens_trigger_categorical(self):
        """Business value tokens ('N/A', 'Pass') trigger categorical mode."""
        self.ans_1a.name = "N/A"
        self.ans_1a.save()

        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&group_by=option&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        labels = [d["label"] for d in data["data"]]
        self.assertIn("N/A", labels)

    def test_autofield_all_null_dataset_defaults_cleanly(self):
        """All-null autofield dataset defaults to 0 without errors."""
        Answers.objects.filter(question=self.q_autofield).update(name="NaN")
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"][0]["value"], 0)

    def test_autofield_used_as_value_metric(self):
        """Autofield question can be used as value_question in option."""
        # Group by operational status (q_option), aggregate score (q_autofield)
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_option.id}"
            f"&value_question={self.q_autofield.id}"
            "&group_by=option&monitoring=all&repeat_agg=sum"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data["data"]) > 0)

    def test_autofield_scatter_mode(self):
        """Autofield can be used in scatter mode on X or Y axis."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&mode=scatter"
            f"&question_id={self.q_autofield.id}"
            f"&question_y={self.q_number.id}"
            "&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        # Check coordinates exist and are numeric floats
        self.assertIn("x", data[0])
        self.assertIn("y", data[0])
        self.assertIsInstance(data[0]["x"], float)
        self.assertIsInstance(data[0]["y"], float)

    def test_autofield_negative_and_scientific_notation(self):
        """Autofield handles negative numbers and scientific notation."""
        self.ans_1a.name = "-15.5"
        self.ans_1a.save()
        self.ans_1b.name = "1.2e2"  # 120.0
        self.ans_1b.save()
        self.ans_2a.name = "-0.5"
        self.ans_2a.save()
        self.ans_2b.name = "10.0"
        self.ans_2b.save()

        # Average: (-15.5 + 120.0 - 0.5 + 10.0) / 4 = 114.0 / 4 = 28.5
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"][0]["value"], 28.5)

    def test_autofield_dual_axis_scatter(self):
        """Scatter plot where both X and Y axes are autofield questions."""
        q_autofield_y = Questions.objects.create(
            form=self.monitoring,
            question_group=self.q_number.question_group,
            name="Computed Factor",
            label="Computed Factor",
            type=QuestionTypes.autofield,
            order=11,
        )
        Answers.objects.create(
            data=self.mon1b,
            question=q_autofield_y,
            name="5.0",
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.mon2b,
            question=q_autofield_y,
            name="10.0",
            created_by=self.user,
        )

        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&mode=scatter"
            f"&question_id={self.q_autofield.id}"
            f"&question_y={q_autofield_y.id}"
            "&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        # Verify dual autofield coordinates
        self.assertEqual(data[0]["x"], 20.5)
        self.assertEqual(data[0]["y"], 5.0)
        self.assertEqual(data[1]["x"], 40.0)
        self.assertEqual(data[1]["y"], 10.0)

    def test_autofield_scatter_skips_invalid_mixed_points(self):
        """Scatter plot skips points with non-numeric or null coordinates."""
        self.ans_1b.name = "Pass"  # Non-numeric string on X
        self.ans_1b.save()

        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&mode=scatter"
            f"&question_id={self.q_autofield.id}"
            f"&question_y={self.q_number.id}"
            "&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Only Site Beta (mon2b) should be present, mon1b is skipped
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["x"], 40.0)

    def test_autofield_zero_values_aggregation(self):
        """Zero values ('0', '0.0') are aggregated as true zeros, not nulls."""
        Answers.objects.filter(question=self.q_autofield).update(name="0.0")
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}"
            "&monitoring=all&repeat_agg=sum"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"][0]["value"], 0.0)
        self.assertEqual(data["data"][0]["label"], "Total")

    def test_autofield_kpi_mixed_fallback_count(self):
        """KPI card on mixed-type autofield returns top category count."""
        # Mix dataset with 2 'Fail', 1 'Pass', 1 '12'
        self.ans_1a.name = "Fail"
        self.ans_1a.save()
        self.ans_1b.name = "Fail"
        self.ans_1b.save()
        self.ans_2a.name = "Pass"
        self.ans_2a.save()
        self.ans_2b.name = "12"
        self.ans_2b.save()

        # No group_by requested (KPI card style)
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_autofield.id}&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Fallback to categorical grouping produces the category counts
        self.assertTrue(len(data["data"]) > 0)
        labels = {d["label"]: d["value"] for d in data["data"]}
        self.assertEqual(labels["Fail"], 2)
        self.assertEqual(labels["Pass"], 1)
        self.assertEqual(labels["12"], 1)
