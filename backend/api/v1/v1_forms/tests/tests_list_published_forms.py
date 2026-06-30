from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import FormStatus


@override_settings(USE_TZ=False, TEST_ENV=True)
class ListPublishedFormsTestCase(TestCase):
    """GET /api/v1/forms/published — runtime forms feed for the web app.

    Replaces the window.forms global baked into config.min.js.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.url = "/api/v1/forms/published"

    def test_returns_200_without_auth(self):
        """Public, like config.js — no authentication required."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)

    def test_sets_no_cache_header(self):
        """Cache-Control: no-cache prevents the browser-cache staleness."""
        res = self.client.get(self.url)
        self.assertEqual(res["Cache-Control"], "no-cache")

    def test_item_shape_matches_baked_forms(self):
        """Each item has id, name, version and full content."""
        data = self.client.get(self.url).json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        item = data[0]
        self.assertEqual(
            sorted(item.keys()), ["content", "id", "name", "version"]
        )
        self.assertIn("question_group", item["content"])

    def test_returns_all_published_forms_including_children(self):
        """Mirrors generate_config: every published form, parents AND
        children (unlike /forms which filters parent__isnull)."""
        published_ids = set(
            Forms.objects.filter(
                status=FormStatus.published
            ).values_list("id", flat=True)
        )
        data = self.client.get(self.url).json()
        returned_ids = {item["id"] for item in data}
        self.assertEqual(returned_ids, published_ids)

    def test_excludes_unpublished_forms(self):
        """Draft/unpublished forms must not leak into the feed."""
        form = Forms.objects.filter(status=FormStatus.published).first()
        form.status = FormStatus.draft
        form.save(update_fields=["status"])

        data = self.client.get(self.url).json()
        returned_ids = {item["id"] for item in data}
        self.assertNotIn(form.id, returned_ids)
