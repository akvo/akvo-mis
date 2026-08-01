import os
from unittest.mock import patch

import pandas as pd
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.job import handle_administrations_bulk_upload
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant

UPLOAD_URL = "/api/v1/upload/bulk-administrations"


@override_settings(USE_TZ=False, TEST_ENV=True)
class BulkUploadJobTestCase(TestCase):
    """The upload is asynchronous, so acceptance is not success.

    Before this, the only record of an import was an emailed CSV that
    arrived minutes later; the API said 200 the moment the file was
    received and nothing ever contradicted it.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(subdomain="acme")
        self.levels = [
            Levels.objects.create(name=name, level=idx, tenant=self.tenant)
            for idx, name in enumerate(["Country", "Province"])
        ]
        self.root = Administration.objects.create(
            parent=None, level=self.levels[0], name="Kenya",
            tenant=self.tenant,
        )
        self.admin = SystemUser.objects.create_superuser(
            email="a@acme.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=self.tenant,
        )

    def _auth(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _write_file(self, filename, rows):
        columns = [
            col
            for lvl in self.levels
            for col in [f"{lvl.id}|{lvl.name}", f"{lvl.id}|{lvl.name} Code"]
        ]
        named = [{columns[0]: root, columns[2]: child} for root, child in rows]
        os.makedirs("./tmp", exist_ok=True)
        path = f"./tmp/{filename}"
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
        pd.DataFrame(named, columns=columns).to_excel(
            writer, sheet_name="data", index=False
        )
        writer.save()
        return path

    def _run_handler(self, filename, job):
        with patch("api.v1.v1_jobs.job.storage.download"), patch(
            "api.v1.v1_jobs.job.send_email"
        ), patch("api.v1.v1_jobs.job.generate_sqlite"):
            handle_administrations_bulk_upload(
                filename, self.admin.id, timezone.now(), job_id=job.id
            )
        job.refresh_from_db()
        return job

    def _pending_job(self):
        return Jobs.objects.create(
            type=JobTypes.seed_administration_data,
            user=self.admin,
            status=JobStatus.pending,
            info={"file": "upload.xlsx"},
        )

    def test_the_upload_records_a_pending_job(self):
        self._write_file("posted.xlsx", [(None, "Nairobi")])
        with open("./tmp/posted.xlsx", "rb") as upload:
            with patch(
                "api.v1.v1_jobs.views.async_task", return_value="task-1"
            ), patch("api.v1.v1_jobs.views.storage.upload"):
                res = self.client.post(
                    UPLOAD_URL, {"file": upload}, **self._auth()
                )
        self.assertEqual(res.status_code, 200)

        job = Jobs.objects.get(type=JobTypes.seed_administration_data)
        self.assertEqual(job.status, JobStatus.pending)
        self.assertEqual(job.user, self.admin)
        # The response already carried the task id, and the existing
        # status endpoint resolves a job by it — so that is the handle
        # the page polls with.
        self.assertEqual(res.json()["task_id"], "task-1")
        self.assertEqual(job.task_id, "task-1")

    def test_a_good_file_finishes_the_job(self):
        self._write_file("good.xlsx", [(None, "Nairobi")])
        job = self._run_handler("good.xlsx", self._pending_job())

        self.assertEqual(job.status, JobStatus.done)
        self.assertTrue(
            Administration.objects.filter(
                tenant=self.tenant, name="Nairobi"
            ).exists()
        )

    def test_a_rejected_file_fails_the_job_and_keeps_the_error_file(self):
        self._write_file("bad.xlsx", [("Wrongland", "Nairobi")])
        job = self._run_handler("bad.xlsx", self._pending_job())

        self.assertEqual(job.status, JobStatus.failed)
        # The error CSV is emailed too, but the path on the job is what
        # lets the page say more than "it failed".
        self.assertTrue(job.result)
        self.assertFalse(
            Administration.objects.filter(
                tenant=self.tenant, name="Nairobi"
            ).exists()
        )

    def test_a_missing_data_sheet_fails_the_job(self):
        # A separate terminal branch, and the one most likely to be
        # forgotten: it returns before the validator is ever consulted.
        os.makedirs("./tmp", exist_ok=True)
        writer = pd.ExcelWriter("./tmp/nosheet.xlsx", engine="xlsxwriter")
        pd.DataFrame({"a": [1]}).to_excel(
            writer, sheet_name="other", index=False
        )
        writer.save()

        job = self._run_handler("nosheet.xlsx", self._pending_job())
        self.assertEqual(job.status, JobStatus.failed)

    def test_the_status_endpoint_reports_the_job(self):
        job = self._pending_job()
        Jobs.objects.filter(pk=job.pk).update(task_id="task-9")
        res = self.client.get(
            "/api/v1/download/status/task-9", **self._auth()
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "pending")
