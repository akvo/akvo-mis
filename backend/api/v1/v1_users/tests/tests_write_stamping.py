from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttribute,
    Entity,
    Role,
)
from api.v1.v1_users.models import Organisation, SystemUser
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class WriteStampingTestCase(TenantIsolationTestCase):
    """Everything tenant A creates must come out owned by A.

    Before this iteration these all landed with tenant = NULL, which the
    read filtering then hid from their own creator.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["role"] = Role.objects.create(
            name=f"{sub}-role", administration_level=tenant["level"]
        )
        return tenant

    def test_form_create_is_stamped(self):
        res = self.client.post(
            "/api/v1/manage/forms",
            {"name": "Household Survey", "type": 1},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)
        form = Forms.objects.get(name="Household Survey")
        self.assertEqual(form.tenant, self.a["tenant"])

    def test_entity_create_is_stamped(self):
        res = self.client.post(
            "/api/v1/entities",
            {"name": "Water Point"},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            Entity.objects.get(name="Water Point").tenant, self.a["tenant"]
        )

    def test_attribute_create_is_stamped(self):
        res = self.client.post(
            "/api/v1/administration-attributes",
            {"name": "Population", "type": "value", "options": []},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            AdministrationAttribute.objects.get(name="Population").tenant,
            self.a["tenant"],
        )

    def test_organisation_create_is_stamped(self):
        res = self.client.post(
            "/api/v1/organisation",
            {"name": "Ministry of Water", "attributes": [1]},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            Organisation.objects.get(name="Ministry of Water").tenant,
            self.a["tenant"],
        )

    def test_administration_create_is_stamped(self):
        res = self.client.post(
            "/api/v1/administrations",
            {
                "name": "New District",
                "parent": self.a["root"].id,
                "level": self.a["child_level"].id,
                "code": "ND1",
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            Administration.objects.get(name="New District").tenant,
            self.a["tenant"],
        )

    def test_created_rows_are_visible_to_their_creator(self):
        # The regression that made iteration 3 undeployable: a create
        # succeeded, landed tenant-less, and vanished from every list.
        self.client.post(
            "/api/v1/entities",
            {"name": "Borehole"},
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        res = self.client.get("/api/v1/entities", **self.auth(self.a["user"]))
        names = [e["name"] for e in res.json()["data"]]
        self.assertIn("Borehole", names)

    def test_user_create_is_stamped(self):
        res = self.client.post(
            "/api/v1/user",
            {
                "first_name": "New",
                "last_name": "Member",
                "email": "member@acme.org",
                "administration": self.a["root"].id,
                "role": self.a["role"].id,
                "forms": [],
                "trained": False,
            },
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertIn(res.status_code, (200, 201))
        self.assertEqual(
            SystemUser.objects.get(email="member@acme.org").tenant,
            self.a["tenant"],
        )

    def test_duplicated_form_keeps_the_tenant(self):
        res = self.client.post(
            f"/api/v1/manage/forms/{self.a['form'].id}/duplicate",
            content_type="application/json",
            **self.auth(self.a["user"]),
        )
        self.assertIn(res.status_code, (200, 201))
        copy = Forms.objects.get(name=f"{self.a['form'].name} (Copy)")
        self.assertEqual(copy.tenant, self.a["tenant"])
