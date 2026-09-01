from io import StringIO
from datetime import timedelta
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


def administration_label(administration):
    """What ListFormDataSerializer should render for a unit.

    Deliberately expressed as "ancestors minus the root, then the unit"
    rather than by re-splitting full_name -- the string split is the bug
    these assertions used to encode.
    """
    ancestors = list(administration.ancestors or [])
    return " - ".join(
        [a.name for a in ancestors[1:]] + [administration.name]
    )


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormDataListTestCase(TestCase, ProfileTestHelperMixin):
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
        self.maxDiff = None
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.call_command(repeat=2, approved=True, draft=False)
        self.form = Forms.objects.get(pk=1)
        self.data = (
            self.form.form_form_data.filter(
                is_pending=False,
                is_draft=False,
            )
            .order_by("?")
            .first()
        )
        # Create a new superuser
        self.user = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )

        self.user.set_password("test")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "test")

        # Create a draft data entry
        draft_data = self.form.form_form_data.create(
            name="Draft Data",
            administration=self.data.administration,
            geo=self.data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=True,
        )
        add_fake_answers(draft_data)
        self.draft_data = draft_data

    def test_form_data_list_exclude_draft(self):
        """Test that the form data list excludes draft data."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        self.assertNotIn(self.draft_data.id, [d["id"] for d in data["data"]])

    def test_form_data_list_filter_by_administration(self):
        """Test that the form data list can be filtered by administration."""
        adm = self.data.administration
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?administration={adm.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        self.assertIn(
            administration_label(adm),
            [
                item["administration"] for item in data["data"]
            ]
        )

    def test_form_data_list_filter_by_parent(self):
        """Test that the form data list can be filtered by parent."""
        child_form = self.form.children.first()
        response = self.client.get(
            f"/api/v1/form-data/{child_form.id}?parent={self.data.uuid}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)

    def test_form_data_list_search_by_name(self):
        """Test that the form data list can be searched by name."""
        # Create a data entry with a specific name for searching
        search_data = self.form.form_form_data.create(
            name="UniqueSearchableName123",
            administration=self.data.administration,
            geo=self.data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(search_data)
        search_data.name = "UniqueSearchable"
        search_data.save()

        # First verify the data exists without search filter
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        all_ids = [d["id"] for d in data["data"]]
        self.assertIn(search_data.id, all_ids)

        # Now test search functionality
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?search=UniqueSearchable",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], search_data.id)

    def test_form_data_list_search_case_insensitive(self):
        """Test that the search is case-insensitive."""
        search_data = self.form.form_form_data.create(
            name="CaseSensitiveTest",
            administration=self.data.administration,
            geo=self.data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(search_data)
        search_data.name = "CaseSensitiveTest"
        search_data.save()

        # Search with lowercase
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?search=casesensitivetest",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], search_data.id)

        # Search with uppercase
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?search=CASESENSITIVETEST",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], search_data.id)

    def test_form_data_list_search_no_results(self):
        """Test that search returns empty results when no match."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?search=NonExistentName12345",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["data"], [])

    def test_form_data_list_search_combined_with_administration(self):
        """Test that search can be combined with administration filter."""
        search_data = self.form.form_form_data.create(
            name="CombinedFilterTest",
            administration=self.data.administration,
            geo=self.data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(search_data)
        search_data.name = "CombinedFilter"
        search_data.save()
        adm = self.data.administration

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?search=CombinedFilter&administration={adm.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], search_data.id)

    def test_form_data_list_filter_by_date_from(self):
        """Test that the form data list can be filtered by date_from."""
        # Refresh to get actual created date from database
        self.data.refresh_from_db()
        data_created_date = self.data.created.date()

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?date_from={data_created_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Data created on or after date_from should be returned
        self.assertGreater(data["total"], 0)

        # Filter with a far future date should return no results
        future_date = data_created_date + timedelta(days=365)
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?date_from={future_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 0)

    def test_form_data_list_filter_by_date_to(self):
        """Test that the form data list can be filtered by date_to."""
        # Refresh to get actual created date from database
        self.data.refresh_from_db()
        data_created_date = self.data.created.date()

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?date_to={data_created_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Data created on or before date_to should be returned
        self.assertGreater(data["total"], 0)

        # Filter with a far past date should return no results
        past_date = data_created_date - timedelta(days=365)
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?date_to={past_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 0)

    def test_form_data_list_filter_by_date_range(self):
        """Test that the form data list can be filtered by date range."""
        # Refresh to get actual created date from database
        self.data.refresh_from_db()
        data_created_date = self.data.created.date()

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?date_from={data_created_date}&date_to={data_created_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Data created on this date should be returned
        self.assertGreater(data["total"], 0)

    def test_form_data_list_date_range_boundary_inclusivity(self):
        """Test that date range boundaries are inclusive."""
        # Create data entry with specific created timestamp
        boundary_data = self.form.form_form_data.create(
            name="BoundaryTest",
            administration=self.data.administration,
            geo=self.data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(boundary_data)

        # Refresh to get actual created date from database
        boundary_data.refresh_from_db()
        created_date = boundary_data.created.date()

        # Test that data created on date_from is included
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?date_from={created_date}&date_to={created_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        data_ids = [d["id"] for d in data["data"]]
        self.assertIn(boundary_data.id, data_ids)

    def test_form_data_list_invalid_date_range(self):
        """Test that invalid date range returns validation error."""
        self.data.refresh_from_db()
        data_created_date = self.data.created.date()
        yesterday = data_created_date - timedelta(days=1)

        # date_from > date_to should return validation error
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?date_from={data_created_date}&date_to={yesterday}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("date_from", data["message"].lower())

    def test_form_data_list_date_filter_combined_with_search(self):
        """Test that date filter can be combined with search."""
        search_data = self.form.form_form_data.create(
            name="DateSearchCombo",
            administration=self.data.administration,
            geo=self.data.geo,
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
            is_draft=False,
        )
        add_fake_answers(search_data)
        # Explicitly set name after add_fake_answers (follows pattern from
        # other search tests)
        search_data.name = "DateSearchCombo"
        search_data.save()

        # Refresh from database to get actual created timestamp
        search_data.refresh_from_db()
        # Use the actual created date
        created_date = search_data.created.date()

        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?search=DateSearchCombo&date_from={created_date}"
            f"&date_to={created_date}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["id"], search_data.id)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AdministrationLabelTestCase(TestCase, ProfileTestHelperMixin):
    """The Region column must not shred names that contain a hyphen.

    The old implementation split full_name on the bare "-" instead of the
    " - " separator, so "KwaZulu-Natal" came back as two tiers and every
    part kept its surrounding spaces.
    """

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        root = Administration.objects.filter(parent__isnull=True).first()
        level_1 = Levels.objects.get(level=1)
        level_2 = Levels.objects.get(level=2)
        self.province = Administration.objects.create(
            name="KwaZulu-Natal", parent=root, level=level_1
        )
        self.district = Administration.objects.create(
            name="Umgungundlovu-West", parent=self.province, level=level_2
        )

        self.user = self.create_user(
            email="hyphen@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.user.set_password("test")
        self.user.save()
        self.token = self.get_auth_token(self.user.email, "test")

        self.form = Forms.objects.get(pk=1)
        self.datapoint = self.form.form_form_data.create(
            name="Hyphen test",
            administration=self.district,
            geo=[0, 0],
            created_by=self.user,
        )

    def test_hyphenated_names_survive_intact(self):
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?administration={self.district.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        labels = [row["administration"] for row in response.json()["data"]]
        self.assertIn("KwaZulu-Natal - Umgungundlovu-West", labels)

    def test_label_has_no_stray_whitespace(self):
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?administration={self.district.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        for label in [r["administration"] for r in response.json()["data"]]:
            self.assertEqual(label, label.strip())
            self.assertNotIn("  ", label)

    def test_root_is_dropped(self):
        # The list is already scoped to one workspace, so the country
        # adds nothing to every row.
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}"
            f"?administration={self.district.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        root = Administration.objects.filter(parent__isnull=True).first()
        for label in [r["administration"] for r in response.json()["data"]]:
            self.assertFalse(label.startswith(root.name))
