from django.db import models


# =========================================================
# Tenant scoping
# =========================================================
# Every tenant-owned model declares TENANT_PATH — the ORM lookup from the
# model to its owning tenant. Direct-FK models use "tenant"; derived models
# use a join, e.g. "form__tenant". for_user() applies it uniformly.
#
# A tenant-less user (user.tenant is None) filters on tenant IS NULL, which
# matches tenant-less rows — the transitional state the test suite runs in.
# The production invariant is that every user has a tenant.


class TenantScopedQuerySetMixin:
    def for_user(self, user):
        # AnonymousUser has no tenant attribute at all. Treat it as another
        # tenant-less actor rather than letting it raise: on a real
        # deployment every row is tenant-owned, so an anonymous caller
        # matches nothing, which is the safe outcome for the handful of
        # endpoints reachable without a token.
        tenant = getattr(user, "tenant", None)
        return self.filter(**{self.model.TENANT_PATH: tenant})


class TenantQuerySet(TenantScopedQuerySetMixin, models.QuerySet):
    pass


# from_queryset copies for_user onto the manager, so plain-manager models
# get Model.objects.for_user(...) without hand-written delegation. The
# soft-deletes and draft managers cannot use this — their get_queryset
# carries with_deleted/only_draft state a generated manager would drop —
# so they delegate explicitly instead.
TenantManager = models.Manager.from_queryset(TenantQuerySet)


def acting_user(context):
    # Serializers here are called with either context={"user": ...} or the
    # DRF default context={"request": ...}. Support both so callers do not
    # have to be normalised first.
    user = context.get("user")
    if user is None:
        request = context.get("request")
        user = getattr(request, "user", None)
    return user


class TenantStampedSerializerMixin:
    # create() stamps the new row with the acting user's tenant. Tenant is
    # never read from the payload — only from the authenticated user — so a
    # caller cannot plant a row in someone else's tenant.
    def create(self, validated_data):
        user = acting_user(self.context)
        validated_data["tenant"] = getattr(user, "tenant", None)
        return super().create(validated_data)
