from datetime import datetime

from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import FormData
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesStackTestCases(VisualizationValuesTestMixin, APITestCase):
    """Test stack_by parameter for stacked charts.

    Test data (from mixin setUp):
    - reg1 (adm_parent):
        - mon1a (Jan 2025): operational_status=active,
          features=[feature_x, feature_y]
        - mon1b (Mar 2025): operational_status=active,
          features=[feature_y, feature_z]
    - reg2 (adm_child):
        - mon2a (Jan 2025): operational_status=inactive,
          features=[feature_x, feature_z]
        - mon2b (Mar 2025): operational_status=pending,
          features=[feature_x, feature_y, feature_z]
    """

    def test_stack_by_option_group_by_month(self):
        """Operational status stacked by option, grouped by month.

        Jan 2025: active=1, inactive=1, pending=0
        Mar 2025: active=1, inactive=0, pending=1

        Response should have option labels as columns.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=option&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("data", data)
        self.assertIn("labels", data)
        self.assertIn("stack_labels", data)
        self.assertIn("colors", data)

        self.assertEqual(len(data["data"]), 2)

        # Verify stack_labels contains all option labels
        self.assertCountEqual(
            data["stack_labels"],
            ["Active", "Inactive", "Pending"],
        )

        # Verify colors from QuestionOptions
        self.assertCountEqual(
            data["colors"],
            ["#64A73B", "#e41a1c", "#ff7f00"],
        )

        # Verify data rows — each row has month + option counts
        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan["Active"], 1)
        self.assertEqual(jan["Inactive"], 1)
        self.assertEqual(jan["Pending"], 0)
        self.assertEqual(mar["Active"], 1)
        self.assertEqual(mar["Inactive"], 0)
        self.assertEqual(mar["Pending"], 1)

    def test_stack_by_option_group_by_parent_id(self):
        """Operational status stacked by option, grouped by parent.

        reg1 (all monitoring): active=2, inactive=0, pending=0
        reg2 (all monitoring): active=0, inactive=1, pending=1
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=parent_id&stack_by=option&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 2)
        self.assertIn("stack_labels", data)

        rows_by_label = {d["label"]: d for d in data["data"]}

        alpha = rows_by_label.get("Site Alpha")
        beta = rows_by_label.get("Site Beta")

        self.assertIsNotNone(alpha)
        self.assertIsNotNone(beta)

        self.assertEqual(alpha["Active"], 2)
        self.assertEqual(alpha["Inactive"], 0)
        self.assertEqual(alpha["Pending"], 0)
        self.assertEqual(beta["Active"], 0)
        self.assertEqual(beta["Inactive"], 1)
        self.assertEqual(beta["Pending"], 1)

        # Per akvo-mis-bvt: cross-form joins need parent_id on each row;
        # parent_name alone is not guaranteed unique across registration
        # submissions and would silently merge distinct datapoints.
        self.assertEqual(alpha["group"], self.reg1.id)
        self.assertEqual(beta["group"], self.reg2.id)

    def test_stack_by_option_group_by_parent_id_on_registration_form(self):
        """Per-parent option query on a REGISTRATION form (akvo-mis-9d8).

        The RWS dashboard's cross_tab widget queries implementing_agencies
        on the registration form with group_by=parent_id + stack_by=option
        so the client can join by parent_id against a categories query on
        the companion monitoring form. Before the fix, this path returned
        zero rows because _stack_option_by_parent assumed data_ids were
        monitoring records (parent__isnull=False), which is never true for
        registration submissions.

        Given two registrations with site_type answers, the response must
        carry one row per registration with option columns populated and
        the parent_id exposed as `group`.
        """
        from api.v1.v1_data.models import Answers

        Answers.objects.create(
            data=self.reg1,
            question=self.q_reg_option,
            options=["urban"],
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.reg2,
            question=self.q_reg_option,
            options=["rural"],
            created_by=self.user,
        )

        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.registration.id}"
            f"&question_id={self.Q_REG_OPTION_ID}"
            "&group_by=parent_id&stack_by=option"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 2)
        rows_by_group = {d["group"]: d for d in data["data"]}

        self.assertIn(self.reg1.id, rows_by_group)
        self.assertIn(self.reg2.id, rows_by_group)

        r1 = rows_by_group[self.reg1.id]
        r2 = rows_by_group[self.reg2.id]

        self.assertEqual(r1["Urban"], 1)
        self.assertEqual(r1["Rural"], 0)
        self.assertEqual(r1["Peri-urban"], 0)
        self.assertEqual(r2["Urban"], 0)
        self.assertEqual(r2["Rural"], 1)
        self.assertEqual(r2["Peri-urban"], 0)

    def test_stack_by_option_group_by_month_latest(self):
        """Stacked chart with monitoring=latest.

        Latest: reg1→active (Mar), reg2→pending (Mar).
        Both latest are in Mar.
        Expected: only Mar row with active=1, pending=1.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=option&monitoring=latest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Only 1 month (Mar) since both latest are in March
        self.assertEqual(len(data["data"]), 1)
        mar = data["data"][0]
        self.assertEqual(mar["Active"], 1)
        self.assertEqual(mar["Pending"], 1)

    def test_stack_by_option_multiple_option_question(self):
        """Multiple option question stacked by option, grouped by month.

        Each selected option is counted separately.
        Jan: feature_x=2, feature_y=1, feature_z=1
          (mon1a=[x,y], mon2a=[x,z])
        Mar: feature_x=1, feature_y=2, feature_z=2
          (mon1b=[y,z], mon2b=[x,y,z])
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_MULTI_ID}"
            "&group_by=month&stack_by=option&monitoring=all"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 2)
        self.assertCountEqual(
            data["stack_labels"],
            ["Feature X", "Feature Y", "Feature Z"],
        )

        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan["Feature X"], 2)
        self.assertEqual(jan["Feature Y"], 1)
        self.assertEqual(jan["Feature Z"], 1)
        self.assertEqual(mar["Feature X"], 1)
        self.assertEqual(mar["Feature Y"], 2)
        self.assertEqual(mar["Feature Z"], 2)

    def test_stack_by_option_with_date_filter(self):
        """Stacked chart filtered by date range.

        from_date=2025-03-01 → only Mar records.
        Mar: mon1b=active, mon2b=pending.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=option&monitoring=all"
            "&from_date=2025-03-01"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 1)
        mar = data["data"][0]
        self.assertEqual(mar["Active"], 1)
        self.assertEqual(mar["Pending"], 1)

    def test_stack_by_option_with_admin_filter(self):
        """Stacked chart filtered by administration.

        reg2 is registered in adm_child. Monitoring data inherits
        administration from its parent registration.
        mon2a (Jan)=inactive, mon2b (Mar)=pending.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=option&monitoring=all"
            f"&administration_id={self.adm_child.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 2)

        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan["Inactive"], 1)
        self.assertEqual(jan["Active"], 0)
        self.assertEqual(mar["Pending"], 1)
        self.assertEqual(mar["Active"], 0)

    def test_stack_by_option_percentage(self):
        """Stacked chart with value_type=percentage.

        All monitoring, group_by=month, stack_by=option.
        Jan: active=1, inactive=1 → total=2 → active=50%, inactive=50%
        Mar: active=1, pending=1 → total=2 → active=50%, pending=50%
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=option&monitoring=all"
            "&value_type=percentage"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(len(data["data"]), 2)

        rows_by_group = {d["group"]: d for d in data["data"]}
        jan = rows_by_group["2025-01"]
        mar = rows_by_group["2025-03"]

        self.assertEqual(jan["Active"], 50.0)
        self.assertEqual(jan["Inactive"], 50.0)
        self.assertEqual(mar["Active"], 50.0)
        self.assertEqual(mar["Pending"], 50.0)

    def test_stack_by_requires_group_by(self):
        """stack_by without group_by — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&stack_by=option"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_by_requires_question_id(self):
        """stack_by without question_id — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&group_by=month&stack_by=option"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_by_invalid_value(self):
        """Invalid stack_by value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=invalid"
        )
        self.assertEqual(response.status_code, 400)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesStackByQuestionTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """stack_by=option + stack_question_id: stacking by ANOTHER question.

    Same fixture as above. The two questions in play:
      600203 operational_status (option)   active / inactive / pending
      600204 features (multiple_option)    feature_x / feature_y / feature_z

    Which gives, over all four monitoring submissions:
      Active   (mon1a, mon1b): X=1 Y=2 Z=1
      Inactive (mon2a):        X=1 Y=0 Z=1
      Pending  (mon2b):        X=1 Y=1 Z=1
    """

    def stacked(self, **params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        response = self.client.get(f"{self.BASE_URL}?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def rows_by_label(self, data):
        return {row["label"]: row for row in data["data"]}

    def test_crosstab_splits_each_bar_by_the_other_question(self):
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            stack_question_id=self.Q_MULTI_ID,
            group_by="option",
            stack_by="option",
            monitoring="all",
        )
        # The legend is the STACKING question's options, in its own
        # option order — that is the whole point of the feature.
        self.assertEqual(
            data["stack_labels"],
            ["Feature X", "Feature Y", "Feature Z"],
        )
        self.assertEqual(
            data["colors"], ["#1f77b4", "#ff7f0e", "#2ca02c"],
        )
        rows = self.rows_by_label(data)
        self.assertEqual(
            {k: rows["Active"][k] for k in data["stack_labels"]},
            {"Feature X": 1, "Feature Y": 2, "Feature Z": 1},
        )
        self.assertEqual(
            {k: rows["Inactive"][k] for k in data["stack_labels"]},
            {"Feature X": 1, "Feature Y": 0, "Feature Z": 1},
        )
        self.assertEqual(
            {k: rows["Pending"][k] for k in data["stack_labels"]},
            {"Feature X": 1, "Feature Y": 1, "Feature Z": 1},
        )
        # A zero is a column, not an absence: akvo-charts derives its
        # series from the row's keys.
        self.assertIn("Feature Y", rows["Inactive"])

    def test_crosstab_bars_are_ordered_by_total_descending(self):
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            stack_question_id=self.Q_MULTI_ID,
            group_by="option",
            stack_by="option",
            monitoring="all",
        )
        # Totals 4, 3, 2 — not the option order active/inactive/pending.
        self.assertEqual(
            data["labels"], ["Active", "Pending", "Inactive"],
        )

    def test_equal_totals_fall_back_to_option_order(self):
        # Reversing the roles gives three bars of total 3 each, so the
        # tie-break is the only thing deciding the order. Without a
        # stable one the chart reshuffles between identical renders.
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_MULTI_ID,
            stack_question_id=self.Q_OPTION_ID,
            group_by="option",
            stack_by="option",
            monitoring="all",
        )
        self.assertEqual(
            data["labels"], ["Feature X", "Feature Y", "Feature Z"],
        )
        self.assertEqual(
            data["stack_labels"], ["Active", "Inactive", "Pending"],
        )

    def test_multi_select_percentage_divides_by_submissions(self):
        """D-1: a multi-select stack states a fact about submissions.

        The Active bar holds two submissions mentioning four features.
        Dividing by the four says "Feature X is 25% of the features
        mentioned"; dividing by the two says "50% of active submissions
        reported Feature X" — which is the sentence a reader assumes.
        """
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            stack_question_id=self.Q_MULTI_ID,
            group_by="option",
            stack_by="option",
            value_type="percentage",
            monitoring="all",
        )
        rows = self.rows_by_label(data)
        self.assertEqual(rows["Active"]["Feature X"], 50.0)
        self.assertEqual(rows["Active"]["Feature Y"], 100.0)
        self.assertEqual(rows["Active"]["Feature Z"], 50.0)
        # Over 100 on purpose: one submission belongs to several stacks.
        self.assertEqual(
            sum(rows["Active"][k] for k in data["stack_labels"]), 200.0
        )
        # And the bar order still follows the counts, not the shares.
        self.assertEqual(
            data["labels"], ["Active", "Pending", "Inactive"],
        )

    def test_single_select_percentage_keeps_the_column_denominator(self):
        # Roles reversed: the stacking question is single-select, so
        # selections and submissions coincide and D-1 changes nothing.
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_MULTI_ID,
            stack_question_id=self.Q_OPTION_ID,
            group_by="option",
            stack_by="option",
            value_type="percentage",
            monitoring="all",
        )
        rows = self.rows_by_label(data)
        self.assertEqual(
            round(sum(rows["Feature X"][k] for k in data["stack_labels"])),
            100,
        )

    def test_a_stack_question_needs_group_by_option(self):
        """Cross-tab or nothing.

        Grouped by month or by site the measured question contributes
        nothing — every number in the chart comes from the stacking
        question — so the chart says something the configuration does
        not. That chart is already spelled by measuring the stacking
        question directly with stack_by=option.
        """
        for group_by in ("month", "parent_id", "date"):
            response = self.client.get(
                f"{self.BASE_URL}?form_id={self.monitoring.id}"
                f"&question_id={self.Q_OPTION_ID}"
                f"&stack_question_id={self.Q_MULTI_ID}"
                f"&group_by={group_by}&stack_by=option&monitoring=all"
            )
            self.assertEqual(
                response.status_code, 400, f"group_by={group_by}"
            )

    def test_group_by_parent_stacks_by_its_own_options(self):
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_MULTI_ID,
            group_by="parent_id",
            stack_by="option",
            monitoring="latest",
        )
        # Order is unspecified on this path (no order_by), so compare
        # order-insensitively or the test passes for the wrong reason.
        rows = self.rows_by_label(data)
        self.assertCountEqual(
            data["labels"], ["Site Alpha", "Site Beta"],
        )
        # Latest per site: mon1b (y, z) and mon2b (x, y, z).
        self.assertEqual(
            {k: rows["Site Alpha"][k] for k in data["stack_labels"]},
            {"Feature X": 0, "Feature Y": 1, "Feature Z": 1},
        )
        self.assertEqual(
            {k: rows["Site Beta"][k] for k in data["stack_labels"]},
            {"Feature X": 1, "Feature Y": 1, "Feature Z": 1},
        )

    def test_group_by_date_stacks_instead_of_returning_nothing(self):
        """group_by=date used to draw an empty chart, silently."""
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            group_by="date",
            stack_by="option",
            monitoring="all",
        )
        self.assertEqual(
            data["labels"],
            ["2025-01-15", "2025-01-20", "2025-03-10", "2025-03-15"],
        )
        rows = self.rows_by_label(data)
        self.assertEqual(rows["2025-01-15"]["Active"], 1)
        self.assertEqual(rows["2025-01-15"]["Inactive"], 0)
        self.assertEqual(rows["2025-01-20"]["Inactive"], 1)
        self.assertEqual(rows["2025-03-15"]["Pending"], 1)

    def test_a_question_is_never_cross_tabbed_against_itself(self):
        """The diagonal is the plain breakdown wearing a legend.

        Every bar is one option, so its only non-zero segment is that
        same option. Falling through to the unstacked breakdown is the
        chart the author meant.
        """
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            group_by="option",
            stack_by="option",
            monitoring="all",
        )
        self.assertNotIn("stack_labels", data)
        self.assertCountEqual(
            [row["label"] for row in data["data"]],
            ["Active", "Inactive", "Pending"],
        )

    def test_omitting_the_stack_question_is_unchanged(self):
        """The self-stack still means what it always meant."""
        data = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            group_by="month",
            stack_by="option",
            monitoring="all",
        )
        self.assertCountEqual(
            data["stack_labels"], ["Active", "Inactive", "Pending"],
        )

    def test_naming_the_measured_question_is_the_self_stack(self):
        """Normalised away, so there is only one spelling of it."""
        explicit = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            stack_question_id=self.Q_OPTION_ID,
            group_by="month",
            stack_by="option",
            monitoring="all",
        )
        implicit = self.stacked(
            form_id=self.monitoring.id,
            question_id=self.Q_OPTION_ID,
            group_by="month",
            stack_by="option",
            monitoring="all",
        )
        self.assertEqual(explicit, implicit)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PendingParentExclusionTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """D-3 / S-7: an unapproved registration is not a site.

    `measure=current_state` filters its parents itself. The
    `all_submissions` path derives them from the children instead and
    used to take whatever the foreign key pointed at, so a registration
    still awaiting approval — with an approved monitoring submission —
    was drawn under one measure and absent under the other. Same site,
    same dashboard, two answers.
    """

    def setUp(self):
        super().setUp()
        self.pending_reg = FormData.objects.create(
            id=7300,
            name="Site Pending",
            form=self.registration,
            administration=self.adm_parent,
            created_by=self.user,
            is_pending=True,
        )
        self._create_monitoring(
            parent=self.pending_reg,
            created_date=datetime(2025, 1, 25),
            number_val=50.0,
            option_val="active",
            multi_vals=["feature_x"],
            date_val="2025-01-25T00:00:00.000Z",
        )
        self.draft_reg = FormData.objects.create(
            id=7301,
            name="Site Draft",
            form=self.registration,
            administration=self.adm_parent,
            created_by=self.user,
            is_draft=True,
        )
        self._create_monitoring(
            parent=self.draft_reg,
            created_date=datetime(2025, 1, 26),
            number_val=60.0,
            option_val="active",
            multi_vals=["feature_y"],
            date_val="2025-01-26T00:00:00.000Z",
        )

    def get(self, query):
        response = self.client.get(f"{self.BASE_URL}?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_stacked_bars_exclude_unapproved_parents(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=parent_id&stack_by=option&monitoring=all"
        )
        self.assertNotIn("Site Pending", data["labels"])
        self.assertNotIn("Site Draft", data["labels"])
        self.assertCountEqual(
            data["labels"], ["Site Alpha", "Site Beta"],
        )

    def test_both_measures_agree_on_which_sites_exist(self):
        params = (
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=parent_id&stack_by=option"
        )
        latest = self.get(f"{params}&monitoring=latest")
        every = self.get(f"{params}&monitoring=all")
        self.assertCountEqual(latest["labels"], every["labels"])

    def test_multiline_stacks_exclude_unapproved_parents(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=parent_id&monitoring=all"
        )
        self.assertNotIn("Site Pending", data["stack_labels"])
        self.assertNotIn("Site Draft", data["stack_labels"])

    def test_approved_parents_are_untouched(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=parent_id&stack_by=option&monitoring=all"
        )
        rows = {row["label"]: row for row in data["data"]}
        # Site Alpha over both its submissions: active twice.
        self.assertEqual(rows["Site Alpha"]["Active"], 2)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ParentGroupContractTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """The response contract a cross-form chart joins on (VIZ-015.a).

    Nothing in the backend knows it is participating in a join, so a
    later "the response carries a redundant `group`, drop it" would pass
    every other backend test and silently empty that chart. These two
    name the contract so the change fails here instead.
    """

    def get(self, query):
        response = self.client.get(f"{self.BASE_URL}?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_registration_rows_carry_their_own_id_as_group(self):
        data = self.get(
            f"form_id={self.registration.id}"
            f"&question_id={self.Q_REG_OPTION_ID}"
            "&group_by=parent_id&stack_by=option"
        )
        groups = {row["group"] for row in data["data"]}
        self.assertTrue(groups.issubset({self.reg1.id, self.reg2.id}))

    def test_monitoring_rows_carry_the_parents_id_as_group(self):
        # The same integer as above, which is the entire reason the two
        # responses can be joined at all.
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=parent_id&stack_by=option&monitoring=latest"
        )
        groups = {row["group"] for row in data["data"]}
        self.assertEqual(groups, {self.reg1.id, self.reg2.id})


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValueQuestionTestCases(VisualizationValuesTestMixin, APITestCase):
    """Bars measured by a number question (VIZ-015.b).

    The fixture's number question is `measurement_value` (600202):
      mon1a active  10.0   mon1b active  20.0
      mon2a inactive 30.0  mon2b pending 40.0
    """

    def get(self, query):
        response = self.client.get(f"{self.BASE_URL}?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def rows(self, data):
        return {r["label"]: r["value"] for r in data["data"]}

    def test_without_a_value_question_the_bars_are_counts(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=option&monitoring=all"
        )
        self.assertEqual(
            self.rows(data),
            {"Active": 2, "Inactive": 1, "Pending": 1},
        )

    def test_sum_replaces_the_count(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=sum&group_by=option&monitoring=all"
        )
        # Active holds 10 + 20; the other two hold one submission each.
        self.assertEqual(
            self.rows(data),
            {"Active": 30.0, "Inactive": 30.0, "Pending": 40.0},
        )

    def test_average_over_the_same_bars(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=average&group_by=option&monitoring=all"
        )
        self.assertEqual(self.rows(data)["Active"], 15.0)

    def test_an_option_with_no_submissions_is_zero_not_missing(self):
        # A hole in a bar chart reads as a rendering fault; a zero reads
        # as an absence of data, which is what it is.
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=sum&group_by=option&monitoring=latest"
        )
        self.assertIn("Active", self.rows(data))

    def test_the_cross_tab_aggregates_per_cell(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&stack_question_id={self.Q_MULTI_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=average"
            "&group_by=option&stack_by=option&monitoring=all"
        )
        rows = {r["label"]: r for r in data["data"]}
        # Active = mon1a (10, features x+y) and mon1b (20, features y+z).
        # Feature Y holds both, so its average is 15.
        self.assertEqual(rows["Active"]["Feature Y"], 15.0)
        self.assertEqual(rows["Active"]["Feature X"], 10.0)
        self.assertEqual(rows["Active"]["Feature Z"], 20.0)

    def test_stacked_by_month_aggregates_per_cell(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=sum"
            "&group_by=month&stack_by=option&monitoring=all"
        )
        rows = {r["label"]: r for r in data["data"]}
        # Jan: mon1a active 10, mon2a inactive 30.
        self.assertEqual(rows["Jan 2025"]["Active"], 10.0)
        self.assertEqual(rows["Jan 2025"]["Inactive"], 30.0)

    def test_stacked_by_site_aggregates_per_cell(self):
        data = self.get(
            f"form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=sum"
            "&group_by=parent_id&stack_by=option&monitoring=all"
        )
        rows = {r["label"]: r for r in data["data"]}
        # Site Alpha is active twice: 10 + 20.
        self.assertEqual(rows["Site Alpha"]["Active"], 30.0)
