from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.dashboard_builder_serializers import (
    serialize_sources,
)
from api.v1.v1_visualization.dashboard_functions import (
    validate_dashboard_payload,
)
from api.v1.v1_visualization.dashboard_snapshot import build_snapshot
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.public_scope import allowlist_from
from api.v1.v1_visualization.tests.global_filter_mixin import (
    BROKEN,
    FINE,
    OPERATIONAL,
    RAINY,
    YES,
    GlobalFilterTestMixin,
)


@override_settings(USE_TZ=False)
class FilterQuestionsConfigTestCase(GlobalFilterTestMixin, APITestCase):
    """Which questions the filter bar offers: `default_filters.questions`.

    The author picks them in the builder; they are checked on save,
    copied into the snapshot on publish, and become what a public viewer
    may filter on (D-6, D-7).
    """

    def setUp(self):
        super().setUp()
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.registration,
            created_by=self.user,
        )

    def check(self, questions):
        return validate_dashboard_payload(
            {
                "name": "Water Points",
                "widgets": [],
                "default_filters": {"questions": questions},
            },
            self.user,
            dashboard=self.dashboard,
        )

    def assert_refused(self, questions):
        error = self.check(questions)
        self.assertIsNotNone(error, "payload was accepted")
        self.assertTrue(
            error.get("field", "").startswith("default_filters.questions"),
            error,
        )

    # ── saving (D-6) ──

    def test_option_questions_of_the_family_are_accepted(self):
        # "Is the infrastructure operational?" and "What is the water
        # source?": both option questions on water point forms.
        self.assertIsNone(self.check([
            {"form": self.CHECK_ID, "name": "infrastructure_status"},
            {"form": self.REG_ID, "name": "water_source"},
        ]))

    def test_dashboard_without_filter_questions_still_saves(self):
        self.assertIsNone(validate_dashboard_payload(
            {"name": "Water Points", "widgets": [], "default_filters": {}},
            self.user,
            dashboard=self.dashboard,
        ))

    def test_school_question_is_refused(self):
        # "Does the school have a toilet?" belongs to another family.
        self.assert_refused(
            [{"form": self.SCHOOL_ID, "name": "has_toilet"}],
        )

    def test_number_question_is_refused(self):
        # "How many households...?" has no options to filter out.
        self.assert_refused(
            [{"form": self.VISIT_ID, "name": "households"}],
        )

    def test_wrong_form_for_the_question_is_refused(self):
        # The status question is on the check form, not the visit form.
        self.assert_refused(
            [{"form": self.VISIT_ID, "name": "infrastructure_status"}],
        )

    def test_unknown_question_is_refused(self):
        self.assert_refused(
            [{"form": self.CHECK_ID, "name": "no_such_question"}],
        )

    def test_ids_must_be_integers(self):
        # "700301" would be stored as a string and then match nothing at
        # Publish, silently dropping the filter.
        self.assert_refused(
            [{"form": str(self.CHECK_ID), "name": "infrastructure_status"}],
        )

    def test_questions_must_be_a_list(self):
        self.assert_refused(
            {"form": self.CHECK_ID, "name": "infrastructure_status"},
        )

    def test_a_name_at_the_family_scope_is_accepted(self):
        # D-20: the registration form does not ask the weather, but at the
        # family scope its monitoring forms do.
        self.assertIsNone(
            self.check([{"form": self.REG_ID, "name": "weather"}]),
        )

    def test_a_name_with_a_colon_is_refused(self):
        # The grammar splits on `:`; such a name could not be sent back.
        self._question(
            self.check_form, 700304, "pump:status", "Pump status",
            [(OPERATIONAL, "Operational"), (BROKEN, "Broken")],
        )
        self.assert_refused([{"form": self.CHECK_ID, "name": "pump:status"}])

    # ── publishing (D-7) ──

    def test_snapshot_carries_the_question_and_its_options(self):
        # A public viewer cannot read the form, so the filter bar's label
        # and choices travel in the snapshot.
        self.dashboard.default_filters = {
            "questions": [
                {"form": self.CHECK_ID, "name": "infrastructure_status"},
            ],
        }
        self.dashboard.save()
        entry = build_snapshot(self.dashboard)["default_filters"][
            "questions"
        ][0]
        self.assertEqual(entry["form"], self.CHECK_ID)
        self.assertEqual(entry["name"], "infrastructure_status")
        self.assertEqual(
            entry.get("label"), "Is the infrastructure operational?",
        )
        self.assertEqual(
            entry.get("options"),
            [
                {"value": "operational", "label": "Operational"},
                {"value": "non_operational", "label": "Non-operational"},
            ],
        )

    def test_snapshot_merges_the_family_scope(self):
        # D-14, D-20: the visit form also asks the weather, same name. It
        # labels `fine` "Clear sky" and has a value the check form lacks.
        # At the family scope the options are merged, visit form first
        # (the registration form does not ask it; forms by id):
        #   value    visit form   check form   filter bar
        #   fine     Clear sky    Fine         Clear sky / Fine
        #   rainy    Rainy        Rainy        Rainy
        #   stormy   Stormy       -            Stormy
        # On the check form alone, only the check form's options.
        self._question(
            self.visit_form, 700205, "weather",
            "What is the weather during the visit?",
            [(FINE, "Clear sky"), (RAINY, "Rainy"), ("stormy", "Stormy")],
        )
        self.dashboard.default_filters = {
            "questions": [
                {"form": self.REG_ID, "name": "weather"},
                {"form": self.CHECK_ID, "name": "weather"},
            ],
        }
        self.dashboard.save()
        family, check = build_snapshot(self.dashboard)["default_filters"][
            "questions"
        ]
        self.assertEqual(
            family.get("label"), "What is the weather during the visit?",
        )
        self.assertEqual(
            family.get("options"),
            [
                {"value": "fine", "label": "Clear sky / Fine"},
                {"value": "rainy", "label": "Rainy"},
                {"value": "stormy", "label": "Stormy"},
            ],
        )
        self.assertEqual(
            check.get("label"), "What is the weather during the check?",
        )
        self.assertEqual(
            check.get("options"),
            [
                {"value": "fine", "label": "Fine"},
                {"value": "rainy", "label": "Rainy"},
            ],
        )

    # ── public viewers (§7 Public dashboards) ──

    def test_public_viewers_may_filter_on_the_listed_question_only(self):
        self.dashboard.published_config = {
            "default_filters": {
                "questions": [
                    {"form": self.CHECK_ID, "name": "infrastructure_status"},
                ],
            },
            "widgets": [],
        }
        allowed = allowlist_from(self.dashboard)
        self.assertTrue(allowed.permits_filter(
            self.CHECK_ID, "infrastructure_status",
        ))
        self.assertFalse(allowed.permits_filter(self.CHECK_ID, "weather"))
        # The same name on another form is another filter (D-20).
        self.assertFalse(allowed.permits_filter(
            self.REG_ID, "infrastructure_status",
        ))

    def test_malformed_filter_entries_narrow_the_allowlist(self):
        self.dashboard.published_config = {
            "default_filters": {"questions": [
                "junk",
                {"form": "abc", "name": "infrastructure_status"},
                {"form": self.CHECK_ID, "name": 5},
                {"form": self.CHECK_ID, "name": "infrastructure_status"},
            ]},
            "widgets": [],
        }
        self.assertEqual(
            allowlist_from(self.dashboard).filter_questions,
            {(self.CHECK_ID, "infrastructure_status")},
        )

    # ── builder (D-8, A4) ──

    def test_builder_sources_carry_question_names(self):
        # The builder warns when "What is the water source?" is asked on
        # both the registration and the visit form. It matches on name.
        names = {
            question["id"]: question.get("name")
            for form in serialize_sources(self.dashboard, self.user)["forms"]
            for question in form["questions"]
        }
        self.assertEqual(names[self.Q_SOURCE], "water_source")
        self.assertEqual(names[self.Q_SOURCE_SEEN], "water_source")


