"""Stamp when each datapoint's file was written, and reconcile them hourly.

The column starts NULL on every existing row, which the device listing reads
as "no file yet": rows stay hidden until the reconcile writes their file.
There is no data migration because a migration must not touch the
filesystem. The backfill is the reconcile itself, run at startup by
run-prod.sh and then by the schedule below. Hiding is safe: the stamp is part
of the listing cursor, so each row is listed again once its file exists.

Hourly through django-q rather than the cron container: job.sh stops the SQL
proxy sidecar, and the worker is already running with an ORM broker.
See doc/design/APP-517-datapoint-file-guarantee.md (D-4).
"""
from django.db import migrations, models

NAME = "reconcile-datapoint-files"
FUNC = "api.v1.v1_data.tasks.reconcile_datapoint_files"
# The literal, not `Schedule.HOURLY`: a migration must not import code that
# can change underneath it.
HOURLY = "H"


def schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    # get_or_create: a replay, or a row an operator added by hand, must not
    # schedule the reconcile twice.
    Schedule.objects.get_or_create(
        name=NAME,
        defaults={"func": FUNC, "schedule_type": HOURLY, "repeats": -1},
    )


def unschedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("v1_data", "0005_formdata_submission_key"),
        # The Schedule table must exist with every column the row relies on.
        ("django_q", "0014_schedule_cluster"),
    ]

    operations = [
        migrations.AddField(
            model_name="formdata",
            name="file_generated_at",
            field=models.DateTimeField(default=None, null=True),
        ),
        migrations.RunPython(schedule, unschedule),
    ]
