from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from django.core.management import call_command
from django.test import TestCase, override_settings

from api.v1.v1_jobs.job import (
    validate_excel_result,
    seed_data_job_result,
)
from api.v1.v1_jobs.models import Jobs, JobTypes, JobStatus
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class TaskRetryIdempotencyTestCase(TestCase):
    """django-q re-delivers unacknowledged tasks, so a result hook can fire
    more than once for the same job. These tests pin the guard that keeps
    side effects (spawning seed_data jobs, sending emails) at most once --
    the defect that flooded prod with 368 emails from two uploads."""

    def setUp(self):
        call_command("form_seeder", "--test")
        self.user = SystemUser.objects.create(
            email="idem@akvo.org",
            first_name="Idem",
            last_name="Test",
            is_superuser=True,
        )
        self.form = Forms.objects.first()

    def test_validate_result_spawns_one_seed_job_on_redelivery(self):
        job = Jobs.objects.create(
            type=JobTypes.validate_data,
            status=JobStatus.on_progress,
            user=self.user,
            task_id="validate-task-1",
            info={
                "file": "x.xlsx",
                "form": self.form.id,
                "administration": 1,
                "is_update": False,
            },
        )
        task = SimpleNamespace(id="validate-task-1", result=True, success=True)
        with patch(
            "api.v1.v1_jobs.job.async_task", return_value="seed-task-1"
        ) as mock_async:
            validate_excel_result(task)  # first delivery
            validate_excel_result(task)  # django-q re-delivery
            validate_excel_result(task)  # and again

        self.assertEqual(
            Jobs.objects.filter(type=JobTypes.seed_data).count(), 1
        )
        self.assertEqual(mock_async.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.done)

    def test_validate_timeout_does_not_spawn_seed(self):
        # A timed-out / killed validate: django-q sets success=False and
        # leaves a truthy error string in result. The job must be marked
        # failed and must NOT spawn a seed_data job.
        job = Jobs.objects.create(
            type=JobTypes.validate_data,
            status=JobStatus.on_progress,
            user=self.user,
            task_id="validate-timeout",
            info={
                "file": "x.xlsx",
                "form": self.form.id,
                "administration": 1,
                "is_update": False,
            },
        )
        task = SimpleNamespace(
            id="validate-timeout",
            result="Traceback: worker timed out",
            success=False,
        )
        with patch(
            "api.v1.v1_jobs.job.async_task", return_value="seed-task"
        ) as mock_async:
            validate_excel_result(task)

        self.assertEqual(
            Jobs.objects.filter(type=JobTypes.seed_data).count(), 0
        )
        mock_async.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.failed)

    def test_seed_result_sends_one_email_on_redelivery(self):
        seed = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.on_progress,
            user=self.user,
            task_id="seed-task-1",
            info={"file": "x.xlsx", "form": self.form.id},
        )
        # result = number of records seeded (> 0)
        task = SimpleNamespace(id="seed-task-1", result=2, success=True)
        with patch("api.v1.v1_jobs.job.storage.download"), patch(
            "api.v1.v1_jobs.job.pd.read_excel",
            return_value=pd.DataFrame({"q1": [1, 2]}),
        ), patch("api.v1.v1_jobs.job.send_email") as mock_send:
            seed_data_job_result(task)  # first delivery
            seed_data_job_result(task)  # django-q re-delivery

        self.assertEqual(mock_send.call_count, 1)
        seed.refresh_from_db()
        self.assertEqual(seed.status, JobStatus.done)

    def test_seed_result_no_change_sends_no_email(self):
        # A no-change upload: seed_data_job returns 0. The "No Data Updates"
        # email was already sent inside seed_excel_data, so the hook must NOT
        # send a second "New Data Submission" email, and the job is done.
        seed = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.on_progress,
            user=self.user,
            task_id="seed-task-0",
            info={"file": "x.xlsx", "form": self.form.id},
        )
        task = SimpleNamespace(id="seed-task-0", result=0, success=True)
        with patch("api.v1.v1_jobs.job.send_email") as mock_send:
            seed_data_job_result(task)

        mock_send.assert_not_called()
        seed.refresh_from_db()
        self.assertEqual(seed.status, JobStatus.done)

    def test_seed_result_error_marks_failed_without_email(self):
        seed = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.on_progress,
            user=self.user,
            task_id="seed-task-err",
            info={"file": "x.xlsx", "form": self.form.id},
        )
        task = SimpleNamespace(id="seed-task-err", result=False, success=True)
        with patch("api.v1.v1_jobs.job.send_email") as mock_send:
            seed_data_job_result(task)

        mock_send.assert_not_called()
        seed.refresh_from_db()
        self.assertEqual(seed.status, JobStatus.failed)
