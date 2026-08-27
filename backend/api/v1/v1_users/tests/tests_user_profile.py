from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import Administration, Role
from api.v1.v1_forms.models import Forms


@override_settings(USE_TZ=False, TEST_ENV=True)
class UserProfileTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder", "--repeat", 2)
        call_command("form_seeder", "--test", 1)
        # Create a superuser for testing
        self.superuser = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        # Create a user for testing
        adm = Administration.objects.filter(
            level__level=3
        ).first()

        form = Forms.objects.filter(
            parent__isnull=True
        ).order_by("?").first()

        self.user = self.create_user(
            email="user.123@test.com",
            role_level=self.IS_ADMIN,
            administration=adm,
            form=form,
        )
        self.user.set_password("test1234")
        self.user.save()

        submitter_role = Role.objects.filter(
            administration_level=adm.level,
            name=f"{adm.level.name} Submitter"
        ).first()
        if submitter_role:
            # Add more roles to the user
            self.user.user_user_role.create(
                administration=adm,
                role=submitter_role
            )
        self.super_token = self.get_auth_token(self.superuser.email)
        self.user_token = self.get_auth_token(self.user.email, "test1234")

    def test_superuser_profile(self):
        response = self.client.get(
            "/api/v1/profile/",
            HTTP_AUTHORIZATION=f"Bearer {self.super_token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            list(data),
            [
                'email',
                'name',
                'roles',
                'trained',
                'phone_number',
                'forms',
                'organisation',
                'last_login',
                'passcode',
                'is_superuser',
                'administration',
                'id',
                'configured',
                'subdomain',
            ]
        )
        self.assertEqual(data["email"], self.superuser.email)
        self.assertEqual(data["roles"], [])

    def test_user_profile(self):
        response = self.client.get(
            "/api/v1/profile/",
            HTTP_AUTHORIZATION=f"Bearer {self.user_token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(len(data["roles"]), 2)
        self.assertEqual(
            list(data["roles"][0]),
            [
                'id',
                'role',
                'administration',
                'is_approver',
                'is_submitter',
                'is_editor',
                'can_delete',
                'can_invite_user',
                'can_form_builder',
                'can_form_delete',
                'can_form_create',
                'can_form_edit',
                'can_form_publish',
                'can_dashboard_view',
                'can_dashboard_create',
                'can_dashboard_edit',
                'can_dashboard_publish',
                'can_dashboard_delete',
                'can_dashboard_share_public',
            ]
        )
        self.assertEqual(
            list(data["roles"][0]["administration"]),
            ['id', 'name', 'level', 'level_id', 'full_name']
        )

    def test_user_profile_with_invalid_token(self):
        response = self.client.get(
            "/api/v1/profile/",
            HTTP_AUTHORIZATION="Bearer invalid_token",
        )
        self.assertEqual(response.status_code, 401)

    def test_user_profile_with_no_auth(self):
        response = self.client.get("/api/v1/profile/")
        self.assertEqual(response.status_code, 401)
