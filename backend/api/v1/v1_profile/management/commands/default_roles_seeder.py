from django.core.management import BaseCommand

from api.v1.v1_profile.constants import (
    DataAccessTypes,
    FeatureAccessTypes,
    FeatureTypes
)
from api.v1.v1_profile.models import Levels
from utils.tenant_command import resolve_tenant


class Command(BaseCommand):
    help = (
        "Seed default roles and permissions for one workspace's levels. "
        "Omit --tenant to seed the tenant-less space."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test",
            nargs="?",
            const=False,
            default=False,
            type=bool
        )
        # No short flag: -t is already --test on this command, as on
        # form_seeder. Two flags one keystroke apart is how a subdomain
        # ends up in --test.
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=("Workspace subdomain whose levels get roles. Omit to "
                  "seed the tenant-less space."),
        )

    def handle(self, *args, **options):
        test = options.get("test")
        # `Levels.objects` is a plain TenantManager -- it adds `for_user`,
        # not an implicit filter -- so .all() means every workspace. On the
        # CLI there is no request to narrow it, which is how one
        # `seeder.sh --tenant=<sub>` run created roles across four
        # unrelated workspaces. Optional, and omitting it means the
        # tenant-less space: that is what resolve_tenant documents, and
        # what administration_seeder --test writes, so the test suite
        # selects the same rows .all() used to.
        tenant = resolve_tenant(options.get("tenant"))
        workspace = tenant.subdomain if tenant else "the tenant-less space"
        all_levels = Levels.objects.filter(tenant=tenant)
        for level in all_levels:
            # Create Admin role
            admin_role, created = level.role_administration_level\
                .get_or_create(
                    name=f"{level.name} Admin",
                    defaults={
                        "description": (
                            "Administrator with full access to all forms"
                        )
                    }
                )
            if created or test:
                admin_role.role_role_access.create(
                    data_access=DataAccessTypes.read
                )
                admin_role.role_role_access.create(
                    data_access=DataAccessTypes.submit
                )
                admin_role.role_role_access.create(
                    data_access=DataAccessTypes.edit
                )
                admin_role.role_role_access.create(
                    data_access=DataAccessTypes.delete
                )

                # Add user access feature
                admin_role.role_role_feature_access.create(
                    type=FeatureTypes.user_access,
                    access=FeatureAccessTypes.invite_user
                )
                # Add form builder feature (granular access types)
                for fb_access in [
                    FeatureAccessTypes.form_view,
                    FeatureAccessTypes.form_create,
                    FeatureAccessTypes.form_edit,
                    FeatureAccessTypes.form_publish,
                    FeatureAccessTypes.form_delete,
                ]:
                    admin_role.role_role_feature_access.create(
                        type=FeatureTypes.form_builder,
                        access=fb_access,
                    )

            # Create Submitter role
            submitter_role, created = level.role_administration_level\
                .get_or_create(
                    name=f"{level.name} Submitter",
                    defaults={
                        "description": (
                            "Submitter with read and submit access"
                            "to all forms"
                        )
                    }
                )
            if created or test:
                submitter_role.role_role_access.create(
                    data_access=DataAccessTypes.read
                )
                submitter_role.role_role_access.create(
                    data_access=DataAccessTypes.submit
                )

            # Create Approver role
            approver_role, created = level.role_administration_level\
                .get_or_create(
                    name=f"{level.name} Approver",
                    defaults={
                        "description": (
                            "Approver with read and"
                            "approve access to all forms"
                        )
                    }
                )
            if created or test:
                approver_role.role_role_access.create(
                    data_access=DataAccessTypes.read
                )
                approver_role.role_role_access.create(
                    data_access=DataAccessTypes.approve
                )
            if not test:
                # Level names are unique per tenant, not per install, so an
                # unqualified "Roles created for National level." four times
                # over is exactly what hid the cross-workspace leak.
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Roles created for {level.name} level "
                        f"({workspace})."
                    )
                )
