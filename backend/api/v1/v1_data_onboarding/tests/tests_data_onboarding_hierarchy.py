import json
import os
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings

from api.v1.v1_data_onboarding.tests.tests_data_onboarding_draft import (
    openai_client,
    proposal,
)
from api.v1.v1_data_onboarding.models import DataOnboarding
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    RoleFeatureAccess,
    UserRole,
)
from api.v1.v1_users.models import SystemUser
from utils.tenant_test_case import TenantIsolationTestCase

URL = "/api/v1/data-onboarding"

CSV = (
    "site_id;site_name;district;village\n"
    "S-001;Alpha;North;Hill\n"
    "S-002;Beta;South;Vale\n"
    "S-003;Gamma;acme-d;Dale\n"
)


def three_levels():
    p = proposal()
    p["administration"].update(
        levels=["Country", "District", "Village"],
        source={"sheet": "csv", "columns": ["district", "village"]},
        units=[["South", "Vale"]],
    )
    p["data"][0].update(
        administration_columns=["district", "village"],
        columns=[{"question": "site_name", "column": "site_name"}],
        value_maps=[],
    )
    return p


@override_settings(
    USE_TZ=False, TEST_ENV=True, BASE_DOMAIN="app.com",
    OPENAI_API_KEY="sk-test-mock-key",
)
class HierarchyLimitsTestCase(TenantIsolationTestCase):
    """Who may add levels and units, and where rows may load."""

    def setUp(self):
        super().setUp()
        self.store = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.store)

        def upload(file, folder=None, filename=None):
            shutil.copyfile(file, os.path.join(self.store, filename))

        def download(url):
            return os.path.join(self.store, url.split("/")[-1])

        for target, kwargs in (
            ("api.v1.v1_data_onboarding.views.storage.upload",
             {"side_effect": upload}),
            ("api.v1.v1_data_onboarding.tasks.storage.download",
             {"side_effect": download}),
            ("api.v1.v1_data_onboarding.views.async_task",
             {"return_value": "task-id"}),
        ):
            p = patch(target, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        self.tenant = self.a["tenant"]
        self.root = self.a["root"]
        self.admin = self.a["user"]

    def fresh(self):
        """Leave the tenant with just the root."""
        self.a["child"].delete()
        self.a["child_level"].delete()

    def populated(self):
        """Root > North, acme-d; three levels."""
        Levels.objects.create(name="village", level=2, tenant=self.tenant)
        self.north = Administration.objects.create(
            parent=self.root, level=self.a["child_level"], name="North",
            tenant=self.tenant,
        )

    def scoped(self, administration):
        user = SystemUser.objects.create_user(
            email="team@acme.org", password="Secret#Pass123",
            first_name="T", last_name="T", tenant=self.tenant,
        )
        role = Role.objects.create(
            name="data team", administration_level=administration.level,
        )
        RoleFeatureAccess.objects.create(
            role=role, type=FeatureTypes.data_onboarding,
            access=FeatureAccessTypes.data_onboard,
        )
        UserRole.objects.create(
            user=user, role=role, administration=administration
        )
        return user

    def host(self):
        return {"HTTP_HOST": "acme.app.com"}

    def draft(self, user, p):
        from api.v1.v1_data_onboarding.tasks import draft_proposal

        res = self.client.post(
            URL, {"file": SimpleUploadedFile("sites.csv", CSV.encode())},
            **self.auth(user), **self.host(),
        )
        pk = res.json()["id"]
        with patch("openai.OpenAI",
                   return_value=openai_client(json.dumps(p))):
            draft_proposal(pk)
        return pk

    def apply(self, user, pk):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding
        from api.v1.v1_data_onboarding.views import async_task

        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                f"{URL}/{pk}/apply", **self.auth(user), **self.host()
            )
        self.assertEqual(res.status_code, 200)
        args = async_task.call_args
        with patch("openai.OpenAI") as openai:
            apply_onboarding(*args.args[1:], forms=args.kwargs["forms"])
        openai.assert_not_called()
        return self.get(user, pk)

    def get(self, user, pk):
        return self.client.get(
            f"{URL}/{pk}", **self.auth(user), **self.host()
        ).json()

    def level_names(self):
        return list(
            Levels.objects.filter(tenant=self.tenant)
            .order_by("level").values_list("name", flat=True)
        )

    def unit_names(self):
        return sorted(
            Administration.objects.filter(tenant=self.tenant)
            .values_list("name", flat=True)
        )

    def outside(self, body):
        return [
            (i["row"], i["question"], i["kind"])
            for i in body["report"]["issues"]
            if "outside" in i["reason"]
        ]

    def test_super_admin_on_a_fresh_tenant_adds_the_levels(self):
        self.fresh()
        body = self.apply(self.admin, self.draft(self.admin, three_levels()))
        self.assertEqual(body["status"], "applied")
        self.assertEqual(self.level_names(), ["", "District", "Village"])
        self.assertEqual(body["report"]["forms"][0]["loaded"], 3)

    def test_a_scoped_role_cannot_add_levels(self):
        self.fresh()
        user = self.scoped(self.root)
        body = self.get(user, self.draft(user, three_levels()))
        self.assertEqual(body["status"], "failed")
        self.assertIn("Only a super admin", body["error"])
        self.assertEqual(self.level_names(), [""])

    def test_no_one_adds_levels_on_a_populated_tenant(self):
        p = three_levels()
        p["administration"]["levels"].append("Household")
        self.populated()
        body = self.get(self.admin, self.draft(self.admin, p))
        self.assertEqual(body["status"], "failed")
        self.assertIn("below the root", body["error"])
        self.assertEqual(self.level_names(), ["", "district", "village"])

    def test_no_one_adds_levels_below_an_existing_level(self):
        # A level below the root, but no units under it yet.
        self.a["child"].delete()
        body = self.get(self.admin, self.draft(self.admin, three_levels()))
        self.assertEqual(body["status"], "failed")
        self.assertIn("below the root", body["error"])
        self.assertEqual(self.level_names(), ["", "district"])

    def test_apply_rechecks_a_tree_populated_after_the_draft(self):
        self.fresh()
        pk = self.draft(self.admin, three_levels())
        Administration.objects.create(
            parent=self.root, level=Levels.objects.create(
                name="district", level=1, tenant=self.tenant
            ), name="Elsewhere", tenant=self.tenant,
        )
        body = self.apply(self.admin, pk)
        self.assertEqual(body["status"], "failed")
        self.assertIn("below the root", body["error"])
        self.assertEqual(self.unit_names(), ["Elsewhere", "acme"])

    def test_super_admin_on_a_populated_tenant_keeps_the_levels(self):
        self.populated()
        body = self.apply(self.admin, self.draft(self.admin, three_levels()))
        self.assertEqual(body["status"], "applied")
        self.assertEqual(self.level_names(), ["", "district", "village"])
        self.assertEqual(body["report"]["forms"][0]["loaded"], 3)
        self.assertEqual(self.outside(body), [])

    def test_a_scoped_role_loads_only_inside_its_subtree(self):
        self.populated()
        user = self.scoped(self.north)
        body = self.apply(user, self.draft(user, three_levels()))
        self.assertEqual(body["status"], "applied")
        self.assertEqual(self.level_names(), ["", "district", "village"])
        self.assertEqual(body["report"]["forms"][0]["loaded"], 1)
        # South (file and Proposal) would hang off the root; Dale off
        # acme-d. Both parents are outside North, so neither is created.
        self.assertEqual(
            self.unit_names(), ["Hill", "North", "acme", "acme-d"]
        )
        self.assertEqual(self.outside(body), [
            (3, "location", "skipped"), (4, "location", "skipped"),
        ])
        for issue in body["report"]["issues"]:
            for value in ("South", "Vale", "acme-d", "Dale"):
                self.assertNotIn(value, issue["reason"])

    def test_a_scoped_user_applying_a_super_admins_proposal_is_confined(
        self
    ):
        self.populated()
        pk = self.draft(self.admin, three_levels())
        user = self.scoped(self.north)
        body = self.apply(user, pk)
        self.assertEqual(body["status"], "applied")
        self.assertEqual(body["report"]["forms"][0]["loaded"], 1)
        self.assertEqual(
            self.unit_names(), ["Hill", "North", "acme", "acme-d"]
        )
        self.assertEqual(len(self.outside(body)), 2)

    def test_a_scoped_user_cannot_edit_in_new_levels(self):
        self.fresh()
        pk = self.draft(self.admin, three_levels())
        res = self.client.post(
            f"{URL}/{pk}/edits",
            {"op": "rename_form", "form": "sites", "name": "Wells"},
            content_type="application/json",
            **self.auth(self.scoped(self.root)), **self.host(),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Only a super admin", res.json()["message"])

    def test_the_review_lists_the_units_apply_will_add(self):
        self.populated()
        pk = self.draft(self.admin, three_levels())
        self.assertEqual(self.get(self.admin, pk)["units"], {
            "new": [["North", "Hill"], ["South"], ["South", "Vale"],
                    ["acme-d", "Dale"]],
            "outside": [],
        })
        # A scoped viewer sees what Apply would add for them, and what
        # it would leave out.
        self.assertEqual(self.get(self.scoped(self.north), pk)["units"], {
            "new": [["North", "Hill"]],
            "outside": [["South"], ["South", "Vale"], ["acme-d", "Dale"]],
        })
        self.assertNotIn("Hill", json.dumps(
            DataOnboarding.objects.get(pk=pk).proposal
        ))
