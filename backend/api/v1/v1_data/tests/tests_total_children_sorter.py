from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormDataSortingTestCase(TestCase, ProfileTestHelperMixin):
    """Test cases for sorting form data list."""

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

        # Create test data with different names and child counts
        self.data_a = self.form.form_form_data.create(
            name="AAA Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        add_fake_answers(self.data_a)

        self.data_z = self.form.form_form_data.create(
            name="ZZZ Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        add_fake_answers(self.data_z)

        # Create children for data_z (so it has more children)
        for _ in range(3):
            child = self.child_form.form_form_data.create(
                parent=self.data_z,
                name="Child of ZZZ",
                administration=self.administration,
                geo=[0.0, 0.0],
                created_by=self.user,
                updated_by=self.user,
                is_pending=False,
            )
            add_fake_answers(child)

    def test_sort_by_name_ascending(self):
        """Test sorting by name in ascending order."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?sort_by=name&sort_type=ascend",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 1)

        names = [item["name"] for item in data["data"]]
        self.assertEqual(names, sorted(names))

    def test_sort_by_name_descending(self):
        """Test sorting by name in descending order."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?sort_by=name&sort_type=descend",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 1)

        names = [item["name"] for item in data["data"]]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_sort_by_total_children_descending(self):
        """Test sorting by total_children in descending order."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=total_children&sort_type=descend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 1)

        counts = [item["total_children"] for item in data["data"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_sort_by_total_children_ascending(self):
        """Test sorting by total_children in ascending order."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=total_children&sort_type=ascend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 1)

        counts = [item["total_children"] for item in data["data"]]
        self.assertEqual(counts, sorted(counts))

    def test_default_sort_by_created_descending(self):
        """Test default sorting is by created in descending order."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 1)

        # Most recently created should be first (descending)
        # data_z was created after data_a
        ids = [item["id"] for item in data["data"]]
        self.assertIn(self.data_z.id, ids)
        self.assertIn(self.data_a.id, ids)
        # data_z should come before data_a in the list
        self.assertLess(ids.index(self.data_z.id), ids.index(self.data_a.id))

    def test_invalid_sort_by_returns_error(self):
        """Test that invalid sort_by value returns error."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?sort_by=invalid_field",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_sort_type_returns_error(self):
        """Test that invalid sort_type value returns error."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?sort_type=invalid_type",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
