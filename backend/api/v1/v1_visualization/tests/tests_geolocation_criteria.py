from datetime import datetime

from django.test.utils import override_settings
from django.utils.timezone import make_aware
from rest_framework.test import APITestCase

from api.v1.v1_data.models import Answers
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeolocationCriteriaTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """Test criteria filter on /maps/geolocation/{form_id}."""

    BASE_URL = "/api/v1/maps/geolocation"

    def setUp(self):
        super().setUp()
        # Add an option answer on the registration form for reg1
        # (Site Alpha) so we have something to filter against.
        Answers.objects.create(
            data=self.reg1,
            question=self.q_reg_option,
            options=["type_a"],
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.reg2,
            question=self.q_reg_option,
            options=["type_b"],
            created_by=self.user,
        )

    def test_criteria_narrows_map_results(self):
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?criteria=option_equals"
            f":{self.q_reg_option.id}:type_a"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = [row["name"] for row in data]
        self.assertEqual(names, ["Site Alpha"])

    def test_criteria_malformed_returns_200_empty(self):
        """Serializer invalid → view returns empty (existing behavior)."""
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?criteria=bogus:1:2"
        )
        # GeoLocationFilterSerializer.is_valid() failure returns [] 200.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_no_criteria_returns_all(self):
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = sorted(row["name"] for row in data)
        self.assertEqual(names, ["Site Alpha", "Site Beta"])

    def test_from_date_filters_by_created(self):
        """from_date filters registration records by FormData.created."""
        FormData = type(self.reg1)
        FormData.objects.filter(id=self.reg1.id).update(
            created=make_aware(datetime(2025, 1, 10)),
        )
        FormData.objects.filter(id=self.reg2.id).update(
            created=make_aware(datetime(2025, 6, 10)),
        )
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-05-01"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Beta"])

    def test_to_date_upper_bound(self):
        """to_date bounds registration records.

        Ends before either site's monitoring (01-15 and 01-20): a site
        monitored in the range is in it too (VIZ-027 D-23).
        """
        FormData = type(self.reg1)
        FormData.objects.filter(id=self.reg1.id).update(
            created=make_aware(datetime(2025, 1, 10)),
        )
        FormData.objects.filter(id=self.reg2.id).update(
            created=make_aware(datetime(2025, 6, 10)),
        )
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?to_date=2025-01-12"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Alpha"])

    def test_a_site_monitored_in_the_range_is_in_it(self):
        """Site Beta, registered in June, was monitored in January."""
        FormData = type(self.reg1)
        FormData.objects.filter(id=self.reg2.id).update(
            created=make_aware(datetime(2025, 6, 10)),
        )
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-01-18&to_date=2025-01-25"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Beta"])
