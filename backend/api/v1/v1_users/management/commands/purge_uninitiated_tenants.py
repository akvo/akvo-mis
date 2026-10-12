"""Purge workspaces that never finished signing up.

The scheduler is the normal caller -- see the django-q Schedule row
created by v1_users migration 0012. This command exists so that a
human can see what the scheduler would do (--dry-run) or make it
happen now, without reaching into the worker.
"""
from django.core.management.base import BaseCommand

from api.v1.v1_users.tasks import purge_uninitiated_tenants


class Command(BaseCommand):
    help = (
        "Delete tenants that never completed /register/configure "
        "within TENANT_PURGE_AFTER_HOURS."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be purged without deleting it.",
        )

    def handle(self, *args, **options):
        result = purge_uninitiated_tenants(dry_run=options["dry_run"])
        purged, skipped = result["purged"], result["skipped"]
        verb = "Would purge" if result["dry_run"] else "Purged"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {len(purged)}: {', '.join(purged) or '-'}"
        ))
        # Skips are the half an operator has to act on: a workspace
        # that owns rows will never purge on its own.
        if skipped:
            self.stdout.write(self.style.WARNING(
                f"Skipped {len(skipped)}: {', '.join(skipped)}"
            ))
