import io
import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

import openpyxl
from django.core import mail
from django.test.utils import override_settings
from django.utils import timezone
from django_q.models import Schedule

from api.v1.v1_data_onboarding.constants import DataOnboardingStatus
from api.v1.v1_data_onboarding.models import DataOnboarding
from api.v1.v1_data_onboarding.tests.tests_data_onboarding_draft import (
    proposal,
)
from utils.tenant_test_case import TenantIsolationTestCase

URL = "/api/v1/data-onboarding"

REPORT = {
    "forms": [
        {"key": "sites", "name": "Water sites", "form": 1, "loaded": 41},
        {"key": "visits", "name": "Visits", "form": 2, "loaded": 7},
    ],
    "issues": [
        {"sheet": "csv", "row": 5, "question": "site_name",
         "kind": "skipped", "reason": "A required answer is missing."},
        {"sheet": "csv", "row": 9, "question": "water_source",
         "kind": "warning", "reason": "Not one of the options."},
    ],
}


@override_settings(
    USE_TZ=False, BASE_DOMAIN="app.com", OPENAI_API_KEY="sk-test-mock-key"
)
class DataOnboardingHistoryTestCase(TenantIsolationTestCase):
    def setUp(self):
        super().setUp()
        # Nothing here should reach OpenAI; fail loudly if it does.
        p = patch("openai.OpenAI", side_effect=AssertionError("OpenAI"))
        p.start()
        self.addCleanup(p.stop)

    def host(self, t="a"):
        return {"HTTP_HOST": f"{getattr(self, t)['tenant'].subdomain}.app.com"}

    def get(self, path, t="a"):
        return self.client.get(
            f"{URL}{path}", **self.auth(getattr(self, t)["user"]),
            **self.host(t),
        )

    def onboarding(self, t="a", **fields):
        return DataOnboarding.objects.create(
            tenant=getattr(self, t)["tenant"],
            created_by=getattr(self, t)["user"],
            file_name=fields.pop("file_name", "sites.csv"),
            **fields,
        )

    def test_lists_the_tenants_data_onboardings_newest_first(self):
        old = self.onboarding(
            file_name="old.csv", status=DataOnboardingStatus.applied,
            report=REPORT,
        )
        new = self.onboarding(file_name="new.xlsx")
        self.onboarding(t="b", file_name="beta.csv")

        res = self.get("")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual([r["id"] for r in body], [new.id, old.id])
        self.assertEqual(body[1]["status"], "applied")
        self.assertEqual(body[1]["file_name"], "old.csv")
        self.assertEqual(body[1]["created_by"], "A A")
        self.assertTrue(body[1]["created"])
        self.assertTrue(body[1]["updated"])
        # The list is a history, not a copy of each Proposal.
        self.assertNotIn("proposal", body[1])

        self.assertEqual(
            [r["file_name"] for r in self.get("", t="b").json()],
            ["beta.csv"],
        )

    def test_downloads_the_report_as_a_spreadsheet(self):
        pk = self.onboarding(
            status=DataOnboardingStatus.applied, report=REPORT
        ).id
        res = self.get(f"/{pk}/report")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment;", res["Content-Disposition"])
        self.assertIn(".xlsx", res["Content-Disposition"])

        wb = openpyxl.load_workbook(io.BytesIO(res.content))
        rows = [list(r) for r in wb.active.iter_rows(values_only=True)]
        self.assertEqual(rows, [
            ["Form", "Records loaded", None, None, None],
            ["Water sites", 41, None, None, None],
            ["Visits", 7, None, None, None],
            [None, None, None, None, None],
            ["Sheet", "Row", "Question", "Outcome", "Reason"],
            ["csv", 5, "site_name", "Row skipped",
             "A required answer is missing."],
            ["csv", 9, "water_source", "Answer dropped",
             "Not one of the options."],
        ])

    def test_no_report_to_download_before_apply(self):
        pk = self.onboarding(status=DataOnboardingStatus.proposed).id
        self.assertEqual(self.get(f"/{pk}/report").status_code, 404)

    def test_another_tenant_cannot_download_the_report(self):
        pk = self.onboarding(
            status=DataOnboardingStatus.applied, report=REPORT
        ).id
        self.assertEqual(self.get(f"/{pk}/report", t="b").status_code, 404)

    def test_a_failed_apply_emails_the_creator_a_link(self):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding

        # The upload is gone from storage, so Apply cannot read it.
        pk = self.onboarding(
            status=DataOnboardingStatus.applying, proposal=proposal(),
            file="data_onboarding/missing.csv",
        ).id
        with self.assertLogs("api.v1.v1_data_onboarding.tasks", "ERROR"):
            apply_onboarding(pk)

        body = self.get(f"/{pk}").json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["admin@acme.org"])
        self.assertIn("failed", email.subject.lower())
        html = email.alternatives[0][0]
        self.assertIn(
            f"acme.app.com/control-center/data-onboarding/{pk}", html
        )

    def test_a_killed_apply_worker_also_emails_the_creator(self):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding_result

        pk = self.onboarding(
            status=DataOnboardingStatus.applying, proposal=proposal()
        ).id
        apply_onboarding_result(
            type("Task", (), {"success": False, "args": [pk]})()
        )
        self.assertEqual(self.get(f"/{pk}").json()["status"], "failed")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@acme.org"])


