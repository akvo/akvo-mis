from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Levels
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin

TEMPLATE_URL = "/api/v1/export/administrations-template"
ENTITY_TEMPLATE_URL = "/api/v1/export/entity-data-template"
UPLOAD_URL = "/api/v1/upload/bulk-administrations"


@override_settings(USE_TZ=False, TEST_ENV=True)
class BulkUploadGateTestCase(TestCase, TenantTestHelperMixin):
    """A tenant fresh out of configuration: one named level, one root unit.

    That is the state the gate exists to catch. Its template would be a
    single column holding the root the tenant already has, and an upload
    against it could say nothing new — so both are refused until the
    tenant adds a tier below the root.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")

    def _auth(self):
        return self.bearer(self.acme.admin)

    def _add_province(self):
        return Levels.objects.create(
            name="Province", level=1, tenant=self.acme.tenant
        )

    def test_template_export_blocked_with_only_a_root_level(self):
        res = self.client.get(TEMPLATE_URL, **self._auth())
        self.assertEqual(res.status_code, 400)
        self.assertIn("administrative levels", res.json()["message"])

    def test_entities_template_export_blocked_with_only_a_root_level(self):
        res = self.client.get(ENTITY_TEMPLATE_URL, **self._auth())
        self.assertEqual(res.status_code, 400)
        self.assertIn("administrative levels", res.json()["message"])

    def test_upload_blocked_with_only_a_root_level(self):
        res = self.client.post(UPLOAD_URL, {}, **self._auth())
        self.assertEqual(res.status_code, 400)
        self.assertIn("administrative levels", res.json()["message"])

    def test_template_export_allowed_once_a_deeper_level_exists(self):
        self._add_province()
        res = self.client.get(TEMPLATE_URL, **self._auth())
        self.assertEqual(res.status_code, 200)
        self.assertIn("spreadsheetml.sheet", res["Content-Type"])

    def test_upload_reaches_file_validation_once_the_gate_is_met(self):
        # Paired with the refusal above so that test cannot pass merely
        # because the route is missing: with the gate met the same empty
        # POST is still a 400, but from the file serializer rather than
        # the gate.
        self._add_province()
        res = self.client.post(UPLOAD_URL, {}, **self._auth())
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("administrative levels", res.json()["message"])

    def test_unnamed_level_zero_blocks_even_with_a_deeper_level(self):
        # Configuration names level 0, so this is the pre-configuration
        # tenant rather than anything a configured one can reach — but the
        # gate is two conditions and both are load-bearing.
        self._add_province()
        Levels.objects.filter(pk=self.acme.levels[0].pk).update(name="")
        res = self.client.get(TEMPLATE_URL, **self._auth())
        self.assertEqual(res.status_code, 400)

    def test_another_tenants_levels_do_not_open_the_gate(self):
        self.create_tenant("beta", ["State", "City"], "Uganda")
        res = self.client.get(TEMPLATE_URL, **self._auth())
        self.assertEqual(res.status_code, 400)
