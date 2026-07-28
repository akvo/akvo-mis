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


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)
