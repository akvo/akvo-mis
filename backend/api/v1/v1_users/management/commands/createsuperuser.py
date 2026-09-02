"""createsuperuser, but the account can be given a workspace.

Django's own command has no idea workspaces exist, so `seeder.sh
--tenant=<sub>` threaded one through every step except this one and
handed back a `tenant=NULL` superadmin. That account cannot authenticate
at any workspace host -- `TenantAwareBackend.authenticate` filters on
`tenant=` and a NULL row never matches -- and on the base domain login is
refused outright, so with BASE_DOMAIN set it could sign in nowhere. Even
single-host it read `tenant IS NULL` through every scoped queryset while
the forms and administrations beside it were owned by a workspace.

This subclass adds `--tenant` and leaves the rest to Django. It only
takes effect because `api.v1.v1_users` precedes `django.contrib.auth` in
INSTALLED_APPS -- see the note there.
"""
from django.contrib.auth.management.commands import createsuperuser
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from api.v1.v1_users.models import SystemUser
from utils.tenant_command import resolve_tenant


class Command(createsuperuser.Command):
    help = "Create a superuser, optionally owned by one workspace."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace subdomain the superuser belongs to. Omit to "
                "create a tenant-less account -- how single-host installs "
                "and the test suite run. 'default' exists on any migrated "
                "database."
            ),
        )

    def handle(self, *args, **options):
        # Resolved before anything is created. An unknown subdomain is a
        # typo, and a superadmin stranded in the tenant-less space looks
        # like a successful run until the day it cannot log in.
        tenant = resolve_tenant(options.pop("tenant", None))
        if tenant is None:
            return super().handle(*args, **options)
        existing = set(
            SystemUser.objects_with_deleted.values_list("pk", flat=True)
        )
        try:
            # Atomic because the workspace can only be applied after
            # Django has written the row. Django's own uniqueness check
            # is workspace-blind, so `unique_email_per_tenant` can still
            # reject the stamp -- and an un-atomic failure would leave the
            # half-made account behind in the tenant-less space.
            with transaction.atomic():
                super().handle(*args, **options)
                # The command creates exactly one account and returns
                # nothing, so the new row is found by difference rather
                # than by email, which the interactive path never puts in
                # options.
                SystemUser.objects_with_deleted.exclude(
                    pk__in=existing
                ).update(tenant=tenant)
        except IntegrityError:
            raise CommandError(
                f"An account with that email already exists in workspace "
                f"'{tenant.subdomain}'. Emails are unique per workspace, "
                f"not per install, so this only surfaces here."
            )
