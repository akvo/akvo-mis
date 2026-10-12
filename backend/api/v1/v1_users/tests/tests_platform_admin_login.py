from unittest import mock

from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import (
    TENANT_PASSWORD,
    TenantTestHelperMixin,
)
from api.v1.v1_users.models import SystemUser

LOGIN = "/api/v1/login"
OPERATOR_PASSWORD = "Secret#Pass123"


@override_settings(BASE_DOMAIN="app.com")
class PlatformAdminLoginTestCase(TestCase, TenantTestHelperMixin):
    """Operators sign in at the console; everyone else does not.

    The console must not become an oracle for which addresses exist in
    which workspace, so a workspace account typed in here is refused
    with the message the base domain already gives.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.operator.set_password(OPERATOR_PASSWORD)
        self.operator.save()

    def operator_credentials(self):
        return {"email": "ops@akvo.org", "password": OPERATOR_PASSWORD}

    def workspace_credentials(self):
        return {
            "email": self.acme.admin.email,
            "password": TENANT_PASSWORD,
        }

    def test_operator_signs_in_on_the_admin_host(self):
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="admin.app.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_workspace_account_is_refused_on_the_admin_host(self):
        # 401 and the generic credentials failure, not the 400 this
        # asserted while the console still evaluated workspace
        # passwords. Narrowing console authentication to tenant-less
        # accounts means a workspace account matches no row here at all,
        # so it never reaches the operator check below and is refused
        # the same way a wrong password is.
        #
        # The oracle this class guards against is unaffected: every
        # failed console sign-in now answers identically, whether the
        # address exists in a workspace or nowhere.
        response = self.client.post(
            LOGIN, self.workspace_credentials(), HTTP_HOST="admin.app.com"
        )
        self.assertEqual(response.status_code, 401)

    def test_an_operator_who_also_has_a_workspace_account_signs_in(self):
        # Reported from akvotest: an invited operator could not sign in
        # to the console, and was told to use their workspace address
        # instead. They already held a workspace account under the same
        # address and had reused its password when accepting the
        # invitation -- a state the invite flow permits, because
        # OperatorInviteSerializer refuses only a second *tenant-less*
        # account.
        #
        # The console resolves no tenant, so login reaches the
        # tenant=None branch of TenantAwareBackend, which searched every
        # workspace on the deployment and returned the first row whose
        # password matched. The workspace account predates the
        # invitation and so comes first, and the operator was handed
        # that row and refused for not being an operator.
        twin = self.acme.admin
        operator = SystemUser.objects.create(
            email=twin.email, is_platform_admin=True, tenant=None
        )
        operator.set_password(TENANT_PASSWORD)
        operator.save()
        self.assertLess(twin.pk, operator.pk)
        response = self.client.post(
            LOGIN,
            {"email": twin.email, "password": TENANT_PASSWORD},
            HTTP_HOST="admin.app.com",
        )
        self.assertEqual(response.status_code, 200, response.content)
        # The operator's own row, not the workspace twin's.
        self.assertEqual(response.json()["id"], operator.pk)

    def test_operator_is_refused_on_a_workspace_host(self):
        # TenantAwareBackend scopes the lookup to the host's tenant, and
        # an operator's tenant is NULL, so no row matches and the view
        # answers with its generic credentials failure.
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="acme.app.com"
        )
        self.assertEqual(response.status_code, 401)

    def test_operator_is_refused_on_the_base_domain(self):
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="app.com"
        )
        self.assertEqual(response.status_code, 400)

    def test_the_session_says_the_signed_in_account_is_an_operator(self):
        # The console's route guard is the only thing standing between a
        # workspace account and the /admin tree, and it has nothing else
        # to read: `is_superuser` is a workspace role (D-1) and a
        # tenant-less `subdomain` is "" for reasons unrelated to being
        # an operator. Without this field on the wire the guard can
        # never pass, and the console redirects its own operators to
        # the login page they just came from.
        response = self.client.post(
            LOGIN, self.operator_credentials(), HTTP_HOST="admin.app.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_platform_admin"])

    def test_a_workspace_account_is_not_an_operator(self):
        response = self.client.post(
            LOGIN, self.workspace_credentials(), HTTP_HOST="acme.app.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_platform_admin"])

    def test_a_forgotten_password_is_reset_on_the_console(self):
        # Same reasoning as the activation link: everything past this
        # URL is bound to a host, and an operator's host is the console.
        # Sending them to the base domain hands them a link to the one
        # origin that refuses to sign them in -- /login there redirects
        # to find-workspace, so the reset can never be completed.
        with mock.patch("api.v1.v1_users.views.send_email") as send_email:
            response = self.client.post(
                "/api/v1/user/forgot-password",
                {"email": "ops@akvo.org"},
                content_type="application/json",
                HTTP_HOST="admin.app.com",
            )
        self.assertEqual(response.status_code, 200)
        url = send_email.call_args.kwargs["context"]["button_url"]
        self.assertIn("//admin.app.com", url)
        self.assertIn("/login/", url)
