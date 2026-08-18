from django.core.management import BaseCommand
from utils.custom_generator import generate_sqlite
from api.v1.v1_profile.models import Administration, Entity, EntityData
from api.v1.v1_users.models import Organisation, Tenant

MODELS = [Administration, Organisation, Entity, EntityData]


class Command(BaseCommand):
    # Add test arguments
    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=False, default=False, type=bool
        )

    def handle(self, *args, **options):
        test = options.get("test", False)
        # The tenant-less pass stays: seeders and single-tenant installs
        # still read the root files. The per-tenant pass is what a device
        # actually downloads.
        for model in MODELS:
            file = generate_sqlite(model, test=test)
            if not test:
                self.log_generated(file, model)
        for tenant in Tenant.objects.all():
            for model in MODELS:
                file = generate_sqlite(model, tenant=tenant, test=test)
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
