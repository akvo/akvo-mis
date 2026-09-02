import json

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False)
class PublicEndpointAccessTestCase(TestCase, ProfileTestHelperMixin):
    """An anonymous caller may only ask what the snapshot names."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_public@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        # create_user() never assigns a tenant, so it defaults to
        # None. resolve_view_scope's anonymous path resolves the
        # single-host tenant through public_tenant(), which returns
        # the one real Tenant row the seeders leave behind — so the
        # dashboard has to sit on that same row or no anonymous
        # lookup will ever find it.
        self.user.tenant = Tenant.objects.get()
        self.user.save()
        self.root = Forms.objects.get(pk=6001)
        # form_seeder --test leaves forms tenant-less, but
        # tenant_scoped_forms() filters by tenant once resolve_view_
        # scope hands back a concrete tenant (which it always does for
        # an anonymous, single-host request). Without this the form
        # itself 404s even once the dashboard lookup succeeds.
        self.root.tenant = self.user.tenant
        self.root.save()
        # Form 5 ("Test Form 5") is real, seeded by
        # form_seeder --test, and never named in this
        # dashboard's snapshot. Tenant-scoped the same way as
        # self.root: if it weren't, a form check_ids regression
        # would still 404 via tenant_scoped_forms downstream, and
        # test_a_form_not_on_the_dashboard_is_404 would pass for
        # the wrong reason.
        self.off_dashboard_form = Forms.objects.get(pk=5)
        self.off_dashboard_form.tenant = self.user.tenant
        self.off_dashboard_form.save()
        # Same gap, one level up: resolve_default_administration_id
        # falls back to the tenant's root administration, and that
        # root is tenant-less coming out of the seeder too.
        Administration.objects.filter(parent__isnull=True).update(
            tenant=self.user.tenant
        )
        # A second, real question on the root form that the
        # dashboard's snapshot never references. An id that does not
        # exist at all (e.g. 600199) can't stand in for "on the form
        # but off the dashboard": ValuesFilterSerializer.validate()
        # already 400s a question_id that isn't on form_id, before
        # check_ids ever runs, so it would only prove the serializer
        # still works — not that check_ids does.
        self.off_dashboard_question = Questions.objects.create(
            id=600105,
            form=self.root,
            question_group=Questions.objects.get(
                pk=600102
            ).question_group,
            order=5,
            label="Off dashboard metric",
            name="off_dashboard_metric",
            type=QuestionTypes.number,
        )
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            tenant=self.user.tenant,
            created_by=self.user,
            status=DashboardStatus.published,
            is_public=True,
            published_config={
                "default_filters": {},
                "widgets": [
                    {
                        "id": 1,
                        "order": 1,
                        "type": "bar",
                        "col_span": 12,
                        "title": "By status",
                        "color": None,
                        "form": 6001,
                        "question": 600102,
                        "config": {"group_by": "option"},
                    },
                    # Names form 6002 on the snapshot so an escalation
                    # request may use it as monitoring_form_id. No
                    # question here: the escalation tests below only
                    # need columns=name:parent_name (no qid) for the
                    # allowed case, and reuse the already-off-dashboard
                    # 600105 for the negative ones.
                    {
                        "id": 2,
                        "order": 2,
                        "type": "table",
                        "col_span": 12,
                        "title": "Escalation",
                        "color": None,
                        "form": 6002,
                        "question": None,
                        "config": {},
                    },
                ],
            },
        )

    def values(self, **params):
        params.setdefault("dashboard_slug", "water-points")
        return self.client.get("/api/v1/visualization/values", params)

    def escalation(self, **params):
        params.setdefault("dashboard_slug", "water-points")
        return self.client.get(
            "/api/v1/visualization/escalation/6001", params
        )

    def formula(self, **params):
        params.setdefault("dashboard_slug", "water-points")
        params.setdefault("group_by", "parent_id")
        return self.client.get(
            "/api/v1/visualization/values/formula", params
        )

    def geo(self, form_id, **params):
        params.setdefault("dashboard_slug", "water-points")
        return self.client.get(
            "/api/v1/maps/geolocation/{0}".format(form_id), params
        )

    def bucket_formula(self, question_id):
        return json.dumps({
            "buckets": [{
                "value": "Yes",
                "label": "Yes",
                "all_of": [{
                    "question_id": question_id,
                    "op": "option_equals",
                    "value": "Yes",
                }],
            }],
            "default": {"value": "_no_info", "label": "_no_info"},
        })

    def test_an_allowed_form_and_question_answer(self):
        res = self.values(form_id=6001, question_id=600102)
        self.assertEqual(res.status_code, 200)

    def test_a_form_not_on_the_dashboard_is_404(self):
        # off_dashboard_form (id 5) is real, tenant-scoped to
        # this test's tenant, and not named anywhere in this
        # dashboard's snapshot. No question_id: 6002 is now on
        # the dashboard too (added for the escalation tests
        # below), so a form/question pair built on 6002 would
        # 404 on the question branch of check_ids and leave the
        # form branch this test exists to guard unexercised.
        res = self.values(form_id=self.off_dashboard_form.id)
        self.assertEqual(res.status_code, 404)

    def test_a_question_not_on_the_dashboard_is_404(self):
        res = self.values(form_id=6001, question_id=600105)
        self.assertEqual(res.status_code, 404)

    def test_a_criteria_question_not_on_the_dashboard_is_404(self):
        res = self.values(
            form_id=6001,
            question_id=600102,
            criteria="option_equals:600105:Yes",
        )
        self.assertEqual(res.status_code, 404)

    def test_a_date_question_not_on_the_dashboard_is_404(self):
        res = self.values(
            form_id=6001, question_id=600102, date_question_id=600199
        )
        self.assertEqual(res.status_code, 404)

    def test_no_slug_is_404(self):
        res = self.client.get(
            "/api/v1/visualization/values",
            {"form_id": 6001, "question_id": 600102},
        )
        self.assertEqual(res.status_code, 404)

    def test_no_slug_with_a_bogus_form_id_is_404_not_400(self):
        """The scope check must run before the serializer.

        ValuesFilterSerializer.validate_form_id issues a tenant-
        unscoped existence query. If that ran before resolve_view_
        scope, an anonymous caller with no dashboard could tell
        "form not found" (400) from "no public dashboard" (404), and
        enumerate another workspace's form ids one guess at a time —
        no aggregates leak, but the schema does.
        """
        res = self.client.get(
            "/api/v1/visualization/values", {"form_id": 999999}
        )
        self.assertEqual(res.status_code, 404)

    def test_an_allowed_escalation_request_answers(self):
        res = self.escalation(
            monitoring_form_id=6002, columns="name:parent_name"
        )
        self.assertEqual(res.status_code, 200)

    def test_an_escalation_monitoring_form_not_on_the_dashboard_is_404(
        self,
    ):
        res = self.escalation(
            monitoring_form_id=9999, columns="name:parent_name"
        )
        self.assertEqual(res.status_code, 404)

    def test_an_escalation_column_question_not_on_the_dashboard_is_404(
        self,
    ):
        res = self.escalation(
            monitoring_form_id=6002,
            columns="measurement:answer:600105",
        )
        self.assertEqual(res.status_code, 404)

    def test_an_escalation_criteria_question_not_on_the_dashboard_is_404(
        self,
    ):
        res = self.escalation(
            monitoring_form_id=6002,
            columns="name:parent_name",
            criteria="option_equals:600105:Yes",
        )
        self.assertEqual(res.status_code, 404)

    def test_a_private_dashboard_serves_nothing(self):
        self.dashboard.is_public = False
        self.dashboard.save()
        res = self.values(form_id=6001, question_id=600102)
        self.assertEqual(res.status_code, 404)

    def test_a_draft_dashboard_serves_nothing(self):
        self.dashboard.status = DashboardStatus.draft
        self.dashboard.save()
        res = self.values(form_id=6001, question_id=600102)
        self.assertEqual(res.status_code, 404)

    def test_formula_with_an_allowed_question(self):
        res = self.formula(
            form_id=6001, formula=self.bucket_formula(600102)
        )
        self.assertEqual(res.status_code, 200)

    def test_formula_smuggling_a_foreign_question_is_404(self):
        res = self.formula(
            form_id=6001, formula=self.bucket_formula(600199)
        )
        self.assertEqual(res.status_code, 404)

    def test_formula_on_a_foreign_form_is_404(self):
        # off_dashboard_form (id 5) is real and tenant-scoped to
        # this test's tenant (see setUp), so a check_ids regression
        # would still reach tenant_scoped_forms and 404 there
        # instead -- a bogus id like 9999 would make that
        # indistinguishable. 6002 cannot be used here either: it is
        # already on this dashboard's snapshot (the escalation
        # widget names it), so check_ids would permit it.
        res = self.formula(
            form_id=self.off_dashboard_form.id,
            formula=self.bucket_formula(600102),
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_on_the_allowed_form(self):
        self.assertEqual(self.geo(6001).status_code, 200)

    def test_geolocation_on_a_foreign_form_is_404(self):
        # Same reasoning as test_formula_on_a_foreign_form_is_404.
        self.assertEqual(
            self.geo(self.off_dashboard_form.id).status_code, 404
        )

    def test_geolocation_with_a_foreign_monitoring_form_is_404(self):
        # monitoring_form_id only reaches a query filter when
        # from_date or to_date is also set, so it is never looked up
        # against the database either way -- check_ids is the only
        # thing that can reject it, and a bogus id proves that just
        # as well as a real off-dashboard one. 6002 is on this
        # dashboard's snapshot, so 9999 is used instead.
        res = self.geo(
            6001, include_monitoring="true", monitoring_form_id=9999
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_with_no_slug_is_404(self):
        # test_no_slug_is_404 covers /values only. The geolocation
        # endpoint has its own view with its own scope check ordered
        # before its serializer (GeolocationListView.get), so it
        # needs its own regression rather than inheriting /values'.
        res = self.client.get(
            "/api/v1/maps/geolocation/6001", {}
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_with_an_unparseable_monitoring_form_id_is_404(
        self,
    ):
        # Fix round 1: Allowlist.permits_form used to do a bare
        # int(form_id), and monitoring_form_id is the one id in this
        # module that reaches check_ids straight off the query string
        # with no serializer or int() coercion upstream (form_id is a
        # path int; the others are all validated fields). A
        # hand-crafted monitoring_form_id=abc raised ValueError and
        # 500'd a public page instead of 404ing like any other id
        # that is not on the dashboard.
        res = self.geo(6001, monitoring_form_id="abc")
        self.assertEqual(res.status_code, 404)

    def test_geolocation_with_an_empty_monitoring_form_id_is_404(self):
        res = self.geo(6001, monitoring_form_id="")
        self.assertEqual(res.status_code, 404)
