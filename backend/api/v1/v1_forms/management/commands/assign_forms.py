from django.core.management import BaseCommand
from api.v1.v1_users.models import SystemUser
from api.v1.v1_forms.models import Forms
from utils.tenant_command import resolve_tenant


class Command(BaseCommand):
    help = "Assign every root form in a user's workspace to that user."

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
            self.stdout.write("User doesn't exist")
            exit()
        # Scoped to the account's own workspace rather than to --tenant:
        # the two agree when both are given, and deriving it means a
        # tenant-less invocation still cannot hand somebody another
        # workspace's forms.
        forms = Forms.objects.filter(
            parent__isnull=True, tenant=user.tenant
        ).all()
        for form in forms:
            user.user_form.create(
                form=form
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully assigned {len(forms)} forms "
                f"to user {user.email}."
            )
        )
