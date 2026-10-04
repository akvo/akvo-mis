"""Run the uninitiated-tenant purge hourly.

Hourly rather than daily because a daily pass against a 48-hour
window would make the configured number a floor rather than the
limit: a workspace registered an hour after one run would survive for
up to 71 hours. The query is one indexed scan returning a handful of
rows, so the cheaper schedule buys nothing.

django-q rather than the `backend-cron` container because job.sh ends
by telling the SQL proxy sidecar to exit, so a second crontab entry at
another hour would run without a database -- a coupling invisible from
either file. The qcluster worker is already always-running with an ORM
broker: no new container, no new dependency, and the schedule is a row
an operator can read.
"""
from django.db import migrations

NAME = "purge-uninitiated-tenants"
FUNC = "api.v1.v1_users.tasks.purge_uninitiated_tenants"
# The literal rather than `Schedule.HOURLY`: a migration must not
# import application code that can change underneath it, the same
# reason 0009 reads os.environ rather than settings.
HOURLY = "H"


def schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    # get_or_create so that replaying this migration, or running it on
    # a database where an operator already added the row by hand, does
    # not schedule the purge twice.
    Schedule.objects.get_or_create(
        name=NAME,
        defaults={
            "func": FUNC,
            "schedule_type": HOURLY,
            # Forever. A fixed count would stop purging on a date
            # nobody wrote down.
            "repeats": -1,
        },
    )


def unschedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("v1_users", "0011_tenant_language"),
        # The Schedule table must exist, with every column the row
        # relies on. Read from `showmigrations django_q`, not guessed.
        ("django_q", "0014_schedule_cluster"),
    ]

    operations = [
        migrations.RunPython(schedule, unschedule),
    ]
