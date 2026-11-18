"""Run the Data Onboarding upload purge hourly.

A django-q Schedule, not a backend-cron entry, for the reason given in
v1_users 0012_schedule_tenant_purge.
"""
from django.db import migrations

NAME = "purge-data-onboarding-files"
FUNC = "api.v1.v1_data_onboarding.tasks.purge_onboarding_files"
HOURLY = "H"


def schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.get_or_create(
        name=NAME,
        defaults={"func": FUNC, "schedule_type": HOURLY, "repeats": -1},
    )


def unschedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("v1_data_onboarding", "0001_initial"),
        ("django_q", "0014_schedule_cluster"),
    ]

    operations = [
        migrations.RunPython(schedule, unschedule),
    ]
