from django.core.management import BaseCommand
from faker import Faker

from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_users.models import Organisation, OrganisationAttribute
from utils.tenant_command import resolve_tenant

fake = Faker()


class Command(BaseCommand):
    help = "Generate fake organisations, optionally for one workspace."

    def add_arguments(self, parser):
        parser.add_argument("-r",
                            "--repeat",
                            nargs="?",
                            const=1,
                            default=1,
                            type=int)
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace subdomain the organisations belong to. Omit to "
                "seed into the tenant-less space."
            ),
        )

    def handle(self, *args, **options):
        tenant = resolve_tenant(options.get("tenant"))
        for r in range(options.get("repeat")):
            # Tenant is part of the lookup, not just the defaults: the
            # same company name may legitimately exist in two workspaces,
            # and matching on name alone would hand the second one the
            # first one's row.
            organisation, _ = Organisation.objects.update_or_create(
                name=fake.company() if r != 0 else "Akvo",
                tenant=tenant,
            )
            org_types = [
                OrganisationTypes.member, OrganisationTypes.partnership
            ]
            for org_type in org_types:
                OrganisationAttribute.objects.update_or_create(
                    organisation=organisation,
                    type=org_type
                )
