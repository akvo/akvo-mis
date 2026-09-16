from django.core.management import BaseCommand
from utils.custom_generator import generate_sqlite
from utils.tenant_command import resolve_tenant
from api.v1.v1_profile.models import Administration, Entity, EntityData
from api.v1.v1_users.models import Organisation, Tenant

MODELS = [Administration, Organisation, Entity, EntityData]


class Command(BaseCommand):
    help = (
        "Write the master-data SQLite files a device downloads. "
        "Pass --tenant to rebuild one workspace; omit it to rebuild "
        "every workspace plus the tenant-less files."
    )

    # Add test arguments
    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=False, default=False, type=bool
        )
        # No short flag: -t is already --test here, as on form_seeder and
        # default_roles_seeder.
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace subdomain to rebuild. Omit to rebuild every "
                "workspace and the tenant-less files."
            ),
        )

    def handle(self, *args, **options):
        test = options.get("test", False)
        tenant = resolve_tenant(options.get("tenant"))
        if tenant is not None:
            # A named workspace gets its own directory and nothing else.
            # ./seeder.sh --tenant=<sub> touched one workspace's rows, so
            # rewriting all eight other workspaces' files is work that
            # produces byte-identical output and buries the line the
            # operator is looking for.
            targets = [tenant]
        else:
            # The tenant-less pass stays: seeders and single-tenant
            # installs still read the root files. The per-tenant pass is
            # what a device actually downloads. Both together are the
            # boot-time rebuild run-prod.sh wants -- unlike roles, which
            # create rows, this only rewrites derived files, so "all of
            # them" is a legitimate default here.
            targets = [None] + list(Tenant.objects.all())
        for target in targets:
            for model in MODELS:
                file = generate_sqlite(model, tenant=target, test=test)
                if not test:
                    self.log_generated(file, model)

    def log_generated(self, file, model):
        message = (
            f"{file} Generated Successfully"
            if file
            else (
                f"Failed to generate {model._meta.db_table}, "
                "possibly empty data"
            )
        )
        print(message)
