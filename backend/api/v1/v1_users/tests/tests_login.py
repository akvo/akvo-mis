from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.management.commands.fake_user_seeder import (
    DEFAULT_PASSWORD
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoginUserTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder", "--repeat", 2)

        output = StringIO()
        call_command(
            "fake_user_seeder",
            "--repeat",
            10,
            stdout=output,
            stderr=StringIO(),
        )

    def test_login_user(self):
        # Find a user to login
        user = SystemUser.objects.filter(
            user_user_role__isnull=False,
        ).order_by("?").first()
        if not user:
            self.fail("No user found for login test")
        # Prepare user payload for login
        user_payload = {
            "email": user.email,
            "password": DEFAULT_PASSWORD,
        }
        # Perform login
        user_response = self.client.post(
            "/api/v1/login",
            user_payload,
            content_type="application/json",
        )
        # Check if login was successful
        self.assertEqual(user_response.status_code, 200)
        user_data = user_response.json()

        self.assertEqual(
            list(user_data),
            [
                "email",
                "name",
                "roles",
                "trained",
                "phone_number",
                "forms",
                "organisation",
                "last_login",
                "passcode",
                "is_superuser",
                "administration",
                "id",
                # Drives the frontend's routing gate: an unconfigured
                # workspace goes to the configuration form, not the
                # dashboard.
                "configured",
                "token",
                "invite",
                "expiration_time",
            ],
        )

        # Check user data
        self.assertEqual(user_data["email"], user.email)

        # Check inside roles
        self.assertGreater(len(user_data["roles"]), 0)
        for role in user_data["roles"]:
            self.assertIn("role", role)
            self.assertIn("administration", role)
            self.assertIn("is_approver", role)
            self.assertIn("is_submitter", role)
            self.assertIn("is_editor", role)

    def test_login_user_with_wrong_password(self):
        # Find a user to login
        user = SystemUser.objects.filter(
            user_user_role__isnull=False,
        ).order_by("?").first()
        if not user:
            self.fail("No user found for login test")
        # Prepare user payload for login with wrong password
        user_payload = {
            "email": user.email,
            "password": "wrong_password",
        }
        # Perform login
        user_response = self.client.post(
            "/api/v1/login",
            user_payload,
            content_type="application/json",
        )
        # Check if login failed
        self.assertEqual(user_response.status_code, 401)
        self.assertIn("message", user_response.json())
        self.assertEqual(
            user_response.json()["message"],
            "Invalid login credentials"
        )

    def test_login_user_with_non_existent_email(self):
        # Prepare user payload for login with non-existent email
        user_payload = {
            "email": "unknown@test.com",
            "password": DEFAULT_PASSWORD,
        }
        # Perform login
        user_response = self.client.post(
            "/api/v1/login",
            user_payload,
            content_type="application/json",
        )
        # Check if login failed
        self.assertEqual(user_response.status_code, 401)
        self.assertIn("message", user_response.json())
        self.assertEqual(
            user_response.json()["message"],
            "Invalid login credentials"
        )


@override_settings(USE_TZ=False, TESTING=False)
class LoginAutoCreateDisabledTestCase(TestCase):
    def test_login_on_empty_database_creates_no_user(self):
        # Outside test runs (TESTING=False) a fresh instance must not
        # conjure the legacy admin@akvo.org account — registration is
        # the only way accounts come into being.
        response = self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(SystemUser.objects.count(), 0)
