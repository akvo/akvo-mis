from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import Organisation, SystemUser
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_profile.models import (
    Role,
    Administration,
    Levels,
)
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_users.views import send_email_to_user
from utils.email_helper import EmailTypes
from api.v1.v1_users.models import Tenant
from unittest import mock


@override_settings(USE_TZ=False, TEST_ENV=True)
class AddUserTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder")
        call_command("form_seeder", "--test")
        payload = {"email": "admin@akvo.org", "password": "Test105*"}
        user_response = self.client.post(
            "/api/v1/login", payload, content_type="application/json"
        )
        user = user_response.json()
        self.token = user.get("token")
        self.header = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.org = Organisation.objects.order_by("?").first()

    def test_add_superuser_without_forms(self):
        payload = {
            "email": "super2@test.com",
            "password": "Test105*",
            "first_name": "Super",
            "last_name": "User",
            "is_superuser": True,
            "organisation": self.org.id,
            "forms": [],
            "roles": [],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        # Total forms should be all published forms
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, True)
        self.assertEqual(
            user.user_form.count(),
            Forms.objects.filter(status=FormStatus.published).count(),
        )

    def test_add_superuser_with_forms(self):
        # Get 2 parent forms
        forms = [f.id for f in Forms.objects.filter(parent__isnull=True)[:2]]
        payload = {
            "email": "super2@test.com",
            "password": "Test105*",
            "first_name": "Super",
            "last_name": "User2",
            "is_superuser": True,
            "organisation": self.org.id,
            "forms": forms,
            "roles": [],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        # self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, True)
        # Total forms should be 2
        self.assertEqual(user.user_form.count(), 2)

    def test_add_user_with_single_role(self):
        # Get role by level 2 and read, submit access
        third_level = Levels.objects.get(level=2)
        role = Role.objects.filter(
            administration_level=third_level,
            role_role_access__data_access__in=[
                DataAccessTypes.read,
                DataAccessTypes.submit,
            ],
        ).first()
        adm = (
            Administration.objects.filter(level__level=2).order_by("?").first()
        )
        form = Forms.objects.get(pk=1)
        payload = {
            "email": "admin.3@test.com",
            "password": "Test105*",
            "first_name": "Admin",
            "last_name": adm.name,
            "forms": [form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role.id,
                    "administration": adm.id,
                }
            ],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(user.user_form.count(), 1)

        # Test role assignments with the new multiple roles structure
        user_roles = user.user_user_role.all()
        self.assertEqual(user_roles.count(), 1)

        # Check that the assigned role matches what we sent in the payload
        assigned_role = user_roles.first()
        self.assertEqual(assigned_role.role.id, payload["roles"][0]["role"])
        admin_id = payload["roles"][0]["administration"]
        self.assertEqual(assigned_role.administration.id, admin_id)

    def test_add_user_with_multiple_roles(self):
        # Get role for level 2
        second_level = Levels.objects.get(level=1)
        role_level_2 = Role.objects.filter(
            administration_level=second_level
        ).first()
        adm_level_2 = (
            Administration.objects.filter(level__level=1).order_by("?").first()
        )

        # Get role for level 3
        third_level = Levels.objects.get(level=2)
        role_level_3 = Role.objects.filter(
            administration_level=third_level
        ).first()
        adm_level_3 = (
            Administration.objects.filter(level__level=2).order_by("?").first()
        )

        form = Forms.objects.get(pk=1)
        payload = {
            "email": "multi.role@test.com",
            "password": "Test105*",
            "first_name": "Multiple",
            "last_name": "Roles",
            "forms": [form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role_level_2.id,
                    "administration": adm_level_2.id,
                },
                {
                    "role": role_level_3.id,
                    "administration": adm_level_3.id,
                },
            ],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(user.user_form.count(), 1)

        # Test multiple role assignments
        user_roles = user.user_user_role.all().order_by("role__id")
        self.assertEqual(user_roles.count(), 2)

        # Verify first role assignment
        role1 = user_roles[0]
        self.assertEqual(role1.role.id, payload["roles"][0]["role"])
        admin_id1 = payload["roles"][0]["administration"]
        self.assertEqual(role1.administration.id, admin_id1)

        # Verify second role assignment
        role2 = user_roles[1]
        self.assertEqual(role2.role.id, payload["roles"][1]["role"])
        admin_id2 = payload["roles"][1]["administration"]
        self.assertEqual(role2.administration.id, admin_id2)

    def test_add_user_with_approve_access(self):
        # Get role for level 2 with approve access
        second_level = Levels.objects.get(level=1)
        role_with_approve_access = Role.objects.filter(
            administration_level=second_level,
            role_role_access__data_access=DataAccessTypes.approve,
        ).first()
        adm_level_2 = (
            Administration.objects.filter(level__level=1).order_by("?").first()
        )

        form = Forms.objects.get(pk=1)
        payload = {
            "email": "approver1@test.com",
            "password": "Test105*",
            "first_name": "Approver",
            "last_name": "User",
            "forms": [form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role_with_approve_access.id,
                    "administration": adm_level_2.id,
                }
            ],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(user.user_form.count(), 1)
        user_roles = user.user_user_role.all()
        self.assertEqual(user_roles.count(), 1)
        assigned_role = user_roles.first()
        self.assertEqual(assigned_role.role.id, payload["roles"][0]["role"])
        self.assertEqual(
            assigned_role.administration.id,
            payload["roles"][0]["administration"],
        )
        self.assertTrue(assigned_role.is_approver())
        self.assertTrue(
            assigned_role.role.role_role_access.filter(
                data_access=DataAccessTypes.approve
            ).exists()
        )

    def test_add_user_with_invalid_role(self):
        # Get a valid role for level 2
        second_level = Levels.objects.get(level=1)
        role_level_2 = Role.objects.filter(
            administration_level=second_level
        ).first()
        adm_level_2 = (
            Administration.objects.filter(level__level=1).order_by("?").first()
        )

        form = Forms.objects.get(pk=1)
        payload = {
            "email": "user.invalid@test.com",
            "password": "Test105*",
            "first_name": "Invalid",
            "last_name": "Role",
            "forms": [form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role_level_2.id,
                    "administration": adm_level_2.id,
                },
                {
                    "role": 9999,  # Invalid role ID
                    "administration": adm_level_2.id,
                },
            ],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()["details"]
        self.assertIn("role", data)
        self.assertEqual(data["role"], ["Invalid role ID: 9999"])
        # Ensure no user was created
        self.assertFalse(
            SystemUser.objects.filter(email=payload["email"]).exists()
        )

    def test_add_user_with_invalid_administration(self):
        # Get a valid role for level 2
        second_level = Levels.objects.get(level=1)
        role_level_2 = Role.objects.filter(
            administration_level=second_level
        ).first()
        adm_level_2 = (
            Administration.objects.filter(level__level=1).order_by("?").first()
        )

        form = Forms.objects.get(pk=1)
        payload = {
            "email": "invalid.adm@test.com",
            "password": "Test105*",
            "first_name": "Invalid",
            "last_name": "Administration",
            "forms": [form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role_level_2.id,
                    "administration": adm_level_2.id,
                },
                {
                    "role": role_level_2.id,
                    "administration": 9999,  # Invalid administration ID
                },
            ],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()["details"]
        self.assertIn("administration", data)
        self.assertEqual(
            data["administration"], ["Invalid administration ID: 9999"]
        )

    def test_add_user_with_empty_payload(self):
        payload = {}
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()["details"]
        self.assertIn("email", data)
        self.assertIn("first_name", data)
        self.assertIn("last_name", data)
        self.assertEqual(data["email"], ["This field is required."])
        self.assertEqual(data["first_name"], ["This field is required."])
        self.assertEqual(data["last_name"], ["This field is required."])

    def test_add_user_with_invalid_email(self):
        payload = {
            "email": "invalid-email",
            "password": "Test105*",
            "first_name": "Invalid",
            "last_name": "Email",
            "organisation": self.org.id,
            "forms": [],
            "roles": [],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()["details"]
        self.assertIn("email", data)
        self.assertEqual(data["email"], ["Enter a valid email address."])

    def test_add_user_with_existing_email(self):
        payload = {
            "email": "admin@akvo.org",
            "password": "Test105*",
            "first_name": "Duplicate",
            "last_name": "User",
            "organisation": self.org.id,
            "forms": [],
            "roles": [],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()["details"]
        self.assertIn("email", data)
        self.assertEqual(
            data["email"],
            [
                "This email is already in your workspace. "
                "To make changes, edit the existing user."
            ],
        )

    def test_add_user_with_missing_fields(self):
        payload = {
            "email": "missing@test.com",
            "password": "Test105*",
            "first_name": "Missing",
            # "last_name": "Fields",  # Missing last_name
            "organisation": self.org.id,
            "forms": [],
            "roles": [],
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()["details"]
        self.assertIn("last_name", data)
        self.assertEqual(data["last_name"], ["This field is required."])


@override_settings(
    BASE_DOMAIN="app.com", WEBDOMAIN="https://app.com", TEST_ENV=True
)
class InviteEmailUrlTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        self.tenant = Tenant.objects.create(subdomain="acme")
        self.user = SystemUser.objects.create_user(
            email="test@acme.app.com",
            password="Test105*",
            first_name="Test",
            last_name="User",
            tenant=self.tenant,
        )

    @mock.patch("api.v1.v1_users.views.send_email")
    def test_invite_email_tenant_url(self, mock_send_email):
        request = mock.Mock()
        send_email_to_user(
            type=EmailTypes.user_invite, user=self.user, request=request
        )

        mock_send_email.assert_called_once()
        button_url = mock_send_email.call_args.kwargs["context"]["button_url"]
        self.assertTrue(button_url.startswith("https://acme.app.com/login/"))
