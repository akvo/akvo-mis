"""Scheduled tenant housekeeping.

Phase 1 of sign-up claims a subdomain -- `POST /api/v1/register`
creates a `Tenant` and an inactive superadmin, specifically so that
nobody can take the name during the email round-trip. Nothing ever
gave the claim back. This is what gives it back.

A module of its own rather than a function in views.py because
django-q schedules a task by dotted path, and because nothing here is
a request: the callers are the scheduler and the management command
that exists so a human can see what the scheduler would do.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, ProtectedError
from django.utils import timezone

from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_users.serializers import tenant_is_configured

logger = logging.getLogger(__name__)


def uninitiated_tenants():
    """Workspaces past the window that never finished configuring.

    `tenant_is_configured` is the authority on "finished", and it is
    reused rather than re-expressed in SQL: it is already shared with
    the configuration gate and the bulk-upload gate, and a second
    spelling of the predicate inside a destructive job is exactly
    where the two would drift apart.

    The `exclude` is index-friendly narrowing, not a second predicate.
    It drops every workspace that already has a root unit -- the cheap
    half of the question -- so the job does not walk every historical
    tenant row only to discard it in Python.

    This has to be a correlated `Exists` subquery rather than
    `.exclude(administrations__parent__isnull=True)`: that spelling
    joins through a LEFT OUTER JOIN, and for a tenant with no
    administrations at all the join still produces one row with every
    `administrations` column NULL -- including `parent_id` -- so
    `parent__isnull=True` reads as "has a root" when it actually means
    "has nothing". It would silently exclude every never-configured
    tenant, which is the one case this job exists to catch. `Exists`
    runs its own correlated subquery against `Administration` instead
    of joining, so a tenant with zero rows there has nothing to match.
    """
    cutoff = timezone.now() - timedelta(
        hours=settings.TENANT_PURGE_AFTER_HOURS
    )
    has_root = Administration.objects.filter(
        tenant=OuterRef("pk"), parent__isnull=True
    )
    candidates = Tenant.objects.filter(
        created_at__lt=cutoff,
        # An operator's DELETE is an explicit human act with its own
        # meaning. Finishing it off automatically would quietly
        # change what that button does.
        deleted_at=None,
    ).exclude(Exists(has_root)).order_by("pk")
    return [
        tenant
        for tenant in candidates
        if not tenant_is_configured(tenant)
    ]


def _purge_one(tenant, dry_run):
    """Delete one workspace, or find out why we cannot.

    The database is the guard. Every FK to `Tenant` is PROTECT, so a
    workspace that still owns anything makes `tenant.delete()` raise
    before a row is touched, and `ProtectedError.protected_objects`
    names what held it.

    No pre-flight check of what it owns: `Forms` and `Dashboard` are
    `SoftDeletes` models, so their default manager hides precisely the
    rows that still hold the FK. Leaning on PROTECT also closes the
    race with `/register/configure` for free.

    The users go first, which is only safe because of the
    transaction: hard-deleting a user cascades to anything they
    created, and if the tenant then turns out to be protected the
    rollback takes those cascades with it.
    """
    with transaction.atomic():
        # objects_with_deleted, not `tenant.users`: SystemUser's
        # default manager hides soft-deleted rows, and a soft-deleted
        # user still holds the PROTECT FK that blocks the tenant.
        # hard=True because the plain delete() is a soft delete, which
        # would leave the FK in place and the job looping on this
        # workspace forever.
        SystemUser.objects_with_deleted.filter(tenant=tenant).delete(
            hard=True
        )
        tenant.delete()
        if dry_run:
            # The same code path as a real purge, rolled back at the
            # end. A separate read-only report would be a second
            # implementation of "would this work" -- and the only one
            # of the two that is never exercised in anger.
            transaction.set_rollback(True)


def purge_uninitiated_tenants(dry_run=False):
    """Purge every workspace that never finished signing up.

    Returns the subdomains it purged and the ones it skipped. One
    protected workspace costs one workspace, not the run: the next
    hourly pass retries it, so a row that was transient resolves
    itself.
    """
    candidates = uninitiated_tenants()
    logger.info(
        "Tenant purge: %s candidate(s) older than %sh%s",
        len(candidates),
        settings.TENANT_PURGE_AFTER_HOURS,
        " (dry run)" if dry_run else "",
    )
    purged = []
    skipped = []
    for tenant in candidates:
        # Read after the delete throughout: Model.delete() nulls only
        # the pk, so every other field is still there to log.
        try:
            _purge_one(tenant, dry_run)
        except ProtectedError as error:
            names = {type(o).__name__ for o in error.protected_objects}
            logger.warning(
                "Tenant purge: skipped '%s', still owns %s",
                tenant.subdomain,
                ", ".join(sorted(names)),
            )
            skipped.append(tenant.subdomain)
        else:
            logger.info(
                "Tenant purge: %s '%s' (registered %s)",
                "would purge" if dry_run else "purged",
                tenant.subdomain,
                tenant.created_at.isoformat(),
            )
            purged.append(tenant.subdomain)
    logger.info(
        "Tenant purge: %s purged, %s skipped",
        len(purged),
        len(skipped),
    )
    return {"purged": purged, "skipped": skipped, "dry_run": dry_run}
