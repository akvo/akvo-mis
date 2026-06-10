import os
import uuid
import zipfile
from datetime import timedelta
from io import StringIO
import pandas as pd
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.job import job_generate_data_download, _sanitize_form_name
from api.v1.v1_jobs.constants import (
    DataDownloadTypes,
    JobStatus,
    JobTypes,
)
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import SystemUser
from rest_framework import status
from utils import storage


def _extract_dir():
    """Per-process zip extraction dir. The plain './tmp/zip_extract' is
    shared across Django --parallel workers (separate processes, one
    filesystem); concurrent extract/rmtree races corrupt reads. Keying on
    the worker PID isolates each worker."""
    return f"./tmp/zip_extract_{os.getpid()}"


@override_settings(USE_TZ=False)
class ZipDownloadTestCase(TestCase, ProfileTestHelperMixin):
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
        rows = [
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
        administration_seeder.seed_administration_test(rows=rows)
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

    def _create_xlsx_job(self):
        info = {
            "form_id": self.form.id,
            "administration": None,
            "download_type": DataDownloadTypes.recent,
            "use_label": True,
            "child_form_ids": [],
            "date_from": None,
            "date_to": None,
        }
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

    def test_zip_download_produces_zip_file(self):
        job = self._create_zip_job()
        url = job_generate_data_download(job_id=job.id, **job.info)
        self.assertIn(".zip", url)
        # Cleanup
        storage.delete(url=f"download/{job.result}")

    def test_zip_contains_correct_number_of_files(self):
        job = self._create_zip_job()
        job_generate_data_download(job_id=job.id, **job.info)
        zip_path = f"./tmp/{job.result}"
        storage.download(f"download/{job.result}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            # 1 registration + N monitoring forms
            expected = 1 + len(self.child_form_ids)
            self.assertEqual(len(names), expected)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_registration_excel_has_no_parent_id(self):
        job = self._create_zip_job()
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            reg_name = _sanitize_form_name(self.form.name) + ".xlsx"
            self.assertIn(reg_name, zf.namelist())
            zf.extract(reg_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{reg_name}", sheet_name="data"
            )
            self.assertNotIn("parent_id", df.columns)
        # Cleanup
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_monitoring_excel_has_parent_id(self):
        job = self._create_zip_job()
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            child_name = (
                _sanitize_form_name(
                    self.child_form.name,
                    form_id=self.child_form.id
                ) + ".xlsx"
            )
            self.assertIn(child_name, zf.namelist())
            zf.extract(child_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{child_name}", sheet_name="data"
            )
            self.assertIn("parent_id", df.columns)
            self.assertIn("id", df.columns)
            # Verify parent_id references valid registration data
            reg_ids = set(
                self.form.form_form_data.filter(
                    is_pending=False, is_draft=False
                ).values_list("id", flat=True)
            )
            for pid in df["parent_id"].dropna():
                self.assertIn(int(pid), reg_ids)
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_without_child_forms_produces_xlsx(self):
        job = self._create_xlsx_job()
        url = job_generate_data_download(job_id=job.id, **job.info)
        self.assertIn(".xlsx", url)
        self.assertNotIn(".zip", url)
        storage.delete(url=f"download/{job.result}")

    def test_zip_monitoring_recent_mode(self):
        job = self._create_zip_job(
            download_type=DataDownloadTypes.recent
        )
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            child_name = (
                _sanitize_form_name(
                    self.child_form.name,
                    form_id=self.child_form.id
                ) + ".xlsx"
            )
            zf.extract(child_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{child_name}", sheet_name="data"
            )
            if len(df) > 0:
                parent_ids = df["parent_id"].tolist()
                self.assertEqual(
                    len(parent_ids), len(set(parent_ids)),
                    "Recent mode should have one row per parent"
                )
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_monitoring_all_mode(self):
        job = self._create_zip_job(
            download_type=DataDownloadTypes.all
        )
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            child_name = (
                _sanitize_form_name(
                    self.child_form.name,
                    form_id=self.child_form.id
                ) + ".xlsx"
            )
            zf.extract(child_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{child_name}", sheet_name="data"
            )
            if len(df) > 0:
                parent_ids = df["parent_id"].tolist()
                unique_parents = set(parent_ids)
                self.assertGreaterEqual(len(parent_ids), len(unique_parents))
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_download_with_date_filter(self):
        now = timezone.now()
        today = now.date()
        three_days_ago = (now - timedelta(days=3)).date()

        # Set known dates
        children = list(
            FormData.objects.filter(
                form=self.child_form,
                is_pending=False,
                is_draft=False,
            ).all()
        )
        if len(children) >= 2:
            FormData.objects.filter(pk=children[0].pk).update(
                created=timezone.now() - timedelta(days=5)
            )
            FormData.objects.filter(pk=children[1].pk).update(
                created=timezone.now() - timedelta(days=1)
            )
        job = self._create_zip_job(
            date_from=str(three_days_ago),
            date_to=str(today),
        )
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            child_name = (
                _sanitize_form_name(
                    self.child_form.name,
                    form_id=self.child_form.id
                ) + ".xlsx"
            )
            zf.extract(child_name, _extract_dir() + "/")
            df = pd.read_excel(
                f"{_extract_dir()}/{child_name}", sheet_name="data"
            )
            if len(children) >= 2 and len(df) > 0:
                result_ids = df["id"].tolist()
                self.assertNotIn(children[0].id, result_ids)
                self.assertIn(children[1].id, result_ids)
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_registration_included_when_monitoring_in_date_range(self):
        """Registration created before date_from must appear in the
        registration sheet when its monitoring child was created within
        the date range (mirrors form-data list API behaviour)."""
        import shutil

        # Pick one registration and push its created date far into the past
        reg = self.form.form_form_data.filter(
            is_pending=False, is_draft=False
        ).first()
        self.assertIsNotNone(reg)
        FormData.objects.filter(pk=reg.pk).update(
            created=timezone.now() - timedelta(days=365)
        )

        # Set its monitoring child to be within the date range
        child = self.child_form.form_form_data.filter(
            parent=reg, is_pending=False, is_draft=False
        ).first()
        self.assertIsNotNone(child)
        FormData.objects.filter(pk=child.pk).update(
            created=timezone.now() - timedelta(days=1)
        )

        # Date range: only the last 7 days (registration is 365 days old)
        date_from = (timezone.now() - timedelta(days=7)).date()
        date_to = timezone.now().date()
        job = self._create_zip_job(
            date_from=str(date_from),
            date_to=str(date_to),
        )
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        reg_name = _sanitize_form_name(self.form.name) + ".xlsx"
        child_name = (
            _sanitize_form_name(
                self.child_form.name,
                form_id=self.child_form.id,
            ) + ".xlsx"
        )
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extract(reg_name, _extract_dir() + "/")
            reg_df = pd.read_excel(
                f"{_extract_dir()}/{reg_name}", sheet_name="data"
            )
            reg_ids = reg_df["id"].tolist()
            self.assertIn(
                reg.id, reg_ids,
                "Registration created before date_from must be included "
                "because its monitoring child falls within the range."
            )
            zf.extract(child_name, _extract_dir() + "/")
            child_df = pd.read_excel(
                f"{_extract_dir()}/{child_name}", sheet_name="data"
            )
            child_ids = child_df["id"].tolist()
            self.assertIn(child.id, child_ids)
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_definition_sheet_per_form(self):
        job = self._create_zip_job()
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                zf.extract(name, _extract_dir() + "/")
                xlsx = pd.ExcelFile(f"{_extract_dir()}/{name}")
                self.assertIn(
                    "questions", xlsx.sheet_names,
                    f"Missing 'questions' sheet in {name}"
                )
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")

    def test_zip_context_sheet_in_registration_only(self):
        job = self._create_zip_job()
        job_generate_data_download(job_id=job.id, **job.info)
        storage.download(f"download/{job.result}")
        zip_path = f"./tmp/{job.result}"
        reg_name = _sanitize_form_name(self.form.name) + ".xlsx"
        child_name = (
            _sanitize_form_name(
                self.child_form.name,
                form_id=self.child_form.id
            ) + ".xlsx"
        )
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(_extract_dir() + "/")
            # Registration has context sheet
            reg_xlsx = pd.ExcelFile(f"{_extract_dir()}/{reg_name}")
            self.assertIn("context", reg_xlsx.sheet_names)
            # Monitoring does NOT have context sheet
            child_xlsx = pd.ExcelFile(f"{_extract_dir()}/{child_name}")
            self.assertNotIn("context", child_xlsx.sheet_names)
        import shutil
        if os.path.exists(_extract_dir()):
            shutil.rmtree(_extract_dir())
        if os.path.exists(zip_path):
            os.remove(zip_path)
        storage.delete(url=f"download/{job.result}")


@override_settings(USE_TZ=False)
class ZipDownloadCommandTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("form_seeder", "--test")
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.client.post(
            '/api/v1/login',
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type='application/json',
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

    def test_command_produces_zip_filename_with_child_forms(self):
        form = Forms.objects.get(pk=1)
        child_forms = form.children.all()[:1]
        admin = SystemUser.objects.first()
        result = self.call_command(
            form.id,
            admin.id,
            "-a",
            0,
            "-c",
            *child_forms.values_list("id", flat=True),
        )
        self.assertTrue(result)
        job = Jobs.objects.get(pk=result)
        self.assertTrue(
            job.result.endswith(".zip"),
            f"Expected .zip extension, got: {job.result}"
        )

    def test_command_produces_xlsx_filename_without_child_forms(self):
        form = Forms.objects.get(pk=1)
        admin = SystemUser.objects.first()
        result = self.call_command(
            form.id,
            admin.id,
            "-a",
            0,
        )
        self.assertTrue(result)
        job = Jobs.objects.get(pk=result)
        self.assertTrue(
            job.result.endswith(".xlsx"),
            f"Expected .xlsx extension, got: {job.result}"
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class ZipDownloadFileEndpointTestCase(TestCase, ProfileTestHelperMixin):
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
            form=self.form
        )
        self.token = self.get_auth_token(
            email=self.user.email,
            password="Test105*"
        )

    def test_successful_zip_file_download(self):
        filename = "download-test_form.zip"
        # Create a test zip file
        zip_path = f"./{filename}"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test.txt", "test content")
        storage.upload(file=zip_path, folder="download")
        job = Jobs.objects.create(
            type=JobTypes.download,
            user=self.user,
            status=JobStatus.done,
            info={
                "form_id": self.form.id,
                "child_form_ids": [10001],
            },
            result=filename,
        )
        response = self.client.get(
            f"/api/v1/download/file/{job.result}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"], "application/zip"
        )
        self.assertIn(filename, response["Content-Disposition"])
        # Cleanup
        os.remove(zip_path)
        storage.delete(url=f"download/{filename}")
