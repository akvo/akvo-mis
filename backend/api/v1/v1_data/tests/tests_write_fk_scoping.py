from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Role
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class WriteFkScopingTestCase(TenantIsolationTestCase):
    """A payload may not reference another tenant's object.

    These are 400s rather than 404s: the object addressed by the URL is
    the caller's own, it is a value inside the payload that is invalid.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["role"] = Role.objects.create(
            name=f"{sub}-role", administration_level=tenant["level"]
        )
        return tenant

    def test_add_user_rejects_foreign_role(self):
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "X", "last_name": "Y",
                "email": "x@acme.org",
                "roles": [{
                    "role": self.b["role"].id,
                    "administration": self.a["root"].id,
                }],
                "forms": [], "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)

    def test_add_user_rejects_foreign_administration(self):
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "X", "last_name": "Y",
                "email": "x2@acme.org",
                "roles": [{
                    "role": self.a["role"].id,
                    "administration": self.b["root"].id,
                }],
                "forms": [], "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)

    def test_administration_create_rejects_foreign_parent(self):
        res = self.client.post(
            "/api/v1/administrations",
            {
                "name": "Sneaky",
                "parent": self.b["root"].id,
                "level": self.b["child_level"].id,
                "code": "SN1",
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(
            Administration.objects.filter(name="Sneaky").exists()
        )

    def test_form_data_submission_rejects_foreign_administration(self):
        res = self.client.post(
            f"/api/v1/form-data/{self.a['form'].id}",
            {
                "administration": self.b["child"].id,
                "name": "dp",
                "answers": {},
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)
