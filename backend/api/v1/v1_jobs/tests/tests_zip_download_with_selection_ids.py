import os
import shutil
import uuid
import zipfile
from io import StringIO

import pandas as pd
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.constants import (
    DataDownloadTypes,
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.job import job_generate_data_download, _sanitize_form_name
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import SystemUser
from utils import storage


ADMIN_ROWS = [
    {
        "code_0": "ID",
        "National_0": "Indonesia",
        "code_1": "ID-JK",
        "Province_1": "Jakarta",
        "code_2": "ID-JK-JKE",
        "District_2": "East Jakarta",
        "code_3": "ID-JK-JKE-KJ",
        "Subdistrict_3": "Kramat Jati",
        "code_4": "ID-JK-JKE-KJ-CW",
        "Village_4": "Cawang",
    },
    {
        "code_0": "ID",
        "National_0": "Indonesia",
        "code_1": "ID-JK",
        "Province_1": "Jakarta",
        "code_2": "ID-JK-JKW",
        "District_2": "West Jakarta",
        "code_3": "ID-JK-JKW-KJ",
        "Subdistrict_3": "Kebon Jeruk",
        "code_4": "ID-JK-JKW-KJ-KJ",
        "Village_4": "Kebon Jeruk",
    },
    {
        "code_0": "ID",
        "National_0": "Indonesia",
        "code_1": "ID-YO",
        "Province_1": "Yogyakarta",
        "code_2": "ID-YO-SL",
        "District_2": "Sleman",
        "code_3": "ID-YO-SL-ST",
        "Subdistrict_3": "Seturan",
        "code_4": "ID-YO-SL-ST-CB",
        "Village_4": "Cepit Baru",
    },
    {
        "code_0": "ID",
        "National_0": "Indonesia",
        "code_1": "ID-YO",
        "Province_1": "Yogyakarta",
        "code_2": "ID-YO-BT",
        "District_2": "Bantul",
        "code_3": "ID-YO-BT-BT",
        "Subdistrict_3": "Bantul",
        "code_4": "ID-YO-BT-BT-BT",
        "Village_4": "Bantul",
    },
]


def _extract_dir():
    """Per-process zip extraction dir. The plain './tmp/zip_extract' is
    shared across Django --parallel workers (separate processes, one
    filesystem); concurrent extract/rmtree races corrupt reads. Keying on
    the worker PID isolates each worker."""
    return f"./tmp/zip_extract_{os.getpid()}"


def _cleanup_zip(zip_path: str, job_result: str) -> None:
    """Remove local files and remote storage after a test."""
    if os.path.exists(_extract_dir()):
        shutil.rmtree(_extract_dir())
    if os.path.exists(zip_path):
        os.remove(zip_path)
    storage.delete(url=f"download/{job_result}")


@override_settings(USE_TZ=False)
class ZipDownloadWithSelectionIdsTestCase(TestCase, ProfileTestHelperMixin):
    """Tests for the selection_ids feature in download/generate."""

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        call_command("form_seeder", "--test")
        administration_seeder.seed_administration_test(rows=ADMIN_ROWS)
        call_command("default_roles_seeder", "--test", 1)
        self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.call_command("-r", 2, "--test", True)

        self.form = Forms.objects.get(pk=1)
        self.child_form = self.form.children.first()
        self.child_form_ids = list(
            self.form.children.values_list("id", flat=True)
        )
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

        # Collect all registration FormData ids
        self.all_reg_ids = list(
            FormData.objects.filter(
                form=self.form,
                is_pending=False,
                is_draft=False,
            )
            .order_by("id")
            .values_list("id", flat=True)
        )

    def _create_zip_job(self, **extra_info):
        info = {
            "form_id": self.form.id,
            "administration": None,
            "download_type": DataDownloadTypes.recent,
            "use_label": True,
            "child_form_ids": self.child_form_ids,
            "date_from": None,
            "date_to": None,
        }
        info.update(extra_info)
        job = Jobs.objects.create(
            type=JobTypes.download,
            user=self.user,
            status=JobStatus.on_progress,
            info=info,
            result="placeholder.zip",
        )
        job.result = f"download-test-{uuid.uuid4().hex}.zip"
        job.save()
        return job

    def _create_xlsx_job(self, **extra_info):
        info = {
            "form_id": self.form.id,
            "administration": None,
            "download_type": DataDownloadTypes.recent,
            "use_label": True,
            "child_form_ids": [],
            "date_from": None,
            "date_to": None,
        }
        info.update(extra_info)
        job = Jobs.objects.create(
            type=JobTypes.download,
            user=self.user,
            status=JobStatus.on_progress,
            info=info,
            result="placeholder.xlsx",
        )
        job.result = f"download-test-{uuid.uuid4().hex}.xlsx"
        job.save()
        return job

    def test_selection_ids_filters_registration_data(self):
        """Zip job with selection_ids produces registration Excel
        containing only the selected FormData rows."""
        self.assertGreaterEqual(
            len(self.all_reg_ids), 2,
            "Seeder must create at least 2 registration rows",
        )
        selected = [self.all_reg_ids[0]]

        job = self._create_zip_job(selection_ids=selected)
        job_generate_data_download(job_id=job.id, **job.info)

        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        reg_name = _sanitize_form_name(self.form.name) + ".xlsx"

        with zipfile.ZipFile(zip_path, "r") as zf:
            self.assertIn(reg_name, zf.namelist())
            zf.extract(reg_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{reg_name}", sheet_name="data"
            )
            self.assertEqual(
                len(df), len(selected),
                "Registration Excel should only contain selected rows",
            )
            self.assertIn("id", df.columns)
            result_ids = df["id"].tolist()
            self.assertEqual(result_ids, selected)

        _cleanup_zip(zip_path, job.result)

    def test_selection_ids_filters_monitoring_data(self):
        """Zip job with selection_ids and child_form_ids produces
        monitoring Excel containing only children whose parent_id
        is in the selection_ids."""
        self.assertGreaterEqual(
            len(self.all_reg_ids), 2,
            "Seeder must create at least 2 registration rows",
        )
        selected = [self.all_reg_ids[0]]

        job = self._create_zip_job(selection_ids=selected)
        job_generate_data_download(job_id=job.id, **job.info)

        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        child_name = (
            _sanitize_form_name(
                self.child_form.name,
                form_id=self.child_form.id
            ) + ".xlsx"
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            self.assertIn(child_name, zf.namelist())
            zf.extract(child_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{child_name}", sheet_name="data"
            )
            if len(df) > 0:
                self.assertIn("parent_id", df.columns)
                for pid in df["parent_id"].dropna():
                    self.assertIn(
                        int(pid), selected,
                        "Monitoring rows must belong to selected parents",
                    )

        _cleanup_zip(zip_path, job.result)

    def test_empty_selection_ids_uses_normal_behavior(self):
        """Zip job with selection_ids=[] should produce the same
        number of registration rows as a job without selection_ids."""
        # Job without selection_ids
        job_normal = self._create_zip_job()
        job_generate_data_download(
            job_id=job_normal.id, **job_normal.info
        )
        storage.download(f"download/{job_normal.result}")
        zip_normal = f"./tmp/{job_normal.result}"
        reg_name = _sanitize_form_name(self.form.name) + ".xlsx"

        with zipfile.ZipFile(zip_normal, "r") as zf:
            zf.extract(reg_name, _extract_dir() + "/")
            df_normal = pd.read_excel(
                f"{_extract_dir()}/{reg_name}", sheet_name="data"
            )
        normal_count = len(df_normal)
        _cleanup_zip(zip_normal, job_normal.result)

        # Job with empty selection_ids
        job_empty = self._create_zip_job(selection_ids=[])
        job_generate_data_download(
            job_id=job_empty.id, **job_empty.info
        )
        storage.download(f"download/{job_empty.result}")
        zip_empty = f"./tmp/{job_empty.result}"

        with zipfile.ZipFile(zip_empty, "r") as zf:
            zf.extract(reg_name, _extract_dir() + "/")
            df_empty = pd.read_excel(
                f"{_extract_dir()}/{reg_name}", sheet_name="data"
            )
        empty_count = len(df_empty)
        _cleanup_zip(zip_empty, job_empty.result)

        self.assertEqual(
            normal_count, empty_count,
            "Empty selection_ids should behave the same as no selection_ids",
        )

    def test_xlsx_with_selection_ids(self):
        """XLSX job (no child_form_ids) with selection_ids produces
        an .xlsx file containing only the selected rows."""
        self.assertGreaterEqual(
            len(self.all_reg_ids), 2,
            "Seeder must create at least 2 registration rows",
        )
        selected = [self.all_reg_ids[0]]

        job = self._create_xlsx_job(selection_ids=selected)
        url = job_generate_data_download(job_id=job.id, **job.info)

        self.assertIn(".xlsx", url)
        self.assertNotIn(".zip", url)

        storage.download(f"download/{job.result}")
        xlsx_path = f"./tmp/{job.result}"
        df = pd.read_excel(xlsx_path, sheet_name="data")

        self.assertEqual(
            len(df), len(selected),
            "XLSX should only contain selected rows",
        )
        self.assertIn("id", df.columns)
        result_ids = df["id"].tolist()
        self.assertEqual(result_ids, selected)

        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)
        storage.delete(url=f"download/{job.result}")


@override_settings(USE_TZ=False)
class ZipDownloadCommandWithSelectionIdsTestCase(
    TestCase, ProfileTestHelperMixin
):
    """Tests for the management command with -s (selection_ids) flag."""

    def setUp(self):
        call_command("form_seeder", "--test")
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "job_download",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_command_accepts_selection_ids_argument(self):
        """Management command with -s flag stores selection_ids
        in the job info dictionary."""
        form = Forms.objects.get(pk=1)
        admin = SystemUser.objects.first()

        fake_ids = [100, 200]
        result = self.call_command(
            form.id,
            admin.id,
            "-a", 0,
            "-s", *fake_ids,
        )
        self.assertTrue(result)
        job = Jobs.objects.get(pk=result)
        self.assertIn("selection_ids", job.info)
        self.assertEqual(job.info["selection_ids"], fake_ids)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ZipDownloadApiWithSelectionIdsTestCase(
    TestCase, ProfileTestHelperMixin
):
    """Tests for the download/generate API endpoint with selection_ids."""

    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)

        self.form = Forms.objects.get(pk=1)
        self.administration = Administration.objects.filter(
            level__level=1
        ).order_by("?").first()
        self.user = self.create_user(
            email="admin@akvo.org",
            password="Test105*",
            role_level=self.IS_ADMIN,
            administration=self.administration,
            form=self.form,
        )
        self.token = self.get_auth_token(
            email=self.user.email,
            password="Test105*",
        )
        self.url = "/api/v1/download/generate"

    def test_api_endpoint_accepts_selection_ids(self):
        """GET /api/v1/download/generate with selection_ids query
        params returns HTTP 200."""
        # Seed data so FormData objects exist for the serializer
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            "-r", 2,
            "--test", True,
            stdout=out,
            stderr=StringIO(),
        )

        reg_ids = list(
            FormData.objects.filter(
                form=self.form,
                is_pending=False,
                is_draft=False,
            ).values_list("id", flat=True)[:1]
        )
        self.assertGreaterEqual(len(reg_ids), 1)

        query = (
            f"{self.url}?form_id={self.form.id}"
            f"&selection_ids={reg_ids[0]}"
        )
        response = self.client.get(
            query,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
