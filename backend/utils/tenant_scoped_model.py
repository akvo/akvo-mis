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
        return self.filter(**{self.model.TENANT_PATH: user.tenant})


class TenantQuerySet(TenantScopedQuerySetMixin, models.QuerySet):
    pass


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)
