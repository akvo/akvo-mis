from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class TotalChildrenTestCase(TestCase, ProfileTestHelperMixin):
    """Test cases for total_children field in ListFormDataSerializer."""

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

        # Create parent data without any seeder children
        self.parent_data = self.form.form_form_data.create(
            name="Test Parent Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        add_fake_answers(self.parent_data)

    def _create_child_data(self, parent, is_pending=False):
        """Helper to create child FormData."""
        child = self.child_form.form_form_data.create(
            parent=parent,
            name=f"Child of {parent.name}",
            administration=parent.administration,
            geo=parent.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=is_pending,
        )
        add_fake_answers(child)
        return child

    def test_total_children_field_present_in_response(self):
        """Test that total_children field is present in list response."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        self.assertIn("total_children", data["data"][0])

    def test_total_children_counts_approved_children_only(self):
        """Test that total_children only counts approved children."""
        # Create approved children
        self._create_child_data(
            self.parent_data, is_pending=False
        )
        self._create_child_data(
            self.parent_data, is_pending=False
        )

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        parent_item = next(
            (
                item
                for item in data["data"]
                if item["id"] == self.parent_data.id
            ),
            None
        )
        self.assertIsNotNone(parent_item)
        self.assertGreaterEqual(parent_item["total_children"], 2)

    def test_total_children_excludes_pending_children(self):
        """Test that total_children excludes pending children."""
        # Create one approved and one pending child
        self._create_child_data(
            self.parent_data, is_pending=False
        )
        self._create_child_data(
            self.parent_data, is_pending=True
        )

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        parent_item = next(
            (
                item
                for item in data["data"]
                if item["id"] == self.parent_data.id
            ),
            None
        )
        self.assertIsNotNone(parent_item)
        # Should only count the approved child, not the pending one
        self.assertEqual(parent_item["total_children"], 1)

    def test_total_children_zero_when_no_approved_children(self):
        """Test that total_children is 0 when no approved children exist."""
        # Create only pending children
        self._create_child_data(
            self.parent_data, is_pending=True
        )

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        parent_item = next(
            (
                item
                for item in data["data"]
                if item["id"] == self.parent_data.id
            ),
            None
        )
        self.assertIsNotNone(parent_item)
        self.assertEqual(parent_item["total_children"], 0)


@override_settings(USE_TZ=False, TEST_ENV=True)
class TotalChildrenParentFilterTestCase(TestCase, ProfileTestHelperMixin):
    """Test cases for total_children when filtering by parent."""

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.call_command(repeat=2, approved=True)

        self.form = Forms.objects.get(pk=1)
        self.child_form = self.form.children.first()

        # Get approved parent data from seeder
        self.parent_data = (
            self.form.form_form_data.filter(
                is_pending=False,
            )
            .order_by("?")
            .first()
        )

        self.user = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.user.set_password("test")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "test")

    def test_parent_filter_total_children_field_present(self):
        """Test total_children present when filtering by parent."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.child_form.id}"
                f"?parent={self.parent_data.uuid}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        self.assertIn("total_children", data["data"][0])
