import time
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from faker import Faker

fake = Faker()


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeolocationListTestCases(TestCase, ProfileTestHelperMixin):
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
        self.call_command(repeat=2, test=True, approved=True, draft=False)
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

    def test_geolocation_list_exclude_draft(self):
        """Test that the geolocation list excludes draft data."""
        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data), 0)
        self.assertEqual(
            list(data[0]),
            ["id", "name", "geo", "administration_id"]
        )
        # Ensure draft data is not included in the response
        self.assertNotIn(self.draft_data.id, [d["id"] for d in data])

        # Ensure the geolocation is correctly formatted
        self.assertIsInstance(data[0]["geo"], list)
        # The list response carries coordinates and a label, nothing
        # more; the map widget renders its popup from exactly this.
        self.assertNotIn("administration_full_name", data[0])
        self.assertNotIn("updated", data[0])

    def test_get_geolocation_list_with_administration_filter(self):
        """
            Test that the geolocation list can be filtered by administration.
        """
        admin = self.data.administration
        response = self.client.get(
            (
                f"/api/v1/maps/geolocation/{self.form.id}"
                f"?administration={admin.id}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data), 0)
        self.assertIn(
            admin.id,
            [d["administration_id"] for d in data],
        )

    def test_get_geolocation_list_with_invalid_administration_filter(self):
        """
            Test that an invalid administration filter returns an empty list.
        """
        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.form.id}?administration=9999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, [])

    def test_get_geolocation_list_with_invalid_form_id(self):
        """
            Test that an invalid form ID returns a 404 error.
        """
        response = self.client.get(
            "/api/v1/maps/geolocation/9999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_get_geolocation_list_with_an_authenticated_request(self):
        """
            Test that an authenticated request to the geolocation
            list succeeds.
        """
        # Formerly "with_unauthenticated_user": this class uses plain
        # django.test.TestCase, so self.client has no .credentials()
        # (that's DRF APIClient-only, see VisualizationValuesTestMixin
        # .setUp); the per-request header every other test in this
        # file already passes is used here too. #352's anonymous path
        # now requires a dashboard_slug this request never supplies,
        # so this authenticates the same way the rest of the file
        # does rather than testing a request shape the endpoint no
        # longer answers with 200. The genuinely anonymous case --
        # no dashboard_slug returns 404 -- is covered next to
        # test_no_slug_is_404 in tests_public_dashboard_access.py's
        # PublicEndpointAccessTestCase, which owns the anonymous
        # boundary's regression tests.
        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_performance_geolocation_list(self):
        """
            Test the performance of the geolocation list endpoint
            with a large number of entries.
        """
        # Delete existing data entries to ensure a clean state
        self.form.form_form_data.all().delete(hard=True)
        # Create additional data entries to test performance
        for _ in range(1000):
            random_adm = Administration.objects.filter(
                level__level__gte=1
            ).order_by("?").first()
            fake_geo = fake.local_latlng(country_code="ID", coords_only=True)
            self.form.form_form_data.create(
                name="Performance Data",
                administration=random_adm,
                geo=fake_geo,
                created_by=self.user,
                updated_by=self.user,
                is_pending=False,
                is_draft=False,
            )
            # add_fake_answers(new_data)
        # Calculate the time taken for the response
        start_time = time.time()
        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        end_time = time.time()
        duration = end_time - start_time
        self.assertLess(duration, 2)  # Ensure response time is under 2 seconds
        self.assertEqual(response.status_code, 200)

    def test_geolocation_list_by_non_superuser(self):
        """
            Test that a non-superuser can access the geolocation list
            and that the administration filter works correctly.
        """
        adm = self.data.administration
        non_superuser = self.create_user(
            email="non_superuser@example.com",
            role_level=self.IS_ADMIN,
            administration=adm,
            form=self.form,
        )
        non_superuser.set_password("test")
        non_superuser.save()

        non_superuser_token = self.get_auth_token(
            non_superuser.email, "test"
        )

        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {non_superuser_token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data), 0)

        user_role = non_superuser.user_user_role.order_by(
            "administration__level__level"
        ).first()
        self.assertIn(
            user_role.administration.id,
            [d["administration_id"] for d in data],
        )

    def test_geolocation_list_with_no_data_due_user_role_empty(self):
        """
            Test that the geolocation list returns an empty list
            when the user has no roles or administrations.
        """
        no_role_user = self.create_user(
            email="no_role_user@example.com",
            role_level=self.IS_ADMIN,
            form=self.form,
        )
        no_role_user.set_password("test")
        no_role_user.save()

        no_role_user_token = self.get_auth_token(
            no_role_user.email, "test"
        )

        no_role_user.user_user_role.all().delete()  # Ensure no roles exist

        response = self.client.get(
            f"/api/v1/maps/geolocation/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {no_role_user_token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, [])
