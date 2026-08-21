from django.core.management import call_command
from django.test.utils import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False, TEST_ENV=True)
class VisualizationTenantIsolationTestCase(APITestCase):
    """A form owned by another tenant must be indistinguishable from
    a form that does not exist anywhere."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        self.acme = Tenant.objects.create(subdomain="acme")
        self.beta = Tenant.objects.create(subdomain="beta")
        self.user = SystemUser.objects.create_user(
            email="acme@akvo.org",
            password="Secret#Pass123",
            first_name="Ac",
            last_name="Me",
            tenant=self.acme,
        )
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        # Owned by beta; acme must never reach it.
        self.foreign_form = Forms.objects.create(
            name="Beta Sites",
            type=FormTypes.registration,
            tenant=self.beta,
        )

    def make_question(self, form, name, qtype=QuestionTypes.option):
        """A real question on `form`, so a rejection can only come from
        the id being outside the caller's form family — never from the
        id matching no row at all."""
        group = QuestionGroup.objects.create(
            form=form, name=f"{name}_group"
        )
        return Questions.objects.create(
            form=form,
            question_group=group,
            name=name,
            label=name,
            type=qtype,
        )

    def foreign_urls(self):
        fid = self.foreign_form.id
        return [
            f"/api/v1/visualization/values?form_id={fid}",
            f"/api/v1/visualization/escalation/{fid}",
            f"/api/v1/visualization/progress/{fid}",
        ]

    def test_foreign_form_id_is_not_found(self):
        for url in self.foreign_urls():
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 404, f"{url} reached another tenant"
            )

    def test_progress_enumeration_is_closed(self):
        # The reported hole: /progress/1, /2, /3 walked other tenants'
        # forms. Every id the caller does not own must answer the same.
        for pk in [self.foreign_form.id, 1, 2, 3]:
            response = self.client.get(
                f"/api/v1/visualization/progress/{pk}"
            )
            self.assertEqual(
                response.status_code, 404, f"/progress/{pk} was reachable"
            )

    def test_foreign_and_nonexistent_are_indistinguishable(self):
        # The existence oracle: if a foreign id and an id that exists
        # nowhere answer differently, the difference enumerates other
        # tenants' forms. They must agree.
        nonexistent = 99999999
        self.assertFalse(Forms.objects.filter(pk=nonexistent).exists())
        for template in [
            "/api/v1/visualization/values?form_id={}",
            "/api/v1/visualization/escalation/{}",
            "/api/v1/visualization/progress/{}",
        ]:
            foreign = self.client.get(
                template.format(self.foreign_form.id)
            )
            missing = self.client.get(template.format(nonexistent))
            self.assertEqual(
                foreign.status_code,
                missing.status_code,
                f"{template} leaks existence: foreign "
                f"{foreign.status_code} vs missing "
                f"{missing.status_code}",
            )
            self.assertEqual(foreign.status_code, 404)

    def test_monitoring_stats_rejects_a_foreign_parent(self):
        # monitoring-stats takes parent_id and question_id straight from
        # the query string and ran FormData.objects.filter(parent_id=...)
        # unscoped, so authentication alone left an authenticated
        # cross-tenant enumeration.
        #
        # A hardcoded question_id would 404 on its own regardless of
        # scoping -- no Questions row exists with that id -- which would
        # mask a regression in the parent lookup behind a coincidental
        # 404. So this uses a real question, and puts it on an
        # acme-owned form whose `parent` FK points at the beta form
        # (a link FormViewSet.update() can create with no tenant check,
        # a separate pre-existing gap this task does not fix). That
        # keeps the question reachable through the acme-scoped form
        # family regardless of the parent lookup's own scoping, so this
        # test's pass/fail is driven specifically by whether `parent_id`
        # resolves through a tenant-scoped queryset, not diluted by the
        # (also correct) tenant check on the question's form family.
        from api.v1.v1_data.models import FormData
        from api.v1.v1_forms.constants import QuestionTypes
        from api.v1.v1_forms.models import QuestionGroup, Questions

        foreign_datapoint = FormData.objects.create(
            name="Beta datapoint",
            form=self.foreign_form,
            administration=Administration.objects.first(),
            created_by=self.user,
        )
        acme_shadow_form = Forms.objects.create(
            name="Acme shadow monitoring",
            type=FormTypes.monitoring,
            tenant=self.acme,
            parent=self.foreign_form,
        )
        question_group = QuestionGroup.objects.create(
            form=acme_shadow_form, name="qg_1"
        )
        question = Questions.objects.create(
            question_group=question_group,
            form=acme_shadow_form,
            label="Shadow question",
            type=QuestionTypes.number,
        )
        response = self.client.get(
            "/api/v1/visualization/monitoring-stats"
            f"?parent_id={foreign_datapoint.id}&question_id={question.id}"
        )
        self.assertEqual(response.status_code, 404)

    def test_aggregation_is_scoped_without_the_view(self):
        # Defense in depth. The id check in the view is bypassed
        # entirely: the function is called directly with another
        # tenant's form. It must still produce no rows, so that a future
        # caller that forgets the id check cannot leak.
        from api.v1.v1_data.models import FormData
        from api.v1.v1_visualization.functions import (
            get_base_monitoring_qs,
        )

        # Without a beta-owned row for the query to find, the assertion
        # below passes on an empty table whether or not the scope is
        # applied. This row is what makes the test discriminate, and the
        # guard after it keeps a future fixture change from quietly
        # turning the whole test back into a tautology.
        FormData.objects.create(
            name="Beta datapoint",
            form=self.foreign_form,
            administration=Administration.objects.first(),
            created_by=self.user,
        )
        self.assertEqual(
            FormData.objects.filter(form=self.foreign_form).count(),
            1,
            "fixture missing: the scope assertion would be vacuous",
        )

        qs, _, _ = get_base_monitoring_qs(
            self.foreign_form,
            self.foreign_form.id,
            {"monitoring": "all"},
            self.user,
        )
        self.assertEqual(qs.count(), 0)

    # -- /escalation: ids parsed out of criteria and columns ---------

    def test_escalation_rejects_a_foreign_question(self):
        # A question id belonging to another tenant must not ride in on
        # a request whose form_id is legitimate. Everything else here is
        # valid — the monitoring form is a real child of the caller's
        # own form — so a 400 can only come from the question check.
        own_form = Forms.objects.create(
            name="Acme Sites",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        own_monitoring = Forms.objects.create(
            name="Acme Monitoring",
            type=FormTypes.monitoring,
            parent=own_form,
            tenant=self.acme,
        )
        foreign_question = self.make_question(self.foreign_form, "beta_q")
        response = self.client.get(
            f"/api/v1/visualization/escalation/{own_form.id}"
            f"?monitoring_form_id={own_monitoring.id}"
            f"&criteria=option_equals:{foreign_question.id}:yes"
            f"&columns=site:parent_name"
        )
        self.assertEqual(response.status_code, 400)

    def test_escalation_rejects_a_foreign_overdue_deadline(self):
        # "overdue" carries TWO question ids
        # (completion_qid:deadline_qid). Checking only the first leaves
        # the deadline id unvalidated, so the completion id here is a
        # legitimate one of the caller's own and only the deadline is
        # foreign.
        own_form = Forms.objects.create(
            name="Acme Sites Overdue",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        own_monitoring = Forms.objects.create(
            name="Acme Monitoring Overdue",
            type=FormTypes.monitoring,
            parent=own_form,
            tenant=self.acme,
        )
        own_question = self.make_question(
            own_monitoring, "done_at", QuestionTypes.date
        )
        foreign_deadline = self.make_question(
            self.foreign_form, "beta_deadline", QuestionTypes.date
        )
        response = self.client.get(
            f"/api/v1/visualization/escalation/{own_form.id}"
            f"?monitoring_form_id={own_monitoring.id}"
            f"&criteria=overdue:{own_question.id}:{foreign_deadline.id}"
            f"&columns=site:parent_name"
        )
        self.assertEqual(response.status_code, 400)

    def test_escalation_rejects_a_foreign_column_question(self):
        # Column question ids come from a different parser than
        # criteria, so they need their own guard.
        own_form = Forms.objects.create(
            name="Acme Sites Columns",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        own_monitoring = Forms.objects.create(
            name="Acme Monitoring Columns",
            type=FormTypes.monitoring,
            parent=own_form,
            tenant=self.acme,
        )
        own_question = self.make_question(own_monitoring, "status")
        foreign_question = self.make_question(
            self.foreign_form, "beta_col_q"
        )
        response = self.client.get(
            f"/api/v1/visualization/escalation/{own_form.id}"
            f"?monitoring_form_id={own_monitoring.id}"
            f"&criteria=option_equals:{own_question.id}:yes"
            f"&columns=leak:answer:{foreign_question.id}"
        )
        self.assertEqual(response.status_code, 400)

    def test_escalation_rejects_a_foreign_monitoring_form(self):
        # The criteria question is a legitimate one of the caller's own,
        # so the only thing left to reject is monitoring_form_id.
        own_form = Forms.objects.create(
            name="Acme Sites 2",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        own_question = self.make_question(own_form, "acme_q")
        response = self.client.get(
            f"/api/v1/visualization/escalation/{own_form.id}"
            f"?monitoring_form_id={self.foreign_form.id}"
            f"&criteria=option_equals:{own_question.id}:yes"
            f"&columns=site:parent_name"
        )
        self.assertEqual(response.status_code, 400)

    # -- /values: the question_id existence oracle ---------------------

    def test_values_question_id_does_not_leak_form_existence(self):
        # ValuesFilterSerializer validates question_id against form_id
        # before the view's tenant-scoped form lookup runs. Unscoped,
        # that check PASSES for a foreign form's own question (the view
        # then 404s) but always FAILS for a form that exists nowhere
        # (400), because no question can sit on a form with no rows.
        # That 400-vs-404 split says "this form exists somewhere" —
        # the same oracle Task 2 closed for the bare form_id, merely
        # costlier to walk. Both shapes must answer alike.
        foreign_question = self.make_question(
            self.foreign_form, "beta_values_q"
        )
        nonexistent = 99999999
        self.assertFalse(Forms.objects.filter(pk=nonexistent).exists())
        foreign = self.client.get(
            "/api/v1/visualization/values"
            f"?form_id={self.foreign_form.id}"
            f"&question_id={foreign_question.id}"
        )
        missing = self.client.get(
            "/api/v1/visualization/values"
            f"?form_id={nonexistent}"
            f"&question_id={foreign_question.id}"
        )
        self.assertEqual(
            foreign.status_code,
            missing.status_code,
            "/values leaks existence via question_id: foreign "
            f"{foreign.status_code} vs missing {missing.status_code}",
        )
        self.assertEqual(foreign.status_code, 400)

    def test_values_criteria_does_not_leak_form_existence(self):
        # criteria carries question ids through a second, separate
        # lookup in the same serializer, so it needs the same scope or
        # the oracle simply moves one query parameter across.
        foreign_question = self.make_question(
            self.foreign_form, "beta_criteria_q"
        )
        nonexistent = 99999999
        self.assertFalse(Forms.objects.filter(pk=nonexistent).exists())
        criteria = f"option_equals:{foreign_question.id}:yes"
        foreign = self.client.get(
            "/api/v1/visualization/values"
            f"?form_id={self.foreign_form.id}&criteria={criteria}"
        )
        missing = self.client.get(
            "/api/v1/visualization/values"
            f"?form_id={nonexistent}&criteria={criteria}"
        )
        self.assertEqual(
            foreign.status_code,
            missing.status_code,
            "/values leaks existence via criteria: foreign "
            f"{foreign.status_code} vs missing {missing.status_code}",
        )
        self.assertEqual(foreign.status_code, 400)

    # -- /progress: the same monitoring_form_id hole -------------------

    def test_progress_rejects_a_foreign_monitoring_form(self):
        # /progress takes monitoring_form_id from the query string the
        # same way /escalation did, and the spec requires it validated
        # on both. The component question ids are the spec's deliberate
        # residual and are not checked here, so a 400 can only come
        # from the monitoring_form_id family check.
        own_form = Forms.objects.create(
            name="Acme Sites Progress",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        response = self.client.get(
            f"/api/v1/visualization/progress/{own_form.id}"
            f"?monitoring_form_id={self.foreign_form.id}"
            f"&components=base:any_yes:1"
        )
        self.assertEqual(response.status_code, 400)

    def test_escalation_rejects_a_foreign_child_of_my_own_form(self):
        # Forms.tenant is an independent column, not something a child
        # inherits through `parent`, and FormViewSet.update() repoints a
        # form's parent FK from request data with no tenant check
        # (v1_forms/functions.py). So another tenant's form can sit
        # inside the caller's form family, and deriving the family from
        # parent_form.children alone accepts it. The family has to be
        # both a child of the resolved parent AND of its tenant.
        own_form = Forms.objects.create(
            name="Acme Sites Reparented",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        foreign_child = Forms.objects.create(
            name="Beta Monitoring Reparented",
            type=FormTypes.monitoring,
            parent=own_form,
            tenant=self.beta,
        )
        own_question = self.make_question(own_form, "acme_reparent_q")
        response = self.client.get(
            f"/api/v1/visualization/escalation/{own_form.id}"
            f"?monitoring_form_id={foreign_child.id}"
            f"&criteria=option_equals:{own_question.id}:yes"
            f"&columns=site:parent_name"
        )
        self.assertEqual(response.status_code, 400)

    def test_escalation_rejects_a_foreign_date_question(self):
        # date_question_id carries a question id like criteria and
        # columns do, and reaches the same queries. It is not in the
        # design's documented residual list, so it gets the same check.
        own_form = Forms.objects.create(
            name="Acme Sites Dates",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        own_monitoring = Forms.objects.create(
            name="Acme Monitoring Dates",
            type=FormTypes.monitoring,
            parent=own_form,
            tenant=self.acme,
        )
        own_question = self.make_question(own_monitoring, "acme_date_q")
        foreign_date = self.make_question(
            self.foreign_form, "beta_date_q", QuestionTypes.date
        )
        response = self.client.get(
            f"/api/v1/visualization/escalation/{own_form.id}"
            f"?monitoring_form_id={own_monitoring.id}"
            f"&criteria=option_equals:{own_question.id}:yes"
            f"&columns=site:parent_name"
            f"&date_question_id={foreign_date.id}"
        )
        self.assertEqual(response.status_code, 400)

    def test_escalation_blames_the_parameter_that_failed(self):
        # A columns failure used to be reported under the "criteria"
        # key. validate_serializers_message drops the key from the HTTP
        # body, so this asserts on serializer.errors directly — the one
        # place the attribution is observable, and the place it starts
        # mattering as soon as anything surfaces field names.
        from api.v1.v1_visualization.dashboard_serializers import (
            EscalationFilterSerializer,
        )

        own_form = Forms.objects.create(
            name="Acme Sites Blame",
            type=FormTypes.registration,
            tenant=self.acme,
        )
        own_question = self.make_question(own_form, "acme_blame_q")
        foreign_question = self.make_question(
            self.foreign_form, "beta_blame_q"
        )
        serializer = EscalationFilterSerializer(
            data={
                "monitoring_form_id": own_form.id,
                "criteria": f"option_equals:{own_question.id}:yes",
                "columns": f"leak:answer:{foreign_question.id}",
            },
            context={"parent_form": own_form},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("columns", serializer.errors)
        self.assertNotIn("criteria", serializer.errors)
