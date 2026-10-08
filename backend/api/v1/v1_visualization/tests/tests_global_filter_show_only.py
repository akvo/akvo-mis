import json
from datetime import datetime

from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.tests.global_filter_mixin import (
    BROKEN,
    GROUND,
    OPERATIONAL,
    RAIN,
    SURFACE,
    YES,
    GlobalFilterTestMixin,
)

# VIZ-027 D-21 (backend BE-10): the filter bar shows only the ticked
# values, as the WAI portal does, and `global_match` combines filters.
# Read the fixture table in global_filter_mixin.py first. Latest check:
#   Operational      1, 2, 3, 7, 8, 9
#   Non-operational  4, 5, 6
#   never checked    10 (hidden by any status filter)
# Water source: Rainwater 8, 9.

VISITED_SITES = {1, 2, 3, 4, 5, 6, 7, 8, 9}
WORKING = {1, 2, 3, 7, 8, 9}


@override_settings(USE_TZ=False, TEST_ENV=True)
class ShowOnlyTestCase(GlobalFilterTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.working = self.show_only(self.Q_STATUS, OPERATIONAL)
        self.rain = self.show_only(self.Q_SOURCE, RAIN)
        self.number_by_id = {site.id: n for n, site in self.site.items()}

    def test_show_only_operational_on_every_chart(self):
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=self.working), WORKING,
        )
        # Site 10 was never checked, so it has no "Operational": hidden.
        self.assertEqual(
            self.sites_on_registration(global_criteria=self.working),
            WORKING,
        )

    def test_the_kpi_counts_only_the_shown_points(self):
        response = self.values(
            form_id=self.REG_ID, global_criteria=self.working,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 6)

    def test_show_only_a_registration_answer(self):
        self.assertEqual(
            self.sites_on_registration(global_criteria=self.rain), {8, 9},
        )

    def test_two_filters_match_all_by_default(self):
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.working + self.rain,
            ),
            {8, 9},
        )
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.working + self.rain,
                global_match="all",
            ),
            {8, 9},
        )

    def test_two_filters_match_any(self):
        # Operational OR Rainwater, as the WAI portal combines them.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.working + self.rain,
                global_match="any",
            ),
            WORKING,
        )

    def test_any_also_combines_a_filter_out(self):
        # Rainwater OR "not Non-operational": 1-3, 7-9 pass the second,
        # 8 and 9 the first; 4, 5, 6 pass neither.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=(
                    self.rain + self.filter_out(self.Q_STATUS, BROKEN)
                ),
                global_match="any",
            ),
            WORKING,
        )

    def test_any_with_a_two_part_filter_out(self):
        # The family filter on water_source has a registration part and a
        # visit part (the visit form asks it too). Not Rainwater: 1-7;
        # OR latest check Non-operational: 4, 5, 6. Of the visited sites,
        # 8 and 9 pass neither.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=(
                    self.filter_out(self.Q_SOURCE, RAIN)
                    + self.show_only(self.Q_STATUS, BROKEN)
                ),
                global_match="any",
            ),
            VISITED_SITES - {8, 9},
        )

    def test_a_family_filter_falls_back_to_the_registration_in_range(
        self,
    ):
        # Site 1's visit (02-15) says Rainwater; its registration says
        # Ground water. Ending the range on 02-10 leaves the visit out, so
        # the registration decides and site 1 is not shown.
        visit = FormData.objects.get(
            form=self.visit_form, parent=self.site[1],
        )
        self._answer(visit, self.Q_SOURCE_SEEN, options=[RAIN])
        self.assertEqual(
            self.sites_on_registration(
                global_criteria=self.rain, to_date="2025-02-10",
            ),
            {8, 9},
        )
        self.assertEqual(
            self.sites_on_registration(global_criteria=self.rain),
            {1, 8, 9},
        )

    def test_the_date_range_judges_the_latest_answer_in_range(self):
        # Range ends 02-28: only site 4 has an Operational check in it
        # (01-10). Site 3 broke on 01-10, site 5 on 01-20; the rest were
        # checked in March (D-13's table: 1 water point).
        self.assertEqual(
            self.sites_on_registration(
                global_criteria=self.working, to_date="2025-02-28",
            ),
            {4},
        )

    def test_one_matching_pump_is_enough(self):
        # D-9: site 7's newer check reports two pumps, one of each.
        self._check(7, datetime(2025, 3, 20), [OPERATIONAL, BROKEN])
        self.assertIn(
            7, self.sites_on_registration(global_criteria=self.working),
        )
        self.assertIn(
            7, self.sites_on_registration(
                global_criteria=self.show_only(self.Q_STATUS, BROKEN),
            ),
        )

    def test_map_table_and_colours_show_only_the_same_points(self):
        pins = self.client.get(
            f"/api/v1/maps/geolocation/{self.REG_ID}",
            {"global_criteria": self.working},
        )
        table = self.client.get(
            f"/api/v1/visualization/escalation/{self.REG_ID}",
            {
                "monitoring_form_id": self.VISIT_ID,
                "columns": "name:parent_name",
                "page_size": 100,
                "global_criteria": self.working,
            },
        )
        colours = self.client.get(
            "/api/v1/visualization/values/formula",
            {
                "form_id": self.VISIT_ID,
                "group_by": "parent_id",
                "formula": json.dumps({
                    "buckets": [{
                        "value": "hit", "label": "Hit",
                        "all_of": [{
                            "question_id": self.Q_HOUSEHOLDS,
                            "op": ">=", "value": 0,
                        }],
                    }],
                    "default": {"value": "miss", "label": "Miss"},
                }),
                "global_criteria": self.working,
            },
        )
        self.assertEqual(
            {
                "map": self.site_numbers(r["name"] for r in pins.json()),
                "table": {
                    self.number_by_id[r["id"]]
                    for r in table.json()["results"]
                },
                "colours": {
                    self.number_by_id[r["group"]]
                    for r in colours.json()["data"]
                },
            },
            {"map": WORKING, "table": WORKING, "colours": WORKING},
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class ShowOnlyValidationTestCase(GlobalFilterTestMixin, APITestCase):
    def status(self, **params):
        params.setdefault("form_id", self.VISIT_ID)
        return self.values(**params).status_code

    def test_results(self):
        both = (
            self.show_only(self.Q_STATUS, OPERATIONAL)
            + self.filter_out(self.Q_STATUS, BROKEN)
        )
        self.assertEqual(
            {
                "both types on one filter": self.status(
                    global_criteria=both,
                ),
                "match both": self.status(
                    global_criteria=self.show_only(
                        self.Q_STATUS, OPERATIONAL,
                    ),
                    global_match="both",
                ),
                "match any": self.status(
                    global_criteria=self.show_only(
                        self.Q_STATUS, OPERATIONAL,
                    ),
                    global_match="any",
                ),
                "match without a filter": self.status(
                    global_match="both",
                ),
                "empty value": self.status(
                    global_criteria=[
                        f"option_in:{self.CHECK_ID}:infrastructure_status:",
                    ],
                ),
            },
            {
                "both types on one filter": 400,
                "match both": 400,
                "match any": 200,
                "match without a filter": 400,
                "empty value": 400,
            },
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class PublicShowOnlyTestCase(GlobalFilterTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        tenant = Tenant.objects.get()
        self.user.tenant = tenant
        self.user.save()
        Forms.objects.filter(
            pk__in=[self.REG_ID, self.VISIT_ID, self.CHECK_ID],
        ).update(tenant=tenant)
        Administration.objects.filter(parent__isnull=True).update(
            tenant=tenant,
        )
        Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.registration,
            tenant=tenant,
            created_by=self.user,
            status=DashboardStatus.published,
            is_public=True,
            published_config={
                "default_filters": {"questions": [{
                    "form": self.CHECK_ID,
                    "name": "infrastructure_status",
                }]},
                "widgets": [{
                    "id": 1, "order": 1, "type": "bar", "col_span": 12,
                    "title": "Sample taken", "color": None,
                    "form": self.VISIT_ID, "question": self.Q_SAMPLE,
                    "config": {"group_by": "option"},
                }],
            },
        )
        self.client.credentials()

    def sample_chart(self, global_criteria):
        return self.client.get(self.VALUES_URL, {
            "form_id": self.VISIT_ID,
            "question_id": self.Q_SAMPLE,
            "group_by": "option",
            "dashboard_slug": "water-points",
            "global_criteria": global_criteria,
        })

    def test_show_only_on_the_published_filter(self):
        # Yes on the latest visit: sites 1-3, 5-9. Shown: 1-3, 7-9 -> 6.
        response = self.sample_chart(
            self.show_only(self.Q_STATUS, OPERATIONAL),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            {row["group"]: row["value"] for row in response.json()["data"]}
            [YES],
            6,
        )

    def test_any_cannot_slip_in_an_unpublished_filter(self):
        response = self.sample_chart(
            self.show_only(self.Q_STATUS, OPERATIONAL)
            + self.show_only(self.Q_SOURCE, RAIN),
        )
        self.assertEqual(response.status_code, 404, response.content)
        response = self.client.get(self.VALUES_URL, {
            "form_id": self.VISIT_ID,
            "dashboard_slug": "water-points",
            "global_criteria": (
                self.show_only(self.Q_STATUS, OPERATIONAL)
                + self.show_only(self.Q_SOURCE, RAIN)
            ),
            "global_match": "any",
        })
        self.assertEqual(response.status_code, 404, response.content)

    def test_another_filter_is_refused(self):
        response = self.sample_chart(self.show_only(self.Q_SOURCE, RAIN))
        self.assertEqual(response.status_code, 404, response.content)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ShowOnlyOnTheChartedQuestionTestCase(GlobalFilterTestMixin, APITestCase):
    """D-22: a chart of the filtered question itself counts only the
    ticked values, as a slicer does. On top of the fixture, the
    registration form asks "What is the water used for?" (multiple
    option): site 8 drinking + irrigation, site 9 drinking.
    Show only irrigation -> site 8, which also answered drinking.
    """

    Q_USES = 700105

    def setUp(self):
        super().setUp()
        self._question(
            self.registration, self.Q_USES, "water_uses",
            "What is the water used for?",
            [("drinking", "Drinking"), ("irrigation", "Irrigation")],
            type_=QuestionTypes.multiple_option,
        )
        self._answer(
            self.site[8], self.Q_USES, options=["drinking", "irrigation"],
        )
        self._answer(self.site[9], self.Q_USES, options=["drinking"])
        self.irrigation = self.show_only(self.Q_USES, "irrigation")

    def test_the_filtered_question_counts_only_the_ticked_values(self):
        counts = self.by_option(self.values(
            form_id=self.REG_ID, question_id=self.Q_USES, group_by="option",
            global_criteria=self.irrigation,
        ))
        self.assertEqual(
            (counts["irrigation"], counts["drinking"]), (1, 0),
        )

    def test_another_question_charts_every_answer_of_the_shown_points(self):
        # Site 8 is shown; its water source is Rainwater.
        counts = self.by_option(self.values(
            form_id=self.REG_ID, question_id=self.Q_SOURCE,
            group_by="option", global_criteria=self.irrigation,
        ))
        self.assertEqual(
            (counts[RAIN], counts[GROUND], counts[SURFACE]), (1, 0, 0),
        )

    def test_without_a_filter_every_value_counts(self):
        counts = self.by_option(self.values(
            form_id=self.REG_ID, question_id=self.Q_USES, group_by="option",
        ))
        self.assertEqual(
            (counts["irrigation"], counts["drinking"]), (1, 2),
        )
