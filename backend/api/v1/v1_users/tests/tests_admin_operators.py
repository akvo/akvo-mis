import json
from unittest import mock

from django.test import TestCase, override_settings

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser

ADMIN_HOST = "admin.app.com"
OPERATORS = "/api/v1/admin/operators"


@override_settings(BASE_DOMAIN="app.com")
class AdminOperatorsTestCase(TestCase, TenantTestHelperMixin):
    """Operators grow their own team; the first one cannot.

    Revoking clears the flag rather than deleting the account: MT-023
    adds a table whose operator FK is PROTECT, so a delete would raise.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.auth = self.bearer(self.operator)

    def invite(self, email):
        with mock.patch("api.v1.v1_users.admin_views.send_activation_email"):
            return self.client.post(
                OPERATORS,
                json.dumps({"email": email}),
                content_type="application/json",
                HTTP_HOST=ADMIN_HOST,
                **self.auth,
            )

    def test_lists_only_operators(self):
        response = self.client.get(
            OPERATORS, HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 200)
        emails = [row["email"] for row in response.json()]
        self.assertEqual(emails, ["ops@akvo.org"])
        self.assertNotIn(self.acme.admin.email, emails)

    def test_invites_a_peer(self):
        self.assertEqual(self.invite("dedi@akvo.org").status_code, 200)
        invited = SystemUser.objects.get(email="dedi@akvo.org")
        self.assertTrue(invited.is_platform_admin)
        self.assertIsNone(invited.tenant_id)
        # Inactive until the activation link is followed, exactly as a
        # registrant is.
        self.assertFalse(invited.is_active)

    def test_refuses_a_duplicate_invite(self):
        self.invite("dedi@akvo.org")
        self.assertEqual(self.invite("dedi@akvo.org").status_code, 400)

    def test_revoke_clears_the_flag_and_keeps_the_account(self):
        self.invite("dedi@akvo.org")
        invited = SystemUser.objects.get(email="dedi@akvo.org")
        response = self.client.delete(
            f"{OPERATORS}/{invited.pk}", HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 200)
        invited.refresh_from_db()
        self.assertFalse(invited.is_platform_admin)
        self.assertTrue(
            SystemUser.objects.filter(pk=invited.pk).exists()
        )

    def test_an_operator_cannot_revoke_themselves(self):
        # The last operator revoking themselves locks everyone out and
        # the only way back is a shell.
        response = self.client.delete(
            f"{OPERATORS}/{self.operator.pk}", HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(WEBDOMAIN="https://app.com")
    def test_the_invitation_links_to_the_console_not_the_base_domain(self):
        # An operator has no workspace, so the ordinary activation link
        # would point at the base domain -- the public signup page, and
        # the one origin where login refuses them. Following it there
        # would hand them a session on a host they cannot use.
        with mock.patch(
            "api.v1.v1_users.views.send_email"
        ) as send_email:
            self.client.post(
                OPERATORS,
                json.dumps({"email": "dedi@akvo.org"}),
                content_type="application/json",
                HTTP_HOST=ADMIN_HOST,
                **self.auth,
            )
        url = send_email.call_args.kwargs["context"]["button_url"]
        self.assertTrue(
            url.startswith("https://admin.app.com/activate/"), url
        )

    def test_a_workspace_user_is_refused(self):
        response = self.client.get(
            OPERATORS, HTTP_HOST=ADMIN_HOST, **self.bearer(self.acme.admin)
        )
        self.assertEqual(response.status_code, 403)
