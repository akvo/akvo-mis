from django.db.models import Q


def accessible_administration_q(user, field="administration"):
    """Scope a FormData-like queryset to the administrations a user may read.

    A user's data scope is, per role in ``user.user_user_role``, that role's
    administration plus its whole descendant subtree (path-based). Superusers
    get an empty ``Q`` -- no administration restriction; tenant scoping is
    applied separately via ``for_user``. A non-superuser with no roles matches
    nothing.

    This is the server-side boundary. A client-supplied ``administration``
    filter must be AND-combined with this Q so that requesting an ancestor (or
    any out-of-scope administration) narrows within the caller's scope instead
    of replacing it -- otherwise any authenticated user can read another
    administration's data by passing its id.

    ``field`` is the lookup from the queried model to its Administration FK
    ("administration" for FormData).
    """
    # No user context (internal/background callers pass user=None) or a
    # superuser: no administration restriction. Tenant scoping is applied
    # separately via for_user, so this stays a pure administration filter.
    if user is None or getattr(user, "is_superuser", False):
        return Q()
    roles = getattr(user, "user_user_role", None)
    if roles is None:
        # e.g. AnonymousUser -- not a real account, so no data access.
        return Q(pk__in=[])
    scope = Q()
    has_role = False
    for user_role in roles.all():
        adm = user_role.administration
        if not adm:
            continue
        subtree = f"{adm.path or ''}{adm.id}."
        scope |= Q(**{f"{field}_id": adm.id}) | Q(
            **{f"{field}__path__startswith": subtree}
        )
        has_role = True
    if not has_role:
        # No role => no data access. An empty Q would mean "no filter", so
        # match nothing explicitly.
        return Q(pk__in=[])
    return scope
