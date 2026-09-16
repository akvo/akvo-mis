from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import Organisation, SystemUser
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.tests.tests_add_user import expected_assignment
from api.v1.v1_profile.models import (
    Role,
    Administration,
    Levels,
)
from api.v1.v1_profile.constants import (
    DataAccessTypes,
    FeatureAccessTypes,
)
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class AddUserByNonSuperUserTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder")
        call_command("form_seeder", "--test")

        self.adm = Administration.objects.filter(
            level__level=3
        ).order_by("id").first()
        self.form = Forms.objects.get(pk=1)
        self.org = Organisation.objects.first()

        self.user = self.create_user(
            email="nonsuper@akvo.org",
            role_level=self.IS_ADMIN,
            administration=self.adm,
            form=self.form,
        )

        self.user.set_password("password")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "password")

    def test_add_user_by_non_superuser_with_same_adm_level(self):
        # Create a new user with valid data at the same administration level
        third_level = Levels.objects.get(level=3)
        role = Role.objects.filter(
            administration_level=third_level,
            role_role_access__data_access__in=[
                DataAccessTypes.read,
                DataAccessTypes.submit
            ],
            role_role_feature_access__access=FeatureAccessTypes.invite_user
        ).first()
        payload = {
            "email": "newadmin3.1@test.com",
            "first_name": "Admin",
            "last_name": self.adm.name,
            "forms": [self.form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role.id,
                    "administration": self.adm.id,
                }
            ]
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(
            set(user.user_form.values_list("form_id", flat=True)),
            expected_assignment([self.form.id]),
        )

        # Check that the user has been assigned the correct role
        user_roles = user.user_user_role.all()
        self.assertEqual(user_roles.count(), 1)

        # Check that the assigned role matches the payload
        assigned_role = user_roles.first()
        self.assertEqual(assigned_role.role.id, payload["roles"][0]["role"])
        admin_id = payload["roles"][0]["administration"]
        self.assertEqual(assigned_role.administration.id, admin_id)

    def test_add_user_by_non_superuser_with_lower_adm_level(self):
        # Create a new user with valid data at a lower administration level
        four_level = Levels.objects.get(level=4)
        role = Role.objects.filter(
            administration_level=four_level,
            role_role_access__data_access__in=[
                DataAccessTypes.read,
                DataAccessTypes.submit
            ],
        ).first()
        first_child = self.adm.parent_administration.order_by("?").first()
        payload = {
            "email": "newuser4.1@test.com",
            "first_name": "User",
            "last_name": self.adm.name,
            "forms": [self.form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role.id,
                    "administration": first_child.id,
                }
            ]
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data, {"message": "User added successfully"})
        user = SystemUser.objects.get(email=payload["email"])
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(
            set(user.user_form.values_list("form_id", flat=True)),
            expected_assignment([self.form.id]),
        )

        # Check that the user has been assigned the correct role
        user_roles = user.user_user_role.all()
        self.assertEqual(user_roles.count(), 1)

        # Check that the assigned role matches the payload
        assigned_role = user_roles.first()
        self.assertEqual(assigned_role.role.id, payload["roles"][0]["role"])
        admin_id = payload["roles"][0]["administration"]
        self.assertEqual(assigned_role.administration.id, admin_id)
        # Check that the user has the correct administration level
        self.assertEqual(assigned_role.administration.level.level, 4)

    def test_add_user_by_non_superuser_with_higher_adm_level(self):
        # Attempt to create a new user with invalid data
        # at a higher administration level
        two_level = Levels.objects.get(level=2)
        role = Role.objects.filter(
            administration_level=two_level,
            role_role_access__data_access__in=[
                DataAccessTypes.read,
                DataAccessTypes.submit
            ],
        ).first()
        parent_adm = self.adm.parent
        payload = {
            "email": "newuser2.1@test.com",
            "first_name": "User",
            "last_name": parent_adm.name,
            "forms": [self.form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role.id,
                    "administration": parent_adm.id,
                }
            ]
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(
            data["message"],
            (
                "You do not have permission to add users "
                "with this role's administration level|"
                "You do not have permission to add users "
                "at a higher administration level"
            )
        )

    def test_add_user_by_invalid_permissions_non_superuser(self):
        # Remove feature access for the user
        self.user.user_user_role.all().delete()
        # Attempt to create a new user with valid data
        third_level = Levels.objects.get(level=3)
        role = Role.objects.filter(
            administration_level=third_level,
            role_role_access__data_access__in=[
                DataAccessTypes.read,
                DataAccessTypes.submit
            ],
            role_role_feature_access__access=FeatureAccessTypes.invite_user
        ).first()
        payload = {
            "email": "newuser3.2@test.com",
            "first_name": "User",
            "last_name": self.adm.name,
            "forms": [self.form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role.id,
                    "administration": self.adm.id,
                }
            ]
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("detail", data)
        self.assertEqual(data, {
            "detail": (
                "You do not have permission to perform this action."
            )
        })
        self.assertFalse(
            SystemUser.objects.filter(email=payload["email"]).exists()
        )

    def test_add_user_by_non_superuser_with_outside_them_role(self):
        user_roles = self.user.user_user_role.values_list(
            'role__id', flat=True
        )
        role = Role.objects.filter(
            administration_level__level=self.adm.level.level - 1,
            role_role_feature_access__access=FeatureAccessTypes.invite_user
        ).exclude(pk__in=user_roles).order_by("?").first()

        payload = {
            "email": "newadmin3.1@test.com",
            "first_name": "Admin",
            "last_name": self.adm.name,
            "forms": [self.form.id],
            "organisation": self.org.id,
            "roles": [
                {
                    "role": role.id,
                    "administration": self.adm.id,
                }
            ]
        }
        response = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(
            response_data,
            {
                "message": (
                    "You do not have permission to add users "
                    "with this role's administration level"
                ),
                "details": {
                    "role": [
                        "You do not have permission to add users "
                        "with this role's administration level"
                    ]
                }
            }
        )
