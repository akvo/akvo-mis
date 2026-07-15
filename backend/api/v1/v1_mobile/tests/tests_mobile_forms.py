from django.test import TestCase
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.models import (
    Administration,
    Role,
    UserRole,
)
from django.core.management import call_command
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_forms.models import Forms, UserForms
from api.v1.v1_forms.constants import FormStatus
from rest_framework import status


class MobileFormsApiTest(TestCase, AssignmentTokenTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.user = SystemUser.objects.create_user(
            email="test@test.org",
            password="test1234",
            first_name="test",
            last_name="testing",
        )
        adm1, adm2 = Administration.objects.filter(
            level__gt=0
        ).all()[:2]
        self.administration = adm1
        self.administration2 = adm2
        self.form = Forms.objects.get(pk=4)
        role_name = "{0} {1}".format(
            self.administration.level.name,
            "Submitter"
        )
        role = Role.objects.filter(name=role_name).first()
        UserRole.objects.create(
            user=self.user,
            role=role,
            administration=self.administration,
        )
        UserForms.objects.create(user=self.user, form=self.form)

        self.passcode = "test1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=self.passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.administration_children = Administration.objects.filter(
            parent=self.administration
        ).all()
        self.mobile_assignment.administrations.add(
            *self.administration_children
        )
        self.mobile_assignment.forms.add(self.form)
        # Explicitly add monitoring forms (children) to the assignment
        # Since selective monitoring form assignment feature,
        # children are no longer auto-included
        # Filter to published status to match API behavior
        self.form_children = Forms.objects.filter(
            parent=self.form,
            status=FormStatus.published
        )
        self.mobile_assignment.forms.add(*self.form_children)

    def test_get_forms_list(self):
        code = {"code": self.passcode}
        response = self.client.post(
            "/api/v1/device/auth",
            code,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # 1 registration form + monitoring forms (explicitly assigned)
        expected_count = 1 + self.form_children.count()
        self.assertEqual(len(data["formsUrl"]), expected_count)

        # Check if the form children are included in the response
        for form_child in self.form_children:
            self.assertIn(
                {
                    "id": form_child.id,
                    "parentId": self.form.id,
                    "version": str(self.form.version),
                    "url": f"/form/{form_child.id}",
                },
                data["formsUrl"],
            )

    def test_get_form_details(self):
        token = self.get_assignment_token(self.passcode)
        response = self.client.get(
            f"/api/v1/device/form/{self.form.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertCountEqual(
            list(data),
            [
                "id",
                "name",
                "version",
                "cascades",
                "approval_instructions",
                "parent",
                "question_group",
                "languages",
                "default_language",
                "translations",
            ],
        )
        self.assertEqual(data["id"], self.form.id)
        self.assertEqual(data["name"], self.form.name)
        self.assertEqual(data["version"], self.form.version)
        self.assertEqual(data["parent"], None)
