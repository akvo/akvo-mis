from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormStatus, FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import Tenant
from api.v1.v1_visualization.constants import SUPPORTED_QUESTION_TYPES
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False)
class DashboardSourcesTestCase(TestCase, ProfileTestHelperMixin):
    """/sources is the family boundary as the UI sees it.

    If a form is not here the builder cannot offer it; if the builder
    somehow does, the family rule rejects it on save. Two barriers,
    one rule — so this endpoint has to draw exactly the same line.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_sources@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        token = RefreshToken.for_user(self.user).access_token
        self.header = {
            "HTTP_AUTHORIZATION": "Bearer {0}".format(token)
        }
        self.root = Forms.objects.get(pk=6001)
        self.monitoring = Forms.objects.get(pk=6002)
        # A second family that must not appear in the response.
        self.stranger = Forms.objects.create(
            name="Unrelated registration",
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            created_by=self.user,
        )
        self.url = "/api/v1/manage/dashboards/{0}/sources".format(
            self.dashboard.id
        )

    def get(self):
        return self.client.get(self.url, **self.header)

    def test_returns_the_root_form_and_its_monitoring_children_only(
        self,
    ):
        body = self.get().json()
        self.assertEqual(
            [f["id"] for f in body["forms"]],
            [self.root.id, self.monitoring.id],
        )

    def test_form_and_question_types_are_lowercase(self):
        # BuilderInspector compares against lowercase literals
        # (form?.type === "monitoring", question.type === "option"),
        # while FieldStr yields "Monitoring" and "Multiple_Option".
        body = self.get().json()
        self.assertEqual(body["forms"][0]["type"], "registration")
        self.assertEqual(body["forms"][1]["type"], "monitoring")
        for form in body["forms"]:
            for question in form["questions"]:
                self.assertEqual(
                    question["type"], question["type"].lower()
                )

    def test_only_the_monitoring_form_carries_a_parent(self):
        body = self.get().json()
        self.assertNotIn("parent", body["forms"][0])
        self.assertEqual(body["forms"][1]["parent"], self.root.id)

    def test_never_returns_an_unsupported_question_type(self):
        body = self.get().json()
        returned = []
        for form in body["forms"]:
            returned.extend(q["id"] for q in form["questions"])
        # 600205 is the seeded text question on the monitoring form.
        self.assertNotIn(600205, returned)
        for question_id in returned:
            self.assertIn(
                Questions.objects.get(pk=question_id).type,
                SUPPORTED_QUESTION_TYPES,
            )

    def test_choice_questions_carry_their_options(self):
        body = self.get().json()
        by_id = {}
        for form in body["forms"]:
            for question in form["questions"]:
                by_id[question["id"]] = question
        option_question = by_id[600203]
        self.assertEqual(option_question["type"], "option")
        self.assertTrue(option_question["options"])
        self.assertIn("value", option_question["options"][0])
        self.assertIn("label", option_question["options"][0])

    def test_non_choice_questions_carry_no_options_key(self):
        body = self.get().json()
        by_id = {}
        for form in body["forms"]:
            for question in form["questions"]:
                by_id[question["id"]] = question
        # 600202 is the seeded number question.
        self.assertNotIn("options", by_id[600202])

    def test_soft_deleted_questions_and_forms_are_excluded(self):
        question = Questions.objects.get(pk=600203)
        question.delete()
        body = self.get().json()
        returned = []
        for form in body["forms"]:
            returned.extend(q["id"] for q in form["questions"])
        self.assertNotIn(600203, returned)

        self.monitoring.delete()
        body = self.get().json()
        self.assertEqual([f["id"] for f in body["forms"]], [self.root.id])

    def test_another_tenants_dashboard_id_is_404(self):
        foreign_tenant = Tenant.objects.create(subdomain="beta")
        foreign_form = Forms.objects.create(
            name="beta-form",
            tenant=foreign_tenant,
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        foreign = Dashboard.objects.create(
            name="Beta", slug="beta", root_form=foreign_form,
            tenant=foreign_tenant,
        )
        res = self.client.get(
            "/api/v1/manage/dashboards/{0}/sources".format(foreign.id),
            **self.header
        )
        self.assertEqual(res.status_code, 404)

    def test_question_type_ids_are_the_four_aggregatable_ones(self):
        # Guards the import: if SUPPORTED_QUESTION_TYPES ever changes,
        # this test says so rather than /sources silently widening.
        self.assertEqual(
            SUPPORTED_QUESTION_TYPES,
            {
                QuestionTypes.number,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
                QuestionTypes.date,
            },
        )
