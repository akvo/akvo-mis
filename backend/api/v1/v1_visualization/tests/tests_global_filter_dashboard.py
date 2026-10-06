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
            {"question": self.Q_STATUS, "form": self.CHECK_ID},
            {"question": self.Q_SOURCE, "form": self.REG_ID},
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
            [{"question": self.Q_TOILET, "form": self.SCHOOL_ID}],
        )

    def test_number_question_is_refused(self):
        # "How many households...?" has no options to filter out.
        self.assert_refused(
            [{"question": self.Q_HOUSEHOLDS, "form": self.VISIT_ID}],
        )

    def test_wrong_form_for_the_question_is_refused(self):
        # The status question is on the check form, not the visit form.
        self.assert_refused(
            [{"question": self.Q_STATUS, "form": self.VISIT_ID}],
        )

    def test_unknown_question_is_refused(self):
        self.assert_refused([{"question": 999999, "form": self.CHECK_ID}])

    def test_ids_must_be_integers(self):
        # "700301" would be stored as a string and then match nothing at
        # Publish, silently dropping the filter.
        self.assert_refused(
            [{"question": str(self.Q_STATUS), "form": self.CHECK_ID}],
        )

    def test_questions_must_be_a_list(self):
        self.assert_refused({"question": self.Q_STATUS, "form": self.CHECK_ID})

    # ── publishing (D-7) ──

    def test_snapshot_carries_the_question_and_its_options(self):
        # A public viewer cannot read the form, so the filter bar's label
        # and choices travel in the snapshot.
        self.dashboard.default_filters = {
            "questions": [{"question": self.Q_STATUS, "form": self.CHECK_ID}],
        }
        self.dashboard.save()
        entry = build_snapshot(self.dashboard)["default_filters"][
            "questions"
        ][0]
        self.assertEqual(entry["question"], self.Q_STATUS)
        self.assertEqual(entry["form"], self.CHECK_ID)
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

    def test_snapshot_merges_a_name_group(self):
        # D-14: the visit form also asks the weather, same name. It labels
        # `fine` "Clear sky" and has a value the check form lacks.
        #   value    check form   visit form   filter bar
        #   fine     Fine         Clear sky    Fine / Clear sky
        #   rainy    Rainy        Rainy        Rainy
        #   stormy   -            Stormy       Stormy
        self._question(
            self.visit_form, 700205, "weather",
            "What is the weather during the visit?",
            [(FINE, "Clear sky"), (RAINY, "Rainy"), ("stormy", "Stormy")],
        )
        self.dashboard.default_filters = {
            "questions": [
                {"question": self.Q_WEATHER, "form": self.CHECK_ID},
            ],
        }
        self.dashboard.save()
        entry = build_snapshot(self.dashboard)["default_filters"][
            "questions"
        ][0]
        self.assertEqual(
            entry.get("label"), "What is the weather during the check?",
        )
        self.assertEqual(
            entry.get("options"),
            [
                {"value": "fine", "label": "Fine / Clear sky"},
                {"value": "rainy", "label": "Rainy"},
                {"value": "stormy", "label": "Stormy"},
            ],
        )

    # ── public viewers (§7 Public dashboards) ──

    def test_public_viewers_may_filter_on_the_listed_question_only(self):
        self.dashboard.published_config = {
            "default_filters": {
                "questions": [
                    {"question": self.Q_STATUS, "form": self.CHECK_ID},
                ],
            },
            "widgets": [],
        }
        allowed = allowlist_from(self.dashboard)
        self.assertTrue(allowed.permits_filter_question(self.Q_STATUS))
        self.assertFalse(allowed.permits_filter_question(self.Q_WEATHER))

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
                    "questions": [
                        {"question": self.Q_STATUS, "form": self.CHECK_ID},
                    ],
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
                    {"question": self.Q_STATUS, "form": self.CHECK_ID},
                    {"question": self.Q_SOURCE, "form": self.REG_ID},
                ]},
                "widgets": [],
            },
        )

        def offered():
            response = self.client.get("/api/v1/dashboards/water-points")
            self.assertEqual(response.status_code, 200, response.content)
            return [
                q["question"]
                for q in response.json()["default_filters"]["questions"]
            ]

        self.assertEqual(offered(), [self.Q_STATUS, self.Q_SOURCE])
        Questions.objects.filter(pk=self.Q_STATUS).delete()
        self.assertEqual(offered(), [self.Q_SOURCE])

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
                    {"question": self.Q_STATUS, "form": self.CHECK_ID},
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
