from django.core.management import BaseCommand

from api.v1.v1_profile.constants import (
    DataAccessTypes,
    FeatureAccessTypes,
    FeatureTypes
)
from api.v1.v1_profile.models import Levels


class Command(BaseCommand):
    help = "Seed default roles and permissions for the application"

    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test",
            nargs="?",
            const=False,
            default=False,
            type=bool
        )

    def handle(self, *args, **options):
        test = options.get("test")
        all_levels = Levels.objects.all()
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
                # Add form builder feature
                admin_role.role_role_feature_access.create(
                    type=FeatureTypes.form_builder,
                    access=FeatureAccessTypes.form_builder
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
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Roles created for {level.name} level."
                    )
                )