@override_settings(USE_TZ=False)
class PublicViewerFilterTestCase(GlobalFilterTestMixin, APITestCase):
    """An anonymous viewer of a public dashboard.

    The published dashboard offers one filter question, "Is the
    infrastructure operational?", and has one chart, "Were you able to
    take a water sample?".
    """

    def setUp(self):
        super().setUp()
        # Same tenant wiring as tests_public_dashboard_access: the
        # anonymous path resolves the single seeded tenant, so the
        # dashboard, its forms and the root administration sit on it.
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
                    "questions": [{
                        "form": self.CHECK_ID,
                        "name": "infrastructure_status",
                    }],
                },
                "widgets": [{
                    "id": 1,
                    "order": 1,
                    "type": "bar",
                    "col_span": 12,
                    "title": "Sample taken",
                    "color": None,
                    "form": self.VISIT_ID,
                    "question": self.Q_SAMPLE,
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

    def test_filtering_out_non_operational_works_for_the_public(self):
        # Yes (latest visit) was 8: sites 1-3 and 5-9. Broken 5 and 6
        # leave -> 6. Site 4 leaves too, but its latest visit said No.
        response = self.sample_chart(self.filter_out(self.Q_STATUS, BROKEN))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 6)

    def test_a_question_the_dashboard_does_not_offer_is_refused(self):
        # "What is the weather during the check?" is in the family but
        # not in the filter bar, so a public caller may not use it.
        response = self.sample_chart(self.filter_out(self.Q_WEATHER, FINE))
        self.assertEqual(response.status_code, 404, response.content)

    def test_the_same_name_at_another_scope_is_refused(self):
        # D-20: the bar offers the status on the check form. The family
        # scope of the same name is another filter, not offered.
        response = self.sample_chart(self.filter_out_on(
            self.REG_ID, "infrastructure_status", BROKEN,
        ))
        self.assertEqual(response.status_code, 404, response.content)

    def test_a_widget_question_cannot_be_used_as_a_filter(self):
        # "Were you able to take a water sample?" is the chart's own
        # question, so a public caller may read it, but the filter bar does
        # not offer it: global_criteria may name filter questions only.
        response = self.sample_chart(self.filter_out(self.Q_SAMPLE, YES))
        self.assertEqual(response.status_code, 404, response.content)

    def test_a_bracketed_key_is_ignored_not_trusted(self):
        # Review finding (HIGH): DRF's ListField also reads
        # `global_criteria[0]=...`, which check_ids never saw. Nothing reads
        # that key now, so it cannot sneak in an unlisted question: the
        # chart is exactly the unfiltered one (Yes 8).
        response = self.client.get(self.VALUES_URL, {
            "form_id": self.VISIT_ID,
            "question_id": self.Q_SAMPLE,
            "group_by": "option",
            "dashboard_slug": "water-points",
            "global_criteria[0]": self.filter_out(self.Q_WEATHER, FINE)[0],
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"][0]["value"], 8)

    def test_a_form_outside_the_dashboard_is_a_404_not_a_family_hint(self):
        # Review finding (MEDIUM): parsing used to run in the serializer,
        # before scoping, and answered "not in this form family" for any
        # form id. Now the form is refused first.
        response = self.client.get(self.VALUES_URL, {
            "form_id": self.SCHOOL_ID,
            "dashboard_slug": "water-points",
            "global_criteria": self.filter_out(self.Q_STATUS, BROKEN),
        })
        self.assertEqual(response.status_code, 404, response.content)


@override_settings(USE_TZ=False)
class DeletedFilterQuestionTestCase(GlobalFilterTestMixin, APITestCase):
    """A filter question deleted after Publish (decided 2026-10-06).

    Filter bar offers "Is the infrastructure operational?" and "What is
    the water source?". Then the status question is deleted in the form
    builder.
    Expect: the next read of the dashboard offers only the water source
    filter, so no viewer can send a filter the backend would refuse.
    """

    def test_a_deleted_filter_question_leaves_the_filter_bar(self):
        Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.registration,
            created_by=self.user,
            status=DashboardStatus.published,
            published_config={
                "default_filters": {"questions": [
                    {"form": self.CHECK_ID, "name": "infrastructure_status"},
                    {"form": self.REG_ID, "name": "water_source"},
                ]},
                "widgets": [],
            },
        )

        def offered():
            response = self.client.get("/api/v1/dashboards/water-points")
            self.assertEqual(response.status_code, 200, response.content)
            return [
                q["name"]
                for q in response.json()["default_filters"]["questions"]
            ]

        self.assertEqual(offered(), ["infrastructure_status", "water_source"])
        Questions.objects.filter(pk=self.Q_STATUS).delete()
        self.assertEqual(offered(), ["water_source"])

    def test_a_family_filter_asked_only_on_a_monitoring_form(self):
        # D-20: the registration form does not ask the weather; at the
        # family scope the check form does. Offered while the check form
        # lives, dropped once it is deleted.
        Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.registration,
            created_by=self.user,
            status=DashboardStatus.published,
            published_config={
                "default_filters": {"questions": [
                    {"form": self.REG_ID, "name": "weather"},
                ]},
                "widgets": [],
            },
        )

        def offered():
            response = self.client.get("/api/v1/dashboards/water-points")
            self.assertEqual(response.status_code, 200, response.content)
            return response.json()["default_filters"]["questions"]

        self.assertEqual(
            offered(), [{"form": self.REG_ID, "name": "weather"}],
        )
        Forms.objects.filter(pk=self.CHECK_ID).delete()
        self.assertEqual(offered(), [])

    def test_a_filter_on_a_deleted_form_leaves_the_filter_bar(self):
        # The whole Quick status check form is deleted: its question is
        # no longer filterable either.
        Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.registration,
            created_by=self.user,
            status=DashboardStatus.published,
            published_config={
                "default_filters": {"questions": [
                    {"form": self.CHECK_ID, "name": "infrastructure_status"},
                ]},
                "widgets": [],
            },
        )
        Forms.objects.filter(pk=self.CHECK_ID).delete()
        response = self.client.get("/api/v1/dashboards/water-points")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["default_filters"]["questions"], [],
        )
