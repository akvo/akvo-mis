import io
import json

from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    import_form_definition,
    normalize_form_definition,
)
from api.v1.v1_forms.tests.tests_form_import_preflight import (
    _make_export_payload,
)
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class FormImportTenantTestCase(TenantIsolationTestCase):
    """Form import is a write path keyed on an id inside the file.

    The id is supplied by whoever uploads the file, so an unscoped match
    would let an import address another tenant's form, and an unstamped
    create would produce a form its own importer cannot see.
    """

    def _upload(self, payload, user, path="/api/v1/manage/forms/import"):
        f = io.BytesIO(json.dumps(payload).encode())
        f.name = "form.json"
        return self.client.post(path, {"file": f}, **self.auth(user))

    def test_preflight_does_not_match_another_tenants_form(self):
        # The file claims beta's form id. For acme that id must look like
        # a form that does not exist, not like an update target.
        res = self._upload(
            _make_export_payload(name="X", form_id=self.b["form"].id),
            self.a["user"],
            path="/api/v1/manage/forms/import/preflight",
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["match"]["exists"])

    def test_imported_form_is_stamped_with_the_importer_tenant(self):
        # The HTTP endpoint enqueues a task, so the create itself is
        # exercised through the function the worker calls.
        norm = normalize_form_definition(
            _make_export_payload(name="Imported Form", form_id=978001)
        )
        form, _ = import_form_definition(
            norm, user=self.a["user"], mode="create"
        )
        self.assertEqual(form.tenant, self.a["tenant"])

    def test_import_foreign_form_id_creates_new_form_in_current_tenant(
        self,
    ):
        foreign_form = self.b["form"]
        original_foreign_name = foreign_form.name

        norm = normalize_form_definition(
            _make_export_payload(
                name="Tenant A New Form",
                form_id=foreign_form.id,
            )
        )
        new_form, action = import_form_definition(
            norm, user=self.a["user"], mode="create_or_update"
        )

        self.assertEqual(action, "created")
        self.assertEqual(new_form.tenant, self.a["tenant"])
        self.assertNotEqual(new_form.id, foreign_form.id)

        # Verify foreign form was not modified
        foreign_form.refresh_from_db()
        self.assertEqual(foreign_form.name, original_foreign_name)
        self.assertEqual(foreign_form.tenant, self.b["tenant"])
