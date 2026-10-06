from django.db import models
from .soft_deletes_model import SoftDeletesQuerySet, SoftDeletesManager
from .tenant_scoped_model import TenantScopedQuerySetMixin


class DraftQuerySet(TenantScopedQuerySetMixin, models.QuerySet):
    def only_draft(self):
        return self.filter(is_draft=True)

    def without_draft(self):
        return self.filter(is_draft=False)

    def published(self):
        return self.filter(is_draft=False)


class DraftSoftDeletesQuerySet(SoftDeletesQuerySet):
    def only_draft(self):
        return self.filter(is_draft=True)

    def without_draft(self):
        return self.filter(is_draft=False)

    def published(self):
        return self.filter(is_draft=False)


class DraftManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.only_draft = kwargs.pop("only_draft", False)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if self.only_draft:
            return DraftQuerySet(self.model).only_draft()
        return DraftQuerySet(self.model).without_draft()

    def published(self):
        return self.get_queryset().published()

    def draft(self):
        return DraftQuerySet(self.model).only_draft()

    def for_user(self, user):
        return self.get_queryset().for_user(user)


class DraftSoftDeletesManager(SoftDeletesManager):
    # Overridable so a model can add its own queryset methods, the way
    # FormData adds `downloadable()`. Every branch below builds from it.
    queryset_class = DraftSoftDeletesQuerySet

    def __init__(self, *args, **kwargs):
        self.only_draft = kwargs.pop("only_draft", False)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        queryset = self.queryset_class(self.model, using=self._db)
        if self.only_draft:
            # For draft data, we only care about non-deleted drafts
            # since drafts are always hard deleted
            return queryset.without_deleted().only_draft()
        if self.with_deleted:
            return queryset
        if self.only_deleted:
            return queryset.only_deleted()
        return queryset.without_deleted()

    def draft(self):
        return self.queryset_class(
            self.model, using=self._db
        ).without_deleted().only_draft()


class Draft(models.Model):
    is_draft = models.BooleanField(default=False)

    class Meta:
        abstract = True

    objects = DraftManager()
    objects_draft = DraftManager(only_draft=True)

    def publish(self) -> None:
        self.is_draft = False
        self.save(update_fields=["is_draft"])

    def mark_as_draft(self) -> None:
        self.is_draft = True
        self.save(update_fields=["is_draft"])
