import json
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.tests.mixins import (
    ProfileTestHelperMixin,
    TenantTestHelperMixin,
)
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class ForgotPasswordUserTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)

        self.user = self.create_user(
            email="test@example.com",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.assertIsNotNone(
            self.user, "No user found for forgot password test"
        )

    def test_forgot_password(self):
        # Prepare user payload for forgot password
        user_payload = {
            "email": self.user.email,
        }
        # Perform forgot password request
        response = self.client.post(
            "/api/v1/user/forgot-password",
            user_payload,
            content_type="application/json",
        )
        # Check if the request was successful
        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        self.assertIn("message", response_data)
        self.assertEqual(
            response_data["message"],
            "Reset password instructions sent to your email"
        )

    def test_forgot_password_non_existent_user(self):
        # Prepare payload for a non-existent user
        user_payload = {
            "email": "non_existent_user@example.com"
        }
        # Perform forgot password request
        response = self.client.post(
            "/api/v1/user/forgot-password",
            user_payload,
            content_type="application/json",
        )
        # Check if the request was successful
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("message", response_data)
        self.assertEqual(
            response_data["message"],
            "Invalid email, user not found"
        )

    def test_forgot_password_invalid_email(self):
        # Prepare payload with an invalid email format
        user_payload = {
            "email": "invalid_email_format"
        }
        # Perform forgot password request
        response = self.client.post(
            "/api/v1/user/forgot-password",
            user_payload,
            content_type="application/json",
        )
        # Check if the request was successful
        self.assertEqual(response.status_code, 400)
        response_data = response.json()

        self.assertIn("message", response_data)
        self.assertEqual(
            response_data["message"],
            "Enter a valid email address."
        )


@override_settings(BASE_DOMAIN="app.com")
class ForgotPasswordOnTheConsoleHostTestCase(TestCase, TenantTestHelperMixin):
    """A reset started on the console must land on the console.

    The lookup is scoped by the request's workspace, and the console
    belongs to none -- so without care the queryset is every account
    with that address, in every workspace, and `.first()` picks one at
    random. An operator who also has a workspace account under the same
    address then gets a link to that workspace instead, where the reset
    completes into a session that cannot open the console.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.shared = "both@akvo.org"
        # The workspace account exists first, so it is the row an
        # unscoped `.first()` returns.
        SystemUser.objects.create(
            email=self.shared, tenant=self.acme.tenant
        )
        self.operator = SystemUser.objects.create(
            email=self.shared, is_platform_admin=True, tenant=None
        )

    def reset_from(self, host):
        with mock.patch("api.v1.v1_users.views.send_email") as send_email:
            response = self.client.post(
                "/api/v1/user/forgot-password",
                json.dumps({"email": self.shared}),
                content_type="application/json",
                HTTP_HOST=host,
            )
        self.assertEqual(response.status_code, 200, response.content)
        return send_email.call_args.kwargs["context"]["button_url"]

    def test_the_console_reset_links_to_the_console(self):
        url = self.reset_from("admin.app.com")
        self.assertIn("//admin.app.com/", url)

    def test_the_workspace_reset_still_links_to_the_workspace(self):
        # The same address at a workspace host is the workspace's
        # account, and must keep working exactly as before.
        url = self.reset_from("acme.app.com")
        self.assertIn("//acme.app.com/", url)
