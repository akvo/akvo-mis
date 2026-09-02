import random
import re
import uuid

from django.core.management import BaseCommand
from faker import Faker

from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_profile.models import (
    Levels,
    Administration,
    Role,
    UserRole,
)
from api.v1.v1_users.models import SystemUser, Organisation
from api.v1.v1_forms.models import Forms, UserForms
from utils.tenant_command import resolve_tenant

fake = Faker()

DEFAULT_PASSWORD = "Test#123"


def create_user(
    administration: Administration,
    is_superuser: bool = False,
    test: bool = False,
    is_approver: bool = False,
    tenant=None,
) -> SystemUser:
    """One fake user, owned by `tenant`.

    Every lookup below is scoped the same way. `tenant=None` filters on
    `tenant IS NULL`, which on a tenant-less install matches everything
    it used to match unscoped -- the same rule `for_user` applies.
    """
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = (
        "{}.{}@test.com").format(
        re.sub("[^A-Za-z0-9]+", "", first_name.lower()),
        str(uuid.uuid4())[:4]
    )
    # `...attribute=<int>` compared the related row's primary key, not its
    # type, so this matched only while the attribute sequence happened to
    # start at OrganisationTypes.member -- and returned nothing, leaving
    # every seeded user org-less, once it had moved on.
    organisation = Organisation.objects.filter(
        organisation_organisation_attribute__type=OrganisationTypes.member,
        tenant=tenant,
    ).order_by("?").first()
    user = SystemUser.objects.create(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone_number=fake.msisdn(),
        is_superuser=is_superuser,
        tenant=tenant,
    )
    if organisation:
        user.organisation = organisation
    if test:
        password = random.choice(["test", None])
        if password:
            user.set_password(password)
    if not test:
        user.set_password(DEFAULT_PASSWORD)
    user.save()

    role_name = "Approver" if is_approver else "Submitter"
    role = Role.objects.filter(
        administration_level=administration.level,
        tenant=tenant,
        name="{0} {1}".format(
            administration.level.name,
            role_name
        )
    ).order_by("?").first()

    if not is_superuser and role:
        UserRole.objects.create(
            user=user,
            administration=administration,
            role=role
        )

    forms = Forms.objects.filter(parent__isnull=True, tenant=tenant).all()
    for form in forms:
        UserForms.objects.get_or_create(
            user=user,
            form=form
        )
    return user


class Command(BaseCommand):
    help = "Generate fake users, optionally for one workspace."

    def add_arguments(self, parser):
        parser.add_argument(
            "-r",
            "--repeat",
            nargs="?",
            const=1,
            default=5,
            type=int
        )
        parser.add_argument(
            "-t",
            "--test",
            nargs="?",
            const=False,
            default=False,
            type=bool
        )
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace subdomain the users belong to. Omit to seed "
                "into the tenant-less space, which is how single-host "
                "installs and the test suite run."
            ),
        )

    def handle(self, *args, **options):
        repeat = options.get("repeat")
        test = options.get("test")
        tenant = resolve_tenant(options.get("tenant"))
        level = 0
        # Both counted within the workspace. Unscoped, the level total ran
        # across every workspace on the install and the root was picked at
        # random from whichever one the ordering happened to surface, so a
        # --tenant run could hang its users off another workspace's
        # hierarchy entirely.
        total_levels = Levels.objects.filter(tenant=tenant).count() - 1
        national_adm = Administration.objects.filter(
            parent__isnull=True, tenant=tenant
        ).order_by("?").first()
        parent_adm = national_adm
        for _ in range(repeat):
            if level > total_levels:
                level = 0
                parent_adm = national_adm
            if level > 0:
                administration = Administration.objects.filter(
                    level__level=level, tenant=tenant
                ).order_by("?").first()
                if not parent_adm.path:
                    parent_adm = administration

            if parent_adm.path:
                administration = Administration.objects.filter(
                    level__level=level,
                    path__startswith=parent_adm.path,
                    tenant=tenant,
                ).first()
            else:
                administration = national_adm
            level += 1
            is_superuser = level == 0
            is_approver = level < total_levels - 1
            create_user(
                administration=administration,
                is_superuser=is_superuser,
                is_approver=is_approver,
                test=test,
                tenant=tenant,
            )

        if not test:
            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully created {} users".format(repeat)
                )
            )
