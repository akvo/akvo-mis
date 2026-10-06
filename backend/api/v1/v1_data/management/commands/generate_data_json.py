from django.core.management import BaseCommand

from api.v1.v1_data.tasks import reconcile_datapoint_files


class Command(BaseCommand):
    help = (
        "Rewrite missing or stale datapoint files and delete orphaned ones. "
        "Runs hourly on the worker; see APP-517."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--test",
            nargs="?",
            const=1,
            default=False,
            type=int
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Rewrite every file, not only the missing or stale ones.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be rewritten and deleted; change nothing.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete orphans even past the wrong-database guard.",
        )

    def handle(self, *args, **options):
        result = reconcile_datapoint_files(
            rewrite_all=options.get("all"),
            dry_run=options.get("dry_run"),
            force=options.get("force"),
        )
        if options.get("test"):
            return
        prefix = "Would have " if options.get("dry_run") else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}rewritten {len(result['rewritten'])}, "
                f"deleted {len(result['deleted'])} datapoint files. "
                f"Failed {len(result['failed'])}, "
                f"refused to delete {len(result['refused'])}."
            )
        )
