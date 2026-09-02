from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_data.models import FormData
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeolocationIncludeMonitoringTestCases(
    VisualizationValuesTestMixin, APITestCase
):
    """Test include_monitoring filter on /maps/geolocation/{form_id}.

    Mixin pre-creates two registrations and four monitoring children:
        reg1 (Site Alpha) → mon1a (2025-01-15), mon1b (2025-03-10)
        reg2 (Site Beta)  → mon2a (2025-01-20), mon2b (2025-03-15)
    """

    BASE_URL = "/api/v1/maps/geolocation"

    def test_include_monitoring_with_from_date(self):
        """from_date filters by monitoring children's created."""
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-02-01&include_monitoring=true"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        # Both regs have a monitoring child after Feb 1 (reg1: mar 10,
        # reg2: mar 15) so both appear.
        self.assertEqual(names, ["Site Alpha", "Site Beta"])

    def test_include_monitoring_with_window(self):
        """from_date + to_date narrow to a window of monitoring."""
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-01-18&to_date=2025-01-22"
            "&include_monitoring=true"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        # Only reg2's mon2a (Jan 20) falls in the window.
        self.assertEqual(names, ["Site Beta"])

    def test_include_monitoring_excludes_when_no_child_in_window(self):
        """Reg with no monitoring child in the window is omitted."""
        # Only reg2 has a monitoring child after Mar 12.
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-03-12&include_monitoring=true"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Beta"])

    def test_include_monitoring_excludes_pending_children(self):
        """Pending monitoring children do not satisfy the filter."""
        # Mark all of reg1's monitoring children as pending.
        FormData.objects.filter(parent=self.reg1).update(is_pending=True)
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-01-01&include_monitoring=true"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Beta"])

    def test_include_monitoring_excludes_draft_children(self):
        """Draft monitoring children do not satisfy the filter."""
        FormData.objects.filter(parent=self.reg1).update(is_draft=True)
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-01-01&include_monitoring=true"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Beta"])

    def test_include_monitoring_false_filters_registration_created(self):
        """Without include_monitoring, dates filter the registration."""
        # Force reg1 created in Jan, reg2 in Jun
        from django.utils.timezone import make_aware
        from datetime import datetime
        FormData.objects.filter(id=self.reg1.id).update(
            created=make_aware(datetime(2025, 1, 10)),
        )
        FormData.objects.filter(id=self.reg2.id).update(
            created=make_aware(datetime(2025, 6, 10)),
        )
        # include_monitoring not set → registration date applies.
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
            "?from_date=2025-05-01"
        )
        self.assertEqual(response.status_code, 200)
        names = sorted(row["name"] for row in response.json())
        self.assertEqual(names, ["Site Beta"])

    def test_geolocation_payload_is_lean(self):
        response = self.client.get(
            f"{self.BASE_URL}/{self.registration.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data), 0)
        for row in data:
            self.assertIn("id", row)
            self.assertIn("name", row)
            self.assertIn("geo", row)
            self.assertNotIn("administration_full_name", row)
            self.assertNotIn("updated", row)
