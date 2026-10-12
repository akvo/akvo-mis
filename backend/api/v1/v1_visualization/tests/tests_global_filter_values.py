from datetime import datetime

from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions
from api.v1.v1_visualization.tests.global_filter_mixin import (
    BROKEN,
    FINE,
    GROUND,
    NO,
    OPERATIONAL,
    RAIN,
    RAINY,
    SURFACE,
    YES,
    GlobalFilterTestMixin,
)

# Read the fixture table in global_filter_mixin.py first: every number
# below is counted from it.

VISITED_SITES = {1, 2, 3, 4, 5, 6, 7, 8, 9}


@override_settings(USE_TZ=False, TEST_ENV=True)
class GlobalFilterFixtureTestCase(GlobalFilterTestMixin, APITestCase):
    """No filter at all: the charts draw what the fixture table says.

    These pass today. If one fails, the fixture is wrong, and so is every
    expected number in the global filter tests.
    """

    def test_every_visited_site_is_on_the_visit_form(self):
        # Site 10 was never visited.
        self.assertEqual(self.sites_on_visit_form(), VISITED_SITES)

    def test_every_site_is_on_the_registration_form(self):
        self.assertEqual(self.sites_on_registration(), set(range(1, 11)))

    def test_water_source_chart(self):
        # Ground water: 1-6. Surface water: 7. Rainwater: 8, 9.
        counts = self.by_option(self.values(
            form_id=self.REG_ID, question_id=self.Q_SOURCE,
            group_by="option",
        ))
        self.assertEqual(
            (counts[GROUND], counts[SURFACE], counts[RAIN]), (6, 1, 2),
        )

    def test_sample_taken_chart_latest_and_all_visits(self):
        # Latest visit per site: site 4's latest (02-20) says No.
        # All visits: nine Yes, plus site 4's second visit, No.
        latest = self.by_option(self.values(
            form_id=self.VISIT_ID, question_id=self.Q_SAMPLE,
            group_by="option",
        ))
        every = self.by_option(self.values(
            form_id=self.VISIT_ID, question_id=self.Q_SAMPLE,
            group_by="option", monitoring="all",
        ))
        self.assertEqual((latest[YES], latest[NO]), (8, 1))
        self.assertEqual((every[YES], every[NO]), (9, 1))

    def test_infrastructure_chart_all_checks(self):
        # Non-operational: 3 (Jan), 4 (Mar), 5, 6.
        # Operational: 1, 2, 3 (Mar), 4 (Jan), 7, 8, 9.
        counts = self.by_option(self.values(
            form_id=self.CHECK_ID, question_id=self.Q_STATUS,
            group_by="option", monitoring="all",
        ))
        self.assertEqual((counts[BROKEN], counts[OPERATIONAL]), (4, 7))


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilterOutNonOperationalTestCase(GlobalFilterTestMixin, APITestCase):
    """The sketch: the viewer filters out "Non-operational".

    Filter: "Is the infrastructure operational?" -> filter out
            Non-operational. The question is on the Quick status check
            form; the charts below are on all three forms.
    Expect: water points 4, 5 and 6 disappear from EVERY chart, because
            their latest check says Non-operational.
    """

    def setUp(self):
        super().setUp()
        self.no_broken = self.filter_out(self.Q_STATUS, BROKEN)

    def test_broken_water_points_leave_the_visit_charts(self):
        # A chart on another form (Water quality visit) loses 4, 5, 6.
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=self.no_broken),
            {1, 2, 3, 7, 8, 9},
        )

    def test_broken_water_points_leave_registration(self):
        # Site 10 was never checked, so nothing says it is broken: it
        # stays (D-5).
        self.assertEqual(
            self.sites_on_registration(global_criteria=self.no_broken),
            {1, 2, 3, 7, 8, 9, 10},
        )

    def test_a_repaired_water_point_stays(self):
        # Site 3 was broken in January and repaired in March. Only the
        # latest check counts (D-4). Site 4 went the other way and goes.
        sites = self.sites_on_visit_form(global_criteria=self.no_broken)
        self.assertIn(3, sites)
        self.assertNotIn(4, sites)

    def test_number_of_water_points_kpi(self):
        # 10 registered water points minus 4, 5, 6.
        response = self.values(
            form_id=self.REG_ID, global_criteria=self.no_broken,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 7)

    def test_water_source_chart(self):
        # Ground water was 1-6; 4, 5, 6 leave. Surface and Rainwater
        # keep every site.
        counts = self.by_option(self.values(
            form_id=self.REG_ID, question_id=self.Q_SOURCE,
            group_by="option", global_criteria=self.no_broken,
        ))
        self.assertEqual(
            (counts[GROUND], counts[SURFACE], counts[RAIN]), (3, 1, 2),
        )

    def test_no_info_bar_counts_only_the_unanswered_site(self):
        # "No info" = water points with no water source answer: only
        # site 10. The filtered-out 4, 5, 6 must not move into "No info".
        counts = self.by_option(self.values(
            form_id=self.REG_ID, question_id=self.Q_SOURCE,
            group_by="option", include_unanswered="true",
            global_criteria=self.no_broken,
        ))
        self.assertEqual((counts[GROUND], counts["_no_info"]), (3, 1))

    def test_percentage_of_water_points_visited(self):
        # Visited: 6 of the 7 remaining water points = 85.71 %.
        # Not 6 of all 10 (60 %): the denominator drops 4, 5, 6 as well.
        response = self.values(
            form_id=self.VISIT_ID, value_type="percentage",
            sum_by="parent_id", global_criteria=self.no_broken,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 85.71)

    def test_percentage_without_group_by(self):
        # Same number through handle_count_mode's other branch.
        response = self.values(
            form_id=self.VISIT_ID, value_type="percentage",
            global_criteria=self.no_broken,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 85.71)

    def test_sample_taken_chart_latest_visit(self):
        # Was Yes 8 / No 1. Site 4 (the No) and 5, 6 (Yes) leave.
        counts = self.by_option(self.values(
            form_id=self.VISIT_ID, question_id=self.Q_SAMPLE,
            group_by="option", global_criteria=self.no_broken,
        ))
        self.assertEqual((counts[YES], counts[NO]), (6, 0))

    def test_sample_taken_chart_all_visits(self):
        # Was Yes 9 / No 1. Both of site 4's visits leave, with 5 and 6.
        counts = self.by_option(self.values(
            form_id=self.VISIT_ID, question_id=self.Q_SAMPLE,
            group_by="option", monitoring="all",
            global_criteria=self.no_broken,
        ))
        self.assertEqual((counts[YES], counts[NO]), (6, 0))

    def test_all_checks_mode_drops_every_check_of_a_broken_site(self):
        # Weather is Fine on all 11 checks. Site 4's January check said
        # Operational, yet it leaves too: the whole water point is
        # filtered out, not single checks (D-2). 11 - 2 (site 4) - 5 - 6.
        counts = self.by_option(self.values(
            form_id=self.CHECK_ID, question_id=self.Q_WEATHER,
            group_by="option", monitoring="all",
            global_criteria=self.no_broken,
        ))
        self.assertEqual(counts[FINE], 7)

    def test_all_checks_chart_still_shows_an_old_non_operational(self):
        # D-2 consequence, and the surprising one: the chart of the very
        # question being filtered still shows 1 Non-operational. It is
        # site 3's January check; site 3 is kept because it was repaired.
        counts = self.by_option(self.values(
            form_id=self.CHECK_ID, question_id=self.Q_STATUS,
            group_by="option", monitoring="all",
            global_criteria=self.no_broken,
        ))
        self.assertEqual((counts[BROKEN], counts[OPERATIONAL]), (1, 6))

    def test_end_date_before_the_repair(self):
        # Date range ends 02-28, so March checks do not count:
        #   site 3: latest check in range is January, Non-op -> out
        #   site 4: latest check in range is January, OK     -> in
        #   site 5: January, Non-operational                 -> out
        #   site 6: no check in range                        -> in
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.no_broken, to_date="2025-02-28",
            ),
            {1, 2, 4, 6, 7, 8, 9},
        )

    def test_start_date_after_the_only_breakdown(self):
        # Date range starts 02-01. Site 5's only check (January) is
        # outside it: nothing in range says it is broken, so it stays.
        # Sites 4 and 6 are broken in March and leave.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.no_broken, from_date="2025-02-01",
            ),
            {1, 2, 3, 5, 7, 8, 9},
        )

    def test_date_question_from_another_form_is_not_used(self):
        # The dashboard's date question is "Date of visit", which lives
        # on the visit form. Checks have no such answer, so the filter
        # falls back to each check's own date (A5). Otherwise no check
        # would match and nothing would be filtered out.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.no_broken,
                date_question_id=self.Q_VISIT_DATE,
                from_date="2025-01-01",
                to_date="2025-12-31",
            ),
            {1, 2, 3, 7, 8, 9},
        )

    def test_one_broken_pump_is_enough(self):
        # Site 11's latest check inspected two pumps: the first
        # Operational, the second Non-operational. One broken repeat is
        # enough to filter the water point out (D-9).
        site = FormData.objects.create(
            name="Site 11",
            form=self.registration,
            administration=self.adm,
            created_by=self.user,
        )
        self.site[11] = self._stamp(site, datetime(2025, 1, 1))
        self._visit(11, datetime(2025, 2, 15), sample_taken=YES)
        self._check(11, datetime(2025, 3, 10), [OPERATIONAL, BROKEN])

        self.assertIn(11, self.sites_on_visit_form())
        self.assertNotIn(
            11, self.sites_on_visit_form(global_criteria=self.no_broken),
        )

    def test_two_filters_together(self):
        # Filter out Non-operational AND Surface water: a water point
        # leaves if either filter removes it. 4, 5, 6 (broken) and 7
        # (surface water).
        both = self.no_broken + self.filter_out(self.Q_SOURCE, SURFACE)
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=both), {1, 2, 3, 8, 9},
        )

    def test_the_filter_survives_a_recreated_question(self):
        # D-20: a form edit soft-deletes the status question and creates
        # it again, same name, new id. The filter names (form, name), so
        # it keeps working on the new question: site 7's newer check
        # answers it Non-operational and site 7 goes. Answers to the old
        # version no longer count, so 4, 5 and 6 come back.
        Questions.objects.filter(pk=self.Q_STATUS).delete()
        recreated = self._question(
            self.check_form, 700306, "infrastructure_status",
            "Is the infrastructure operational?",
            [(OPERATIONAL, "Operational"), (BROKEN, "Non-operational")],
        )
        check = self._check(7, datetime(2025, 3, 20), [])
        self._answer(check, recreated.id, options=[BROKEN])
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=self.no_broken),
            VISITED_SITES - {7},
        )

    def test_filter_runs_inside_the_chart_query(self):
        # D-1: no separate query loads the filtered-out ids. The status
        # match (`options @> ...`) only appears nested under NOT (... IN).
        with CaptureQueriesContext(connection) as ctx:
            self.sites_on_visit_form(global_criteria=self.no_broken)
        matches = [
            q["sql"] for q in ctx.captured_queries
            if "@>" in q["sql"] and str(self.Q_STATUS) in q["sql"]
        ]
        self.assertTrue(matches, "the filter never reached SQL")
        for sql in matches:
            self.assertIn("NOT (", sql)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilterOutRainwaterTestCase(GlobalFilterTestMixin, APITestCase):
    """A filter on a registration question (D-8).

    Filter: "What is the water source?" -> filter out Rainwater.
            The question is on the registration form itself.
    Expect: water points 8 and 9 disappear from every chart, whatever
            the date range.
    """

    def setUp(self):
        super().setUp()
        self.no_rain = self.filter_out(self.Q_SOURCE, RAIN)

    def test_rainwater_points_leave_every_chart(self):
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=self.no_rain),
            {1, 2, 3, 4, 5, 6, 7},
        )
        self.assertEqual(
            self.sites_on_registration(global_criteria=self.no_rain),
            {1, 2, 3, 4, 5, 6, 7, 10},
        )

    def test_date_range_does_not_apply_to_the_water_source(self):
        # Site 8 was registered 2024-12-01, before the range. It still
        # leaves: a registration answer has no visit date to judge.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.no_rain, from_date="2025-01-15",
            ),
            {1, 2, 3, 4, 5, 6, 7},
        )

    def test_corrected_answer_is_what_counts(self):
        # Site 9's water source is corrected from Rainwater to Ground
        # water. It comes back; site 8 is still Rainwater and stays out.
        Answers.objects.filter(
            data=self.site[9], question_id=self.Q_SOURCE,
        ).update(options=[GROUND])
        sites = self.sites_on_visit_form(global_criteria=self.no_rain)
        self.assertIn(9, sites)
        self.assertNotIn(8, sites)

    def test_a_newer_visit_answer_overrides_the_registration(self):
        # The visit form asks "What is the water source?" again, with the
        # same `name`. Filtered on the registration form, the scope is the
        # whole family (D-20): site 1's visit (02-15) answers Rainwater,
        # newer than its registration's Ground water, so site 1 leaves.
        # Site 8, never asked again, is judged by its registration.
        visit = FormData.objects.get(
            form=self.visit_form, parent=self.site[1],
        )
        self._answer(visit, self.Q_SOURCE_SEEN, options=[RAIN])
        sites = self.sites_on_visit_form(global_criteria=self.no_rain)
        self.assertNotIn(1, sites)
        self.assertNotIn(8, sites)

    def test_a_newer_visit_answer_can_bring_a_point_back(self):
        # Site 9 registered Rainwater; its visit says Ground water now.
        visit = FormData.objects.get(
            form=self.visit_form, parent=self.site[9],
        )
        self._answer(visit, self.Q_SOURCE_SEEN, options=[GROUND])
        sites = self.sites_on_visit_form(global_criteria=self.no_rain)
        self.assertIn(9, sites)
        self.assertNotIn(8, sites)

    def test_a_visit_outside_the_range_leaves_the_registration_to_decide(
        self,
    ):
        # Site 1's visit (02-15) says Rainwater, its registration Ground
        # water; site 9's visit says Ground water, its registration
        # Rainwater. With the range ending 02-10, no visit is in range, so
        # each registration answer decides: site 1 stays, site 9 goes.
        for n, source in ((1, RAIN), (9, GROUND)):
            visit = FormData.objects.get(
                form=self.visit_form, parent=self.site[n],
            )
            self._answer(visit, self.Q_SOURCE_SEEN, options=[source])
        sites = self.sites_on_registration(
            global_criteria=self.no_rain, to_date="2025-02-10",
        )
        self.assertIn(1, sites)
        self.assertNotIn(9, sites)
        # Without the range both visits speak: the opposite.
        sites = self.sites_on_registration(global_criteria=self.no_rain)
        self.assertNotIn(1, sites)
        self.assertIn(9, sites)

    def test_two_options_of_one_question(self):
        # Filter out Surface water AND Rainwater: only ground water
        # points 1-6 remain.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(
                    self.Q_SOURCE, SURFACE, RAIN,
                ),
            ),
            {1, 2, 3, 4, 5, 6},
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class GlobalFilterValuesValidationTestCase(
    GlobalFilterTestMixin, APITestCase
):
    """A bad `global_criteria` is a 400, never a silently unfiltered chart
    (D-6, D-10)."""

    def get(self, value, **params):
        params.setdefault("form_id", self.VISIT_ID)
        return self.values(global_criteria=value, **params)

    def message(self, response):
        self.assertEqual(response.status_code, 400, response.content)
        return response.json()["message"]

    def test_form_id_is_not_a_number(self):
        self.message(self.get(
            f"option_not_in:abc:infrastructure_status:{BROKEN}",
        ))

    def test_no_options_given(self):
        self.message(self.get(
            f"option_not_in:{self.CHECK_ID}:infrastructure_status",
        ))

    def test_the_old_question_id_grammar_is_refused(self):
        # D-20 replaced `option_not_in:<qid>:<value>`.
        self.message(self.get(f"option_not_in:{self.Q_STATUS}:{BROKEN}"))

    def test_empty_value_says_so(self):
        self.assertIn(
            "option_not_in requires a value",
            self.message(self.get(
                f"option_not_in:{self.CHECK_ID}:infrastructure_status:",
            )),
        )

    def test_a_name_missing_from_the_form_is_refused(self):
        # The status question is on the check form, not the visit form.
        self.assertIn(
            "no option question",
            self.message(self.get(self.filter_out_on(
                self.VISIT_ID, "infrastructure_status", BROKEN,
            ))),
        )

    def test_more_than_fifty_values_is_refused(self):
        # D-15: bounds what a public caller can send.
        values = [f"value_{i}" for i in range(51)]
        self.message(self.get(self.filter_out(self.Q_STATUS, *values)))

    def test_a_value_with_delimiters_is_filtered_like_any_other(self):
        # D-15: older forms can hold values such as this one, generated
        # from a label before `:`, `,` and `|` were removed at the
        # source. One parameter per value, split at most three times,
        # keeps it intact. Site 7's latest check reports it -> site 7 goes.
        odd = "pump:_broken,_leaking|pipe"
        self._check(7, datetime(2025, 3, 20), [odd])
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(self.Q_STATUS, odd),
            ),
            VISITED_SITES - {7},
        )

    def test_only_show_only_and_filter_out_are_supported(self):
        # D-21: `option_in` and `option_not_in`. A widget criteria type
        # such as `option_equals` is not a global filter.
        self.message(self.get(
            f"option_equals:{self.CHECK_ID}:infrastructure_status:{BROKEN}",
        ))

    def test_filter_out_is_refused_in_a_widgets_own_criteria(self):
        # D-10: inside a widget's criteria it would empty the widget.
        response = self.values(
            form_id=self.VISIT_ID,
            criteria=f"option_not_in:{self.Q_SAMPLE}:{YES}",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_question_from_another_form_family(self):
        # "Does the school have a toilet?" is not about water points.
        self.assertIn(
            "not in this form family",
            self.message(self.get(self.filter_out(self.Q_TOILET, NO))),
        )

    def test_question_without_options(self):
        # "How many households use this water point?" is a number.
        self.message(self.get(self.filter_out(self.Q_HOUSEHOLDS, "10")))

    def test_any_form_of_the_family_can_filter_any_chart(self):
        # A registration chart filtered by a status-check question.
        response = self.get(
            self.filter_out(self.Q_STATUS, BROKEN), form_id=self.REG_ID,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 7)


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilterOutRainyAcrossFormsTestCase(GlobalFilterTestMixin, APITestCase):
    """D-14, D-20: a question asked under the same name on several
    monitoring forms, filtered on the registration form (family scope):
    the most recent answer from any of them wins.

    On top of the fixture, the visit form also asks "What is the weather
    during the visit?" under the same name, `weather`, as the check form.
      site 5: visit 02-15 Rainy, newer than its only check (01-20, Fine)
      site 6: visit 02-15 Rainy, older than its check (03-10, Fine)

    Filter: weather, family scope -> filter out Rainy.
    Expect: site 5 disappears (its latest weather answer is Rainy);
            site 6 stays (its latest weather answer is Fine).
    """

    Q_WEATHER_VISIT = 700205
    Q_CHECK_DATE = 700303

    def setUp(self):
        super().setUp()
        self._question(
            self.visit_form, self.Q_WEATHER_VISIT, "weather",
            "What is the weather during the visit?",
            [(FINE, "Fine"), (RAINY, "Rainy")],
        )
        for n in (5, 6):
            visit = FormData.objects.get(
                form=self.visit_form, parent=self.site[n],
            )
            self._answer(visit, self.Q_WEATHER_VISIT, options=[RAINY])
        # The registration form does not ask the weather; at the family
        # scope its monitoring forms do.
        self.no_rain = self.filter_out_on(self.REG_ID, "weather", RAINY)

    def test_the_most_recent_answer_wins_across_forms(self):
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=self.no_rain),
            VISITED_SITES - {5},
        )

    def test_a_monitoring_form_scope_reads_that_form_only(self):
        # D-20: on the visit form, only visits count: sites 5 and 6 both
        # reported Rainy there. On the check form, only checks: all Fine.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(self.Q_WEATHER_VISIT, RAINY),
            ),
            VISITED_SITES - {5, 6},
        )
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(self.Q_WEATHER, RAINY),
            ),
            VISITED_SITES,
        )

    def test_a_newer_submission_that_skipped_the_question_does_not_count(self):
        # Site 5 gets a check on 03-01 that left the weather unanswered.
        # The latest submission that ANSWERED is still the Rainy visit,
        # so site 5 stays filtered out.
        self._check(5, datetime(2025, 3, 1), [OPERATIONAL], weather=None)
        self.assertNotIn(
            5, self.sites_on_visit_form(global_criteria=self.no_rain),
        )

    def test_dates_use_the_same_named_date_question_on_each_form(self):
        # The check form gets its own "Date of visit" (same name,
        # `visit_date`), answered with each check's date, except site 4's
        # March check, which records 02-25.
        #
        # Filter out Non-operational, range ends 02-28, by "Date of visit":
        #   site 4: its breakdown is dated 02-25, inside the range -> out
        #   site 3: January breakdown -> out;  site 5: January -> out
        # Using each check's created date instead, site 4's breakdown
        # (03-10) would fall outside the range and site 4 would stay.
        self._question(
            self.check_form, self.Q_CHECK_DATE, "visit_date",
            "Date of visit", type_=QuestionTypes.date,
        )
        for check in FormData.objects.filter(form=self.check_form):
            recorded = check.created.strftime("%Y-%m-%d")
            if check.parent_id == self.site[4].id and check.created.month == 3:
                recorded = "2025-02-25"
            self._answer(
                check, self.Q_CHECK_DATE,
                name=f"{recorded}T00:00:00.000Z",
            )
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(self.Q_STATUS, BROKEN),
                date_question_id=self.Q_VISIT_DATE,
                to_date="2025-02-28",
            ),
            {1, 2, 6, 7, 8, 9},
        )

    def test_answers_to_a_deleted_question_version_are_ignored(self):
        # Form edits recreate questions; old answers keep pointing at the
        # deleted version. Like widgets, the filter reads live questions.
        self.assertNotIn(
            5, self.sites_on_visit_form(global_criteria=self.no_rain),
        )
        Questions.objects.filter(pk=self.Q_WEATHER_VISIT).delete()
        self.assertEqual(
            self.sites_on_visit_form(global_criteria=self.no_rain),
            VISITED_SITES,
        )

    def test_the_visit_form_scope_leaves_out_the_registration(self):
        # "What is the water source?" is on the registration form and,
        # under the same name, on the visit form. Filtered on the visit
        # form, only visit answers count (none here): sites 8 and 9 stay.
        # Filtered on the registration form (family scope, D-20), their
        # registration answers decide and they go.
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(self.Q_SOURCE_SEEN, RAIN),
            ),
            VISITED_SITES,
        )
        self.assertEqual(
            self.sites_on_visit_form(
                global_criteria=self.filter_out(self.Q_SOURCE, RAIN),
            ),
            VISITED_SITES - {8, 9},
        )
