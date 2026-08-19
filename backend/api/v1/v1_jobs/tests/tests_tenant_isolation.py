import os

from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.constants import JobStatus, JobTypes, DataDownloadTypes
from api.v1.v1_jobs.models import Jobs
from utils import storage
from utils.tenant_test_case import TenantIsolationTestCase


def _write_result_file(filename):
    path = f"./{filename}"
    with open(path, "a") as f:
        f.write("This is a test file!")
    storage.upload(file=path, filename=filename, folder="download")


@override_settings(USE_TZ=False, TEST_ENV=True)
class JobsTenantIsolationTestCase(TenantIsolationTestCase):
    def setUp(self):
        self._result_files = []
        super().setUp()

    def tearDown(self):
        for filename in self._result_files:
            if os.path.exists(f"./{filename}"):
                os.remove(f"./{filename}")
            storage.delete(url=f"download/{filename}")

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        result_filename = f"{sub}-download.xlsx"
        _write_result_file(result_filename)
        self._result_files.append(result_filename)
        tenant["job"] = Jobs.objects.create(
            type=JobTypes.download,
            user=tenant["user"],
            status=JobStatus.done,
            task_id=f"{sub}-task-id",
            info={
                "form_id": tenant["form"].id,
                "download_type": DataDownloadTypes.all,
            },
            result=result_filename,
        )
        tenant["data"] = FormData.objects.create(
            name=f"{sub}-dp",
            form=tenant["form"],
            administration=tenant["child"],
            created_by=tenant["user"],
        )
        tenant["monitoring_form"] = Forms.objects.create(
            name=f"{sub}-monitoring",
            tenant=tenant["tenant"],
            status=FormStatus.published,
            parent=tenant["form"],
        )
        tenant["monitoring_data"] = FormData.objects.create(
            name=f"{sub}-mdp",
            form=tenant["monitoring_form"],
            administration=tenant["child"],
            created_by=tenant["user"],
            parent=tenant["data"],
        )
        return tenant

    def test_download_file_404_on_foreign_job(self):
        res = self.client.get(
            f"/api/v1/download/file/{self.b['job'].result}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_download_status_404_on_foreign_job(self):
        res = self.client.get(
            f"/api/v1/download/status/{self.b['job'].task_id}",
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)

    def test_download_generate_400_on_foreign_form(self):
        res = self.client.get(
            "/api/v1/download/generate",
            {"form_id": self.b["form"].id},
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)

    def test_download_generate_400_on_foreign_administration(self):
        res = self.client.get(
            "/api/v1/download/generate",
            {
                "form_id": self.a["form"].id,
                "administration_id": self.b["root"].id,
            },
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)

    def test_datapoint_report_400_on_foreign_form(self):
        res = self.client.get(
            "/api/v1/download/datapoint-report",
            {"form_id": self.b["form"].id},
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 400)

    def test_upload_excel_404_on_foreign_form(self):
        res = self.client.post(
            f"/api/v1/upload/excel/{self.b['form'].id}",
            {},
            **self.auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(
            Jobs.objects.filter(user=self.a["user"]).count(), 1
        )

    def test_download_data_worker_scoped_by_job_user(self):
        # Belt-and-suspenders: even if a foreign form id slipped past
        # request validation (or a future caller invokes the task
        # directly), the worker's own FormData query must not surface
        # another tenant's rows.
        from api.v1.v1_jobs.job import download_data

        items = download_data(
            form=self.b["form"],
            selection_ids=[self.b["data"].id],
            user=self.a["user"],
        )
        self.assertEqual(items, [])

    def test_download_monitoring_data_worker_scoped_by_job_user(self):
        from api.v1.v1_jobs.job import download_monitoring_data

        items = download_monitoring_data(
            parent_form=self.b["form"],
            child_form=self.b["monitoring_form"],
            selection_ids=[self.b["data"].id],
            user=self.a["user"],
        )
        self.assertEqual(items, [])

    def test_transform_form_data_for_report_scoped_by_job_user(self):
        from api.v1.v1_jobs.job import transform_form_data_for_report

        result = transform_form_data_for_report(
            form=self.b["form"],
            selection_ids=[self.b["data"].id],
            user=self.a["user"],
        )
        self.assertEqual(result, [])
