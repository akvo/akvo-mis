"""Create the first platform operator.

Operators are invited from the console, but the first one cannot be:
there is nobody to send the invitation to them. This command is the way
in on a fresh deployment, and the only way an operator is created
outside the console.
"""
from django.core.management.base import BaseCommand, CommandError

from api.v1.v1_users.models import SystemUser


class Command(BaseCommand):
    help = "Create a tenant-less platform operator."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, type=str)
        parser.add_argument("--password", required=True, type=str)
        parser.add_argument("--first-name", default="", type=str)
        parser.add_argument("--last-name", default="", type=str)

    def handle(self, *args, **options):
        email = options["email"]
        # Checked here rather than left to the database. The
        # unique_email_per_tenant constraint spans (email, tenant), and
        # Postgres treats every NULL tenant as distinct, so nothing
        # stops a second tenant-less row with this address -- and two
        # operators sharing an address is a login that silently picks
        # one of them.
        if SystemUser.objects_with_deleted.filter(
            email=email, tenant__isnull=True
        ).exists():
            raise CommandError(
                f"A tenant-less account already exists for {email}."
            )
        operator = SystemUser.objects.create(
            email=email,
            first_name=options["first_name"],
            last_name=options["last_name"],
            tenant=None,
            is_platform_admin=True,
        )
        operator.set_password(options["password"])
        operator.save()
        self.stdout.write(
            self.style.SUCCESS(f"Platform operator created: {email}")
        )
