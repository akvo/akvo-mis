"""View-level tests for /api/v1/visualization/values/formula."""
import json
from urllib.parse import quote

from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


def _encode(formula_dict):
    """URL-encode a formula JSON object for query string usage."""
    return quote(json.dumps(formula_dict, separators=(",", ":")))


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormulaValuesViewTests(
    VisualizationValuesTestMixin, APITestCase
):
    """Mixin pre-creates two registrations and four monitoring children
    on form 6002 with answers on q_number (600202)."""

    BASE_URL = "/api/v1/visualization/values/formula"

    def _formula(self):
        # mon1b numeric=20.0 (latest for reg1, passes <= 25)
        # mon2b numeric=40.0 (latest for reg2, fails <= 25)
        return {
            "buckets": [{
                "value": "low",
                "label": "Low",
                "all_of": [{
                    "question_id": self.Q_NUMBER_ID,
                    "op": "<=",
                    "value": 25,
                }],
            }],
            "default": {"value": "high", "label": "High"},
        }

    def test_groups_by_parent_id(self):
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(self._formula())}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        rows = {row["group"]: row["label"] for row in body["data"]}
        self.assertEqual(rows[self.reg1.id], "low")
        self.assertEqual(rows[self.reg2.id], "high")

    def test_between_inclusive_bounds(self):
        # Salinity-style range: 6.5 <= value <= 8.5
        formula = {
            "buckets": [{
                "value": "in_range",
                "label": "In",
                "all_of": [{
                    "question_id": self.Q_NUMBER_ID,
                    "op": "between",
                    "min": 6.5,
                    "max": 25.0,
                }],
            }],
            "default": {"value": "out", "label": "Out"},
        }
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(formula)}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = {
            row["group"]: row["label"]
            for row in response.json()["data"]
        }
        # reg1 latest=20.0 (in), reg2 latest=40.0 (out)
        self.assertEqual(rows[self.reg1.id], "in_range")
        self.assertEqual(rows[self.reg2.id], "out")

    def test_latest_repeat_used(self):
        # On reg1's latest monitoring (mon1b), the repeatable
        # number question has values [8.0, 12.0, 4.0] at indices
        # 0, 1, 2. The latest repeat (index=2) is 4.0. A formula
        # over the repeatable question should reflect 4.0 not 8.0.
        formula = {
            "buckets": [{
                "value": "small",
                "label": "Small",
                "all_of": [{
                    "question_id": self.Q_NUMBER_REPEAT_ID,
                    "op": "<=",
                    "value": 5,
                }],
            }],
            "default": {"value": "big", "label": "Big"},
        }
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(formula)}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = {
            row["group"]: row["label"]
            for row in response.json()["data"]
        }
        # reg1 latest mon1b: index=2 value=4.0 → small
        self.assertEqual(rows[self.reg1.id], "small")
        # reg2 latest mon2b: indices 0,1 values 25.0, 35.0 →
        # latest repeat is 35.0 → big
        self.assertEqual(rows[self.reg2.id], "big")

    def test_parent_with_no_monitoring_omitted(self):
        # Delete all monitoring children for reg1 (hard delete to
        # bypass the soft-delete manager).
        FormData.objects.filter(parent=self.reg1).delete(hard=True)
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(self._formula())}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        groups = [r["group"] for r in rows]
        self.assertNotIn(self.reg1.id, groups)
        self.assertIn(self.reg2.id, groups)

    def test_default_when_no_match(self):
        # Use a formula no datapoint can satisfy.
        formula = {
            "buckets": [{
                "value": "impossible",
                "label": "Never",
                "all_of": [{
                    "question_id": self.Q_NUMBER_ID,
                    "op": ">", "value": 9999,
                }],
            }],
            "default": {"value": "fallback", "label": "FB"},
        }
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(formula)}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = response.json()["data"]
        labels = {row["label"] for row in rows}
        self.assertEqual(labels, {"fallback"})

    def test_pending_monitoring_excluded(self):
        # Make all of reg1's monitoring children pending. The next
        # candidate for reg1 should be NONE; reg1 vanishes from the
        # response.
        FormData.objects.filter(parent=self.reg1).update(is_pending=True)
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(self._formula())}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        groups = [r["group"] for r in response.json()["data"]]
        self.assertNotIn(self.reg1.id, groups)
        self.assertIn(self.reg2.id, groups)

    def test_missing_required_param(self):
        # Missing form_id → 400
        url = (
            f"{self.BASE_URL}"
            f"?group_by=parent_id"
            f"&formula={_encode(self._formula())}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_malformed_formula_rejected(self):
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={quote('not json')}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_criteria_composes(self):
        # Add option answers so we can filter via criteria.
        Answers.objects.create(
            data=self.mon1b,
            question=self.q_option,
            options=["active"],
            created_by=self.user,
        )
        # Filter to monitorings where operational_status == active.
        # Both mon1a and mon1b are 'active' (from the mixin), and
        # we just made sure mon1b also has it. mon2b is 'pending'.
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.MONITORING_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(self._formula())}"
            f"&criteria=option_equals:{self.Q_OPTION_ID}:active"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = {
            row["group"]: row["label"]
            for row in response.json()["data"]
        }
        # reg1 still has an active monitoring → present.
        self.assertIn(self.reg1.id, rows)
        # reg2's latest (mon2b) is 'pending', not 'active', and
        # mon2a is 'inactive', so reg2 should be filtered out.
        self.assertNotIn(self.reg2.id, rows)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormulaValuesRegistrationFormTests(
    VisualizationValuesTestMixin, APITestCase
):
    """Formula endpoint with a registration-form question (no form.parent).

    The endpoint must group by the datapoint's own id rather than parent_id,
    since registration data has parent__isnull=True.
    """

    BASE_URL = "/api/v1/visualization/values/formula"

    def setUp(self):
        super().setUp()
        # Give reg1 a "yes" option answer and reg2 a "no" answer on the
        # registration-form option question (site_type, id=Q_REG_OPTION_ID).
        Answers.objects.create(
            data=self.reg1,
            question=self.q_reg_option,
            options=["yes"],
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.reg2,
            question=self.q_reg_option,
            options=["no"],
            created_by=self.user,
        )

    def _formula(self):
        return {
            "buckets": [{
                "value": "yes",
                "label": "Yes",
                "all_of": [{
                    "question_id": self.Q_REG_OPTION_ID,
                    "op": "option_equals",
                    "value": "yes",
                }],
            }],
            "default": {"value": "no", "label": "No"},
        }

    def test_registration_form_groups_by_own_id(self):
        """
        group key is the registration datapoint's own id,
        not a parent_id.
        """
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.REGISTRATION_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(self._formula())}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = {
            row["group"]: row["label"]
            for row in response.json()["data"]
        }
        # Both registration datapoints should appear.
        self.assertIn(self.reg1.id, rows)
        self.assertIn(self.reg2.id, rows)
        self.assertEqual(rows[self.reg1.id], "yes")
        self.assertEqual(rows[self.reg2.id], "no")

    def test_registration_form_excludes_pending(self):
        """Pending registration datapoints are not included."""
        FormData.objects.filter(id=self.reg1.id).update(is_pending=True)
        url = (
            f"{self.BASE_URL}"
            f"?form_id={self.REGISTRATION_FORM_ID}"
            f"&group_by=parent_id"
            f"&formula={_encode(self._formula())}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        groups = [row["group"] for row in response.json()["data"]]
        self.assertNotIn(self.reg1.id, groups)
        self.assertIn(self.reg2.id, groups)
