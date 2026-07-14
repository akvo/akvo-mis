import typing
from django.core.management import call_command
from django.http import HttpResponse
from django.test import TestCase, override_settings
from rest_framework import status
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False)
class SelectiveMonitoringFormsTestCase(
    TestCase, ProfileTestHelperMixin, AssignmentTokenTestHelperMixin
):
    """
    Tests for selective monitoring form assignment feature.

    This feature allows administrators to selectively assign individual
    monitoring forms to mobile users, instead of automatically including
    all monitoring forms associated with a registration form.
    """

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.user = self.create_user("test@akvo.org", self.IS_ADMIN)
        self.token = self.get_auth_token(self.user.email)

        # Get registration form that has monitoring children
        self.registration_form = Forms.objects.filter(
            parent__isnull=True,
            status=FormStatus.published,
            children__isnull=False
        ).distinct().first()

        # Get monitoring form that is a child of the registration form
        self.monitoring_form = Forms.objects.filter(
            parent=self.registration_form,
            status=FormStatus.published
        ).first()

        self.administration = Administration.objects.filter(
            level__level__gt=0
        ).first()

    def test_create_assignment_with_monitoring_form_without_parent_fails(self):
        """
        Creating an assignment with a monitoring form but without its
        parent registration form should fail with validation error.
        """
        payload = {
            "name": "test assignment",
            "forms": [self.monitoring_form.id],
            "administrations": [self.administration.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                "/api/v1/mobile-assignments",
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("forms", data)
        # Check error contains required registration info
        error = data["forms"][0]
        self.assertEqual(error["form"], str(self.monitoring_form.id))
        self.assertIn("required_registration", error)

    def test_create_assignment_with_monitoring_and_registration_succeeds(self):
        """
        Creating an assignment with both a monitoring form and its
        parent registration form should succeed.
        """
        payload = {
            "name": "test assignment",
            "forms": [self.registration_form.id, self.monitoring_form.id],
            "administrations": [self.administration.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                "/api/v1/mobile-assignments",
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(len(data["forms"]), 2)
        form_ids = [f["id"] for f in data["forms"]]
        self.assertIn(self.registration_form.id, form_ids)
        self.assertIn(self.monitoring_form.id, form_ids)

    def test_create_assignment_with_only_registration_succeeds(self):
        """
        Creating an assignment with only a registration form
        (no monitoring forms) should succeed.
        """
        payload = {
            "name": "test assignment",
            "forms": [self.registration_form.id],
            "administrations": [self.administration.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                "/api/v1/mobile-assignments",
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(len(data["forms"]), 1)
        self.assertEqual(data["forms"][0]["id"], self.registration_form.id)
        self.assertEqual(data["forms"][0]["type"], "registration")

    def test_forms_response_includes_type_field(self):
        """
        The forms field in assignment response should include
        a 'type' field indicating 'registration' or 'monitoring'.
        """
        payload = {
            "name": "test assignment",
            "forms": [self.registration_form.id, self.monitoring_form.id],
            "administrations": [self.administration.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                "/api/v1/mobile-assignments",
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        for form in data["forms"]:
            self.assertIn("type", form)
            self.assertIn(form["type"], ["registration", "monitoring"])

    def test_sync_returns_only_assigned_forms(self):
        """
        When syncing, only explicitly assigned forms should be returned,
        not auto-included monitoring forms.
        """
        # Create assignment with only registration form
        passcode = "testpass"
        assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=passcode
        )
        assignment.forms.add(self.registration_form)
        assignment.administrations.add(self.administration)

        # Sync and check forms returned
        response = self.client.post(
            "/api/v1/device/auth",
            {"code": passcode},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should only return the registration form, not monitoring forms
        self.assertEqual(len(data["formsUrl"]), 1)
        self.assertEqual(data["formsUrl"][0]["id"], self.registration_form.id)

    def test_sync_returns_both_when_explicitly_assigned(self):
        """
        When both registration and monitoring forms are explicitly assigned,
        sync should return both.
        """
        passcode = "testpass2"
        assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment 2", passcode=passcode
        )
        assignment.forms.add(self.registration_form)
        assignment.forms.add(self.monitoring_form)
        assignment.administrations.add(self.administration)

        response = self.client.post(
            "/api/v1/device/auth",
            {"code": passcode},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["formsUrl"]), 2)
        form_ids = [f["id"] for f in data["formsUrl"]]
        self.assertIn(self.registration_form.id, form_ids)
        self.assertIn(self.monitoring_form.id, form_ids)


@override_settings(USE_TZ=False)
class FormsTreeEndpointTestCase(TestCase, ProfileTestHelperMixin):
    """
    Tests for the /api/v1/forms-tree endpoint.

    This endpoint returns published forms in a hierarchical tree structure
    with registration forms as parents and monitoring forms as children.
    """

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.user = self.create_user("test@akvo.org", self.IS_ADMIN)
        self.token = self.get_auth_token(self.user.email)

    def test_forms_tree_requires_authentication(self):
        """The forms-tree endpoint should require authentication."""
        response = self.client.get(
            "/api/v1/forms-tree",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_forms_tree_returns_hierarchical_structure(self):
        """
        The forms-tree endpoint should return forms in hierarchical structure
        with registration forms as parents and monitoring forms as children.
        """
        response = typing.cast(
            HttpResponse,
            self.client.get(
                "/api/v1/forms-tree",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)

        # Check structure of each registration form
        for reg_form in data:
            self.assertIn("id", reg_form)
            self.assertIn("name", reg_form)
            self.assertIn("type", reg_form)
            self.assertIn("children", reg_form)
            self.assertEqual(reg_form["type"], "registration")
            self.assertIsInstance(reg_form["children"], list)

            # Check structure of each monitoring form (child)
            for mon_form in reg_form["children"]:
                self.assertIn("id", mon_form)
                self.assertIn("name", mon_form)
                self.assertIn("type", mon_form)
                self.assertEqual(mon_form["type"], "monitoring")

    def test_forms_tree_only_includes_published_forms(self):
        """
        The forms-tree endpoint should only include published forms.
        """
        # Get a form and mark it as draft
        form = Forms.objects.filter(
            parent__isnull=True,
            status=FormStatus.published
        ).first()
        original_status = form.status
        form.status = FormStatus.draft
        form.save()

        response = typing.cast(
            HttpResponse,
            self.client.get(
                "/api/v1/forms-tree",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        form_ids = [f["id"] for f in data]
        self.assertNotIn(form.id, form_ids)

        # Restore form status
        form.status = original_status
        form.save()

    def test_forms_tree_children_match_parent_relationship(self):
        """
        The monitoring forms listed as children should actually have
        the registration form as their parent in the database.
        """
        response = typing.cast(
            HttpResponse,
            self.client.get(
                "/api/v1/forms-tree",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        for reg_form in data:
            reg_id = reg_form["id"]
            for mon_form in reg_form["children"]:
                # Verify the monitoring form's parent is this registration form
                db_mon_form = Forms.objects.get(id=mon_form["id"])
                self.assertEqual(db_mon_form.parent_id, reg_id)
