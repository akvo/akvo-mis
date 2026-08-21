from django.core.management import call_command
from django.test.utils import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.models import Forms
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
