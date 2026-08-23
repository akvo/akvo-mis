from django.core.management import call_command
from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_forms.models import Forms


@override_settings(USE_TZ=False, TEST_ENV=True)
class VisualizationAuthTestCase(APITestCase):
    """No endpoint in v1_visualization may answer an anonymous caller."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.form = Forms.objects.filter(parent__isnull=True).first()

    def test_every_endpoint_rejects_anonymous(self):
        # The client sends no credentials at all. Each of the eight
        # endpoints must refuse before doing any work.
        form_id = self.form.id
        urls = [
            "/api/v1/visualization/monitoring-stats"
            "?parent_id=1&question_id=1",
            f"/api/v1/visualization/formdata-stats/{form_id}",
            f"/api/v1/maps/geolocation/{form_id}",
            "/api/v1/maps/datapoint/1",
            f"/api/v1/visualization/values/formula?form_id={form_id}",
            f"/api/v1/visualization/values?form_id={form_id}",
            f"/api/v1/visualization/escalation/{form_id}",
            f"/api/v1/visualization/progress/{form_id}",
        ]
        self.assertEqual(len(urls), 8)
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 401, f"{url} answered anonymously"
            )