@override_settings(USE_TZ=False)
class DataOnboardingFileCleanupTestCase(TenantIsolationTestCase):
    def setUp(self):
        super().setUp()
        self.store = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.store)
        os.makedirs(os.path.join(self.store, "data_onboarding"))
        p = patch("utils.storage.STORAGE_PATH", self.store)
        p.start()
        self.addCleanup(p.stop)

    def onboarding(self, name, status, age_days):
        path = os.path.join(self.store, "data_onboarding", name)
        open(path, "w").close()
        record = DataOnboarding.objects.create(
            tenant=self.a["tenant"], created_by=self.a["user"],
            file=f"data_onboarding/{name}", file_name=name, status=status,
            proposal=proposal(), report=REPORT,
        )
        # created is auto_now_add: backdate with update(), not save().
        DataOnboarding.objects.filter(id=record.id).update(
            created=timezone.now() - timedelta(days=age_days)
        )
        return record.id, path

    def purge(self):
        from api.v1.v1_data_onboarding.tasks import purge_onboarding_files

        purge_onboarding_files()

    def test_runs_on_a_schedule(self):
        schedule = Schedule.objects.get(
            func="api.v1.v1_data_onboarding.tasks.purge_onboarding_files"
        )
        self.assertEqual(schedule.repeats, -1)

    def test_deletes_the_file_once_applied(self):
        pk, path = self.onboarding("a.csv", DataOnboardingStatus.applied, 0)
        self.purge()
        self.assertFalse(os.path.exists(path))
        record = DataOnboarding.objects.get(id=pk)
        self.assertIsNone(record.file)
        self.assertEqual(record.proposal, proposal())
        self.assertEqual(record.report, REPORT)

    def test_keeps_an_open_proposals_file_for_14_days(self):
        _, path = self.onboarding("p.csv", DataOnboardingStatus.proposed, 13)
        self.purge()
        self.assertTrue(os.path.exists(path))

    def test_deletes_an_abandoned_proposals_file_after_14_days(self):
        pk, path = self.onboarding(
            "p.csv", DataOnboardingStatus.proposed, 15
        )
        self.purge()
        self.assertFalse(os.path.exists(path))
        record = DataOnboarding.objects.get(id=pk)
        self.assertIsNone(record.file)
        self.assertEqual(record.proposal, proposal())

    def test_a_file_already_gone_is_cleared_without_error(self):
        pk, path = self.onboarding("g.csv", DataOnboardingStatus.applied, 0)
        os.remove(path)
        self.purge()
        self.assertIsNone(DataOnboarding.objects.get(id=pk).file)
