from django.core.management import call_command
from django.test.utils import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.models import Forms
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
