import pandas as pd
import numpy as np
from django.core.management import BaseCommand
from utils.db_manager import reset_table_sequence
from utils.tenant_command import resolve_tenant
from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_users.models import Organisation, OrganisationAttribute

source_file = './source/organisation.csv'


class Command(BaseCommand):
    help = (
        "Seed the bundled organisation fixture, optionally into one "
        "workspace."
    )

    def add_arguments(self, parser):
        parser.add_argument("-c",
                            "--clean",
                            nargs="?",
                            const=1,
                            default=False,
                            type=int)
        parser.add_argument(
            "-vv", "--verbose", nargs="?", const=1, default=False, type=int
        )
        parser.add_argument(
            "-t", "--test", nargs="?", const=1, default=False, type=int
        )
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace subdomain the organisations belong to. Omit to "
                "seed into the tenant-less space, which is how single-host "
                "installs and the test suite run."
            ),
        )

    def handle(self, *args, **options):
        clean = options.get("clean")
        test = options.get("test")
        verbose = options.get("verbose")
        tenant = resolve_tenant(options.get("tenant"))
        if clean:
            # Scoped: a --clean on a multi-workspace install must not take
            # the other workspaces' organisations with it.
            organisations = Organisation.objects.all()
            if tenant is not None:
                organisations = organisations.filter(tenant=tenant)
            organisations.delete()
            self.stdout.write('-- Organisation Cleared')
        df = pd.read_csv(source_file)
        df = df.replace({np.nan: None})
        for org in df.to_dict("records"):
            name = org["name"]
            abbrv = org.get("abbrv")
            types = org.get("types").split(",")
            if abbrv:
                name += f" ({abbrv})"
            # Keyed on the fixture's own primary key in the tenant-less
            # space, where those ids are free. Once a workspace is named
            # they are not: a primary key belongs to one row, so the
            # second workspace would find the first one's organisations,
            # rename them, and create nothing of its own. Name is the
            # identity that repeats per workspace.
            if tenant is None:
                organisation = Organisation.objects.filter(
                    pk=org["id"]
                ).first()
            else:
                organisation = Organisation.objects.filter(
                    name=name, tenant=tenant
                ).first()
            if not organisation:
                organisation = Organisation(
                    id=org.get("id") if tenant is None else None,
                    name=name,
                    tenant=tenant,
                )
                if verbose:
                    print(f"ADDED: {name}")
            elif organisation.name != name:
                if verbose:
                    print(f"UPDATED: {organisation.name} -> {name}")
                organisation.name = name
            organisation.save()
            for tp in types:
                org_type = getattr(OrganisationTypes, tp.strip())
                if not OrganisationAttribute.objects.filter(
                        organisation=organisation, type=org_type).first():
                    attr = OrganisationAttribute(organisation=organisation,
                                                 type=org_type)
                    attr.save()
        reset_table_sequence('organisation')
        if not test:
            self.stdout.write("-- FINISH")
