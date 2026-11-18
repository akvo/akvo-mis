import json
import os
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings

from api.v1.v1_data_onboarding.tests.tests_data_onboarding_draft import (
    CSV,
    openai_client,
    proposal,
)
from api.v1.v1_forms.models import Forms
from utils.tenant_test_case import TenantIsolationTestCase

URL = "/api/v1/data-onboarding"


@override_settings(
    USE_TZ=False, BASE_DOMAIN="app.com", OPENAI_API_KEY="sk-test-mock-key"
)
class DataOnboardingEditTestCase(TenantIsolationTestCase):
    def setUp(self):
        super().setUp()
        self.store = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.store)

        def upload(file, folder=None, filename=None):
            shutil.copyfile(file, os.path.join(self.store, filename))

        def download(url):
            return os.path.join(self.store, url.split("/")[-1])

        for target, fake in (
            ("api.v1.v1_data_onboarding.views.storage.upload", upload),
            ("api.v1.v1_data_onboarding.tasks.download", download),
        ):
            p = patch(target, side_effect=fake)
            p.start()
            self.addCleanup(p.stop)
        p = patch(
            "api.v1.v1_data_onboarding.views.async_task",
            return_value="task-id",
        )
        self.async_task = p.start()
        self.addCleanup(p.stop)

    def host(self):
        return {"HTTP_HOST": f"{self.a['tenant'].subdomain}.app.com"}

    def upload(self):
        return self.client.post(
            URL,
            {"file": SimpleUploadedFile("sites.csv", CSV.encode())},
            **self.auth(self.a["user"]), **self.host(),
        )

    def proposed(self, p=None):
        """A Data Onboarding drafted with the given Proposal."""
        from api.v1.v1_data_onboarding.tasks import draft_proposal

        pk = self.upload().json()["id"]
        with patch("openai.OpenAI", return_value=openai_client(
            json.dumps(p or proposal())
        )):
            draft_proposal(pk)
        return pk

    def get(self, pk):
        return self.client.get(
            f"{URL}/{pk}", **self.auth(self.a["user"]), **self.host()
        ).json()

    def edit(self, pk, **body):
        return self.client.post(
            f"{URL}/{pk}/edits", body, content_type="application/json",
            **self.auth(self.a["user"]), **self.host(),
        )

    def revise(self, pk, instruction="Make site_name optional"):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f"{URL}/{pk}/revise", {"instruction": instruction},
                content_type="application/json",
                **self.auth(self.a["user"]), **self.host(),
            )

    def run_revision(self, pk, content):
        from api.v1.v1_data_onboarding.tasks import revise_proposal

        client = openai_client(content)
        args = self.async_task.call_args
        self.assertEqual(
            args.args[0], "api.v1.v1_data_onboarding.tasks.revise_proposal"
        )
        with patch("openai.OpenAI", return_value=client):
            revise_proposal(*args.args[1:])
        return client

    def test_rename_a_form(self):
        pk = self.proposed()
        res = self.edit(pk, op="rename_form", form="sites", name="Wells")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["proposal"]["forms"][0]["name"], "Wells")
        self.assertEqual(self.get(pk)["proposal"]["forms"][0]["name"], "Wells")

    def test_a_blank_name_is_refused(self):
        pk = self.proposed()
        res = self.edit(pk, op="rename_form", form="sites", name="  ")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            self.get(pk)["proposal"]["forms"][0]["name"], "Water sites"
        )

    def test_an_unknown_op_or_form_is_refused(self):
        pk = self.proposed()
        self.assertEqual(self.edit(pk, op="nope").status_code, 400)
        self.assertEqual(
            self.edit(pk, op="rename_form", form="x", name="Y").status_code,
            400,
        )

    def test_a_name_clash_with_an_active_form_blocks_it(self):
        Forms.objects.create(name="water SITES ", tenant=self.a["tenant"])
        pk = self.proposed()
        blocked = self.get(pk)["blocked"]
        self.assertEqual([b["form"] for b in blocked], ["sites"])
        self.assertEqual(
            [c["kind"] for c in blocked[0]["causes"]], ["name_clash"]
        )

        res = self.edit(pk, op="rename_form", form="sites", name="Wells")
        self.assertEqual(res.json()["blocked"], [])

    def test_archived_forms_and_other_tenants_do_not_clash(self):
        Forms.objects.create(
            name="Water sites", tenant=self.a["tenant"]
        ).soft_delete()
        Forms.objects.create(name="Water sites", tenant=self.b["tenant"])
        pk = self.proposed()
        self.assertEqual(self.get(pk)["blocked"], [])

    def test_archiving_the_old_form_clears_the_clash_on_the_next_check(self):
        old = Forms.objects.create(
            name="Water sites", tenant=self.a["tenant"]
        )
        pk = self.proposed()
        self.assertEqual(len(self.get(pk)["blocked"]), 1)
        old.soft_delete()
        # Any edit re-runs the checks.
        res = self.edit(pk, op="rename_form", form="sites", name="Water sites")
        self.assertEqual(res.json()["blocked"], [])

    def test_drop_a_column_and_keep_it_again(self):
        pk = self.proposed()
        res = self.edit(pk, op="drop_column", form="sites",
                        column="water_source")
        self.assertEqual(res.status_code, 200)
        p = res.json()["proposal"]
        questions = [q["name"] for q in p["forms"][0]["question_group"][0][
            "question"]]
        self.assertEqual(questions, ["location", "site_name"])
        spec = p["data"][0]
        self.assertEqual(spec["columns"], [
            {"question": "site_name", "column": "site_name"},
        ])
        self.assertEqual(spec["value_maps"], [])
        self.assertEqual(
            [c["column"] for c in spec["unmapped_columns"]], ["water_source"]
        )

        res = self.edit(pk, op="keep_column", form="sites",
                        column="water_source")
        self.assertEqual(res.status_code, 200)
        p = res.json()["proposal"]
        kept = p["forms"][0]["question_group"][0]["question"][-1]
        self.assertEqual(
            (kept["name"], kept["label"], kept["type"], kept["required"]),
            ("water_source", "water_source", "input", False),
        )
        self.assertIn(
            {"question": "water_source", "column": "water_source"},
            p["data"][0]["columns"],
        )
        self.assertEqual(p["data"][0]["unmapped_columns"], [])
        self.assertEqual(self.get(pk)["proposal"], p)

    def test_only_loaded_or_left_out_columns_can_be_dropped_or_kept(self):
        pk = self.proposed()
        for op, column in (
            ("drop_column", "site_id"),  # a key column, not a question
            ("keep_column", "site_name"),  # already loaded
            ("drop_column", "nope"),
        ):
            res = self.edit(pk, op=op, form="sites", column=column)
            self.assertEqual(res.status_code, 400, (op, column))
        self.assertEqual(self.get(pk)["proposal"], proposal())

    def revised(self):
        p = proposal()
        p["forms"][0]["question_group"][0]["question"][1]["required"] = False
        return p

    def test_a_revision_redrafts_from_the_proposal_and_profile(self):
        pk = self.proposed()
        self.edit(pk, op="rename_form", form="sites", name="Wells")
        res = self.revise(pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "drafting")
        self.assertEqual(
            res.json()["proposal"]["forms"][0]["name"], "Wells"
        )
        # Edits wait while it revises.
        self.assertEqual(
            self.edit(pk, op="rename_form", form="sites", name="X")
            .status_code, 400,
        )

        client = self.run_revision(pk, json.dumps(self.revised()))

        body = self.get(pk)
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["proposal"], self.revised())
        self.assertIsNone(body["error"])
        sent = json.dumps(client.chat.completions.create.call_args.kwargs)
        self.assertIn("Make site_name optional", sent)
        self.assertIn("Wells", sent)  # the current Proposal
        self.assertIn("water_source", sent)  # the profile
        self.assertNotIn("Alpha well", sent)  # a cell value

    def test_a_revision_runs_the_checks_again(self):
        Forms.objects.create(name="Clinics", tenant=self.a["tenant"])
        pk = self.proposed()
        self.revise(pk)
        p = self.revised()
        p["forms"][0]["name"] = "Clinics"
        self.run_revision(pk, json.dumps(p))
        body = self.get(pk)
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(
            [c["kind"] for c in body["blocked"][0]["causes"]], ["name_clash"]
        )

    def test_a_failed_revision_keeps_the_previous_proposal(self):
        pk = self.proposed()
        self.revise(pk)
        self.run_revision(pk, json.dumps({"forms": []}))
        body = self.get(pk)
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["proposal"], proposal())
        self.assertIn("revision did not match", body["error"])

    def test_a_revision_needs_an_instruction(self):
        pk = self.proposed()
        self.assertEqual(self.revise(pk, "  ").status_code, 400)
        self.async_task.assert_called_once()  # the draft only

    @override_settings(DATA_ONBOARDING_DAILY_CAP=3)
    def test_daily_cap_on_drafts_and_revisions(self):
        from api.v1.v1_data_onboarding.models import DataOnboarding

        old = self.proposed()
        DataOnboarding.objects.filter(pk=old).update(
            created="2020-01-01T00:00:00"
        )
        pk = self.proposed()  # 1
        self.assertEqual(self.revise(pk).status_code, 200)  # 2
        self.run_revision(pk, json.dumps(self.revised()))
        self.assertEqual(self.upload().status_code, 201)  # 3

        res = self.revise(pk)
        self.assertEqual(res.status_code, 429)
        self.assertIn("3 drafts and revisions", res.json()["message"])
        self.assertEqual(self.get(pk)["status"], "proposed")
        self.assertEqual(self.upload().status_code, 429)

        # Edits are free, and the cap is per tenant.
        self.assertEqual(
            self.edit(pk, op="rename_form", form="sites", name="W")
            .status_code, 200,
        )
        res = self.client.post(
            URL, {"file": SimpleUploadedFile("s.csv", CSV.encode())},
            **self.auth(self.b["user"]),
            HTTP_HOST=f"{self.b['tenant'].subdomain}.app.com",
        )
        self.assertEqual(res.status_code, 201)
