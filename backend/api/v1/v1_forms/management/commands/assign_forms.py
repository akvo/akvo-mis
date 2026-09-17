from django.core.management import BaseCommand, CommandError
from api.v1.v1_users.models import SystemUser
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms
from utils.tenant_command import resolve_tenant


class Command(BaseCommand):
    help = (
        "Assign every published form in a user's workspace to that user, "
        "monitoring forms included."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="+", type=str)
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace the account belongs to. Email addresses repeat "
                "across workspaces, so omitting this on a multi-workspace "
                "install may resolve to somebody else's account."
            ),
        )

    def handle(self, *args, **options):
        email = options.get("email")
        tenant = resolve_tenant(options.get("tenant"))
        users = SystemUser.objects.filter(email=email[0])
        if tenant is not None:
            users = users.filter(tenant=tenant)
        user = users.first()
        if not user:
            raise CommandError("User doesn't exist")
        # Scoped to the account's own workspace rather than to --tenant:
        # the two agree when both are given, and deriving it means a
        # tenant-less invocation still cannot hand somebody another
        # workspace's forms.
        # Published forms, not root forms. `parent__isnull=True` left
        # every monitoring form unassigned, and UserSerializer.get_forms
        # returns `user_form.all()` verbatim -- no superuser case, no
        # derivation of children -- so the mobile assignment screen builds
        # its tree from exactly these rows. A registration form with no
        # assigned children offers nothing to attach to a device, which is
        # what made the seeded monitoring form unusable.
        #
        # This is also what the API already does for a superuser created
        # with no explicit form list (v1_users/serializers.py: "if forms is
        # empty and is_superuser is True then assign all published forms").
        # The two paths disagreed; the API's answer is the right one.
        forms = Forms.objects.filter(
            status=FormStatus.published
        ).for_user(user)
        assigned = 0
        for form in forms:
            _, created = user.user_form.get_or_create(form=form)
            assigned += 1 if created else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully assigned {assigned} forms "
                f"to user {user.email}."
            )
        )
