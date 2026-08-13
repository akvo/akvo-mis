from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class ParentFieldsTestCase(TestCase, ProfileTestHelperMixin):
    """Test cases for parent fields in ListFormDataSerializer."""

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.form = Forms.objects.get(pk=1)
        self.child_form = self.form.children.first()
        self.administration = Administration.objects.filter(
            parent__isnull=False
        ).first()

        self.user = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.user.set_password("test")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "test")

        # Create parent registration data
        self.parent_data = self.form.form_form_data.create(
            name="Test Parent Registration Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(self.parent_data)

        # Create child monitoring data
        self.child_data = self.child_form.form_form_data.create(
            parent=self.parent_data,
            name=f"Monitoring of {self.parent_data.name}",
            administration=self.parent_data.administration,
            geo=self.parent_data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(self.child_data)

    def test_monitoring_data_includes_parent_fields(self):
        """Test monitoring data includes parent_name, parent_id,
        parent_form_id."""
        response = self.client.get(
            f"/api/v1/form-data/{self.child_form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertTrue(len(data) > 0)

        child_item = next(
            (item for item in data if item["id"] == self.child_data.id), None
        )
        self.assertIsNotNone(child_item)
        self.assertEqual(child_item["parent_name"], self.parent_data.name)
        self.assertEqual(child_item["parent_id"], self.parent_data.id)
        self.assertEqual(child_item["parent_form_id"], self.form.id)

    def test_registration_data_has_null_parent_fields(self):
        """Test that registration form data has null parent fields."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertTrue(len(data) > 0)

        parent_item = next(
            (item for item in data if item["id"] == self.parent_data.id), None
        )
        self.assertIsNotNone(parent_item)
        self.assertIsNone(parent_item.get("parent_name"))
        self.assertIsNone(parent_item.get("parent_id"))
        self.assertIsNone(parent_item.get("parent_form_id"))
