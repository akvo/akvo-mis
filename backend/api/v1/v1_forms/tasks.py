import json

from django.core.management import call_command

from api.v1.v1_jobs.constants import JobStatus
from api.v1.v1_jobs.models import Jobs
from utils.storage import download
from api.v1.v1_forms.functions import (
    normalize_form_definition,
    validate_form_definition,
    import_form_definition,
)


def refresh_form_config():
    """Clear the Django cache after a form is published.

    Dispatched asynchronously after a form is published. Forms are no longer
    baked into config.min.js — the web frontend fetches them at runtime from
    GET /api/v1/forms/published (see doc/claude/
    remove-window-forms-runtime-fetch.md). Clearing the cache evicts the
    cached published-forms payload and the per-form webform-{id} entries so
    the next fetch returns the updated form list. generate_config is no
    longer needed on the publish path.
    """
    call_command("clear_cache")


def import_form_job(job_id):
    """Background task: parse, validate, and import a form definition file.

    Called via async_task("api.v1.v1_forms.tasks.import_form_job", job.id).
    The Jobs row (type=import_form) is created by the view before dispatch;
    this task reads Jobs.info for the filename and mode, performs the import,
    and updates the Jobs row to done or failed.
    """
    job = Jobs.objects.get(id=job_id)
    info = job.info or {}
    filename = info.get("file")
    mode = info.get("mode", "create_or_update")
    parent_id = info.get("parent_id")
    user = job.user

    try:
        file_path = download(f"upload/{filename}")
        with open(file_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception as exc:
        job.status = JobStatus.failed
        job.result = json.dumps([{
            "code": "file_read_error",
            "message": str(exc),
            "level": "error",
        }])
        job.save(update_fields=["status", "result"])
        return

    norm = normalize_form_definition(raw)
    issues = validate_form_definition(norm)
    errors = [i for i in issues if i.get("level") == "error"]
    if errors:
        job.status = JobStatus.failed
        job.result = json.dumps(errors)
        job.save(update_fields=["status", "result"])
        return

    try:
        form, action = import_form_definition(
            norm, user, mode=mode, parent_id=parent_id
        )
    except Exception as exc:
        job.status = JobStatus.failed
        job.result = json.dumps([{
            "code": "import_error",
            "message": str(exc),
            "level": "error",
        }])
        job.save(update_fields=["status", "result"])
        return

    warnings = [i for i in issues if i.get("level") == "warning"]
    job.status = JobStatus.done
    job.result = json.dumps({
        "form_id": form.id,
        "form_name": form.name,
        "action": action,
        "warnings": warnings,
    })
    job.save(update_fields=["status", "result"])


def import_form_job_result(task):
    """Hook called by Django-Q after import_form_job completes or raises.

    Marks the Jobs row as failed when an unhandled exception reaches here
    (i.e. the task itself crashed before setting status=failed).
    """
    if task.success:
        return

    try:
        job_id = task.args[0]
        job = Jobs.objects.get(id=job_id)
        if job.status not in (JobStatus.done, JobStatus.failed):
            job.status = JobStatus.failed
            job.result = json.dumps([{
                "code": "task_error",
                "message": str(task.result),
                "level": "error",
            }])
            job.save(update_fields=["status", "result"])
    except Exception:
        pass
