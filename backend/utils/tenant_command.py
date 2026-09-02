"""Which tenant is this management command acting on?

The CLI counterpart to `utils.tenant_host.resolve_tenant_from_host` and
`v1_visualization.functions.resolve_request_tenant`: those two answer the
question for an HTTP request, this one answers it for a `--tenant`
argument. Three seeders had grown their own copy, which is how the same
typo produced three different error messages.

A command that writes tenant-owned rows should call this even when it
tolerates a tenant-less run — `required=False` still rejects a subdomain
that does not exist, because an unknown workspace is a typo rather than a
deliberate choice, and silently seeding into the tenant-less space is the
kind of "success" nobody notices until the data is invisible.
"""
from django.core.management.base import CommandError

from api.v1.v1_users.models import Tenant

# How many subdomains to name when the requested one is not found. Enough
# to spot a typo, few enough to stay readable on an install with many
# workspaces.
SUGGESTION_LIMIT = 10


def known_subdomains(limit=SUGGESTION_LIMIT):
    """Subdomains to offer when a lookup fails."""
    return list(
        Tenant.objects.order_by("subdomain").values_list(
            "subdomain", flat=True
        )[:limit]
    )


def resolve_tenant(subdomain, *, required=False):
    """The workspace named by a --tenant argument.

    Parameters
    ----------
    subdomain : str | None
        The raw argument value. Blank and None are treated alike, so a
        shell expanding an unset variable to "" behaves as omission
        rather than as a lookup for the empty subdomain.
    required : bool
        When True, omitting the argument is an error. When False, it
        means the tenant-less space — which is how single-host installs
        and the test suite run.

    Returns
    -------
    Tenant | None

    Raises
    ------
    CommandError
        If required and omitted, or if the subdomain does not exist.
    """
    subdomain = (subdomain or "").strip()
    if not subdomain:
        if required:
            raise CommandError(
                "--tenant is required. 'default' exists on any migrated "
                "database (v1_users/0004_backfill_default_tenant.py)."
            )
        return None

    tenant = Tenant.objects.filter(subdomain=subdomain).first()
    if tenant:
        return tenant

    known = ", ".join(known_subdomains()) or "none"
    raise CommandError(
        f"No workspace with subdomain '{subdomain}'. Known: {known}"
    )
