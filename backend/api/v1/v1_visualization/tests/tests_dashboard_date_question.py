import json
from datetime import datetime

from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.dashboard_functions import (
    validate_dashboard_payload,
)
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.tests.global_filter_mixin import (
    BROKEN,
    OPERATIONAL,
    GlobalFilterTestMixin,
)

# VIZ-027 D-18 (backend BE-8): the dashboard's date question is "Date of
# visit" (700203, on the visit form). The check form asks it too, under
# the same name, so every widget can be dated by it.
#
# On top of the fixture table in global_filter_mixin.py, each check records
# its own date as "Date of visit", except site 4's March check (created
# 03-10), which records 02-25. Checks by "Date of visit":
#
#   site 3   01-10 Non-operational, 03-10 Operational
#   site 4   01-10 Operational,     02-25 Non-operational
#   site 5   01-20 Non-operational
#   others   03-10
#
# Visits are all dated 02-15 (site 4: also 02-20). Registrations were
# created 2025-01-01, except site 8 (2024-12-01).

Q_CHECK_DATE = 700303
LATE_FEBRUARY = {"from_date": "2025-02-20", "to_date": "2025-02-28"}


class DateQuestionFixtureMixin(GlobalFilterTestMixin):
    def setUp(self):
        super().setUp()
        self._question(
            self.check_form, Q_CHECK_DATE, "visit_date",
            "Date of visit", type_=QuestionTypes.date,
        )
        for check in FormData.objects.filter(form=self.check_form):
            recorded = check.created.strftime("%Y-%m-%d")
            if check.parent_id == self.site[4].id and check.created.month == 3:
                recorded = "2025-02-25"
            self._answer(
                check, Q_CHECK_DATE, name=f"{recorded}T00:00:00.000Z",
            )
        self.number_by_id = {site.id: n for n, site in self.site.items()}

    def sites_on_check_form(self, **params):
        """Water points a "Quick status check" chart draws (latest check)."""
        response = self.values(
            form_id=self.CHECK_ID, group_by="parent_id", **params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(response.json()["labels"])

    def map_sites(self, form_id, **params):
        response = self.client.get(
            f"/api/v1/maps/geolocation/{form_id}", params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(row["name"] for row in response.json())

    def broken_colour_sites(self, **params):
        """Water points the status colour marks Non-operational."""
        formula = {
            "buckets": [{
                "value": "broken",
                "label": "Broken",
                "all_of": [{
                    "question_id": self.Q_STATUS,
                    "op": "option_equals",
                    "value": BROKEN,
                }],
            }],
            "default": {"value": "other", "label": "Other"},
        }
        response = self.client.get(
            "/api/v1/visualization/values/formula",
            {
                "form_id": self.CHECK_ID,
                "group_by": "parent_id",
                "formula": json.dumps(formula),
                **params,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        return {
            self.number_by_id[row["group"]]
            for row in response.json()["data"]
            if row["label"] == "broken"
        }


@override_settings(USE_TZ=False, TEST_ENV=True)
class DashboardDateQuestionTestCase(DateQuestionFixtureMixin, APITestCase):
    """One date question for the whole dashboard, matched by name on each
    widget's form (D-18)."""

    by_visit_date = {"date_question_id": GlobalFilterTestMixin.Q_VISIT_DATE}

    def test_a_visit_form_widget_counts_by_its_own_date(self):
        # Unchanged: the question is on this form.
        self.assertEqual(
            self.sites_on_visit_form(**self.by_visit_date, **LATE_FEBRUARY),
            {4},
        )

    def test_a_check_form_widget_counts_by_its_same_named_date(self):
        # Only site 4's check is dated inside late February (02-25). By
        # submission date no check is (January and March), and matching
        # the visit form's id literally finds no check answers at all.
        self.assertEqual(
            self.sites_on_check_form(**self.by_visit_date, **LATE_FEBRUARY),
            {4},
        )

    def test_a_registration_widget_falls_back_to_the_submission_date(self):
        # The registration form does not ask "Date of visit", so it is
        # bounded by when each water point was registered, not emptied.
        # (The fixture's 2025-01-01 is stored as 2024-12-31 23:00: the
        # tests run in Fiji time, on summer time in January. The bound
        # sits between that and site 8's 2024-12-01.) The range ends
        # before any monitoring, which would also count (D-23): site 8's
        # visit is dated 02-15.
        self.assertEqual(
            self.sites_on_registration(
                **self.by_visit_date,
                from_date="2024-12-15",
                to_date="2025-01-05",
            ),
            set(range(1, 11)) - {8},
        )

    def test_the_global_filter_keeps_the_dashboard_date(self):
        # Registration widget, range up to 02-28, filter out
        # Non-operational. The widget itself falls back to the
        # registration date (every site was registered by then), but the
        # filter still judges each site's latest check by "Date of visit":
        #   site 3 (01-10 broken) out, site 4 (02-25 broken) out,
        #   site 5 (01-20 broken) out.
        # Judged by submission date instead, site 4's latest check in range
        # would be January's Operational one and site 4 would stay.
        self.assertEqual(
            self.sites_on_registration(
                **self.by_visit_date,
                to_date="2025-02-28",
                global_criteria=self.filter_out(self.Q_STATUS, BROKEN),
            ),
            {1, 2, 6, 7, 8, 9, 10},
        )

    def test_the_map_follows_the_dashboard_date(self):
        # Water point pins, bounded by their checks: site 4 only.
        self.assertEqual(
            self.map_sites(
                self.REG_ID,
                include_monitoring="true",
                monitoring_form_id=self.CHECK_ID,
                **self.by_visit_date,
                **LATE_FEBRUARY,
            ),
            {4},
        )

    def test_the_map_without_a_date_question_is_unchanged(self):
        # By submission date, no check falls in late February.
        self.assertEqual(
            self.map_sites(
                self.REG_ID,
                include_monitoring="true",
                monitoring_form_id=self.CHECK_ID,
                **LATE_FEBRUARY,
            ),
            set(),
        )

    def test_the_map_without_a_monitoring_form_dates_every_child(self):
        # include_monitoring with no monitoring_form_id: any child counts.
        # From 02-21: by "Date of visit", only site 4's check (02-25) is
        # in range. By submission date nothing is: the last visit is
        # 02-20, and the checks were submitted in January and March.
        after_visits = {"from_date": "2025-02-21", "to_date": "2025-02-28"}
        self.assertEqual(
            self.map_sites(
                self.REG_ID, include_monitoring="true",
                **self.by_visit_date, **after_visits,
            ),
            {4},
        )
        self.assertEqual(
            self.map_sites(
                self.REG_ID, include_monitoring="true", **after_visits,
            ),
            set(),
        )

    def test_the_table_is_dated_on_its_monitoring_form(self):
        # Checks dated up to 02-28: sites 3, 4, 5. One per page, so the
        # paging link must carry the id the client sent, not the check
        # form's copy (a public dashboard only allows the former).
        response = self.client.get(
            f"/api/v1/visualization/escalation/{self.REG_ID}",
            {
                "monitoring_form_id": self.CHECK_ID,
                "columns": "name:parent_name",
                "page_size": 1,
                "to_date": "2025-02-28",
                **self.by_visit_date,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertIn(f"date_question_id={self.Q_VISIT_DATE}", body["next"])
        self.assertNotIn(str(Q_CHECK_DATE), body["next"])

    def test_a_date_question_without_a_range_drops_nothing(self):
        # Site 6 gets a newer check (03-15, Operational) that skipped
        # "Date of visit". With no range, the date question bounds
        # nothing: that check is site 6's latest, so filtering out
        # Non-operational keeps site 6.
        self._check(6, datetime(2025, 3, 15), [OPERATIONAL])
        self.assertEqual(
            self.sites_on_registration(
                **self.by_visit_date,
                global_criteria=self.filter_out(self.Q_STATUS, BROKEN),
            ),
            {1, 2, 3, 6, 7, 8, 9, 10},
        )

    def test_a_replaced_date_question_still_dates_by_its_name(self):
        # A form edit soft-deletes "Date of visit" (700203); the published
        # dashboard keeps that id. The name still reaches the check
        # form's copy instead of falling back to the submission date.
        Questions.objects.filter(pk=self.Q_VISIT_DATE).delete()
        self.assertEqual(
            self.sites_on_check_form(**self.by_visit_date, **LATE_FEBRUARY),
            {4},
        )

    def test_the_status_colours_follow_the_dashboard_date(self):
        # Site 4's check dated 02-25 says Non-operational.
        self.assertEqual(
            self.broken_colour_sites(**self.by_visit_date, **LATE_FEBRUARY),
            {4},
        )
        self.assertEqual(self.broken_colour_sites(**LATE_FEBRUARY), set())


@override_settings(USE_TZ=False)
class DashboardDateQuestionSaveTestCase(GlobalFilterTestMixin, APITestCase):
    """`default_filters.date.date_question` is checked on save (D-18)."""

    def setUp(self):
        super().setUp()
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.registration,
            created_by=self.user,
        )

    def check(self, date_question):
        return validate_dashboard_payload(
            {
                "name": "Water Points",
                "widgets": [],
                "default_filters": {
                    "date": {"enabled": True, "date_question": date_question},
                },
            },
            self.user,
            dashboard=self.dashboard,
        )

    def test_results(self):
        refused = "refused"
        results = {}
        for label, date_question in [
            ("visit date", self.Q_VISIT_DATE),
            ("none", None),
            ("number question", self.Q_HOUSEHOLDS),
            ("option question", self.Q_STATUS),
            ("unknown question", 999999),
            ("string id", str(self.Q_VISIT_DATE)),
        ]:
            error = self.check(date_question)
            results[label] = (
                refused
                if error and error.get("field")
                == "default_filters.date.date_question"
                else error
            )
        self.assertEqual(results, {
            "visit date": None,
            "none": None,
            "number question": refused,
            "option question": refused,
            "unknown question": refused,
            "string id": refused,
        })

    def test_a_replaced_date_question_stays_savable(self):
        # The stored id was soft-deleted by a form edit and a live
        # "Date of visit" took its place: the dashboard still saves.
        Questions.objects.filter(pk=self.Q_VISIT_DATE).delete()
        self.assertIsNotNone(self.check(self.Q_VISIT_DATE))
        self._question(
            self.visit_form, 700206, "visit_date", "Date of visit",
            type_=QuestionTypes.date,
        )
        self.assertIsNone(self.check(self.Q_VISIT_DATE))

    def test_another_familys_date_question_is_refused(self):
        school_date = self._question(
            self.school, 710102, "visit_date", "Date of visit",
            type_=QuestionTypes.date,
        )
        error = self.check(school_date.id)
        self.assertIsNotNone(error)
        self.assertEqual(
            error.get("field"), "default_filters.date.date_question",
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class PublicDashboardDateQuestionTestCase(
    DateQuestionFixtureMixin, APITestCase
):
    """An anonymous viewer: the published date question is allowed, and
    resolved per form on the server; the client never names the check
    form's copy."""

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
                "default_filters": {
                    "date": {
                        "enabled": True,
                        "date_question": self.Q_VISIT_DATE,
                    },
                },
                "widgets": [{
                    "id": 1,
                    "order": 1,
                    "type": "bar",
                    "col_span": 12,
                    "title": "Checks",
                    "color": None,
                    "form": self.CHECK_ID,
                    "question": self.Q_STATUS,
                    "config": {"group_by": "option"},
                }],
            },
        )
        self.client.credentials()

    def status_chart(self, date_question_id):
        return self.client.get(self.VALUES_URL, {
            "form_id": self.CHECK_ID,
            "question_id": self.Q_STATUS,
            "group_by": "option",
            "dashboard_slug": "water-points",
            "date_question_id": date_question_id,
            **LATE_FEBRUARY,
        })

    def test_the_published_date_question_dates_the_check_form(self):
        # Site 4's check dated 02-25: one Non-operational.
        response = self.status_chart(self.Q_VISIT_DATE)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            self.by_option(response),
            {"operational": 0, "non_operational": 1},
        )

    def test_another_date_question_is_refused(self):
        response = self.status_chart(Q_CHECK_DATE)
        self.assertEqual(response.status_code, 404, response.content)

    def test_the_public_map_accepts_only_the_published_date_question(self):
        def pins(date_question_id):
            return self.client.get(
                f"/api/v1/maps/geolocation/{self.REG_ID}",
                {
                    "include_monitoring": "true",
                    "monitoring_form_id": self.CHECK_ID,
                    "dashboard_slug": "water-points",
                    "date_question_id": date_question_id,
                    **LATE_FEBRUARY,
                },
            )

        response = pins(self.Q_VISIT_DATE)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            self.site_numbers(row["name"] for row in response.json()), {4},
        )
        self.assertEqual(pins(Q_CHECK_DATE).status_code, 404)
