from django.db import models

from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import (
    Administration,
    Role,
    UserRole,
    DataAccessTypes,
)
from api.v1.v1_users.models import SystemUser
from utils.tenant_scoped_model import TenantManager


class DataBatch(models.Model):
    # A batch belongs to the tenant that owns its form. Every endpoint here
    # takes a batch id straight from the URL, so without this the ids are
    # sequential and guessable across workspaces.
    TENANT_PATH = "form__tenant"
    objects = TenantManager()
    form = models.ForeignKey(
        to=Forms, on_delete=models.CASCADE, related_name="form_batch_data"
    )
    administration = models.ForeignKey(
        to=Administration,
        on_delete=models.PROTECT,
        related_name="administration_data_batch",
    )
    user = models.ForeignKey(
        to=SystemUser,
        on_delete=models.CASCADE,
        related_name="user_data_batch",
    )
    name = models.TextField()
    uuid = models.UUIDField(default=None, null=True)
    file = models.URLField(default=None, null=True)
    approved = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return self.name  # pragma: no cover

    # Get all the approvers for this batch
    def approvers(self):
        administrations = [self.administration]
        if self.administration.parent:
            # merge adm with ancestors
            ancestors = self.administration.ancestors.all()
            administrations = list(ancestors) + [self.administration]
        # Get all user roles for this administration which have approve access
        # Get form from data_batch_list
        data_batch = self.batch_data_list.first()
        form = data_batch.data.form
        # Build base queryset with common filters
        user_roles = UserRole.objects.filter(
            administration__in=administrations,
            role__role_role_access__data_access=DataAccessTypes.approve,
        ).exclude(
            user__password__exact=""
        ).select_related("user", "role")
        # Apply form access filter
        form_filter = [form]
        if form.parent:
            form_filter.append(form.parent)

        user_roles = user_roles.filter(
            user__user_form__form__in=form_filter
        )

        # Show user and their administration order by administration level
        user_roles = user_roles.order_by(
            "user__email", "administration__level__level"
        )
        user_roles = [
            {
                "user": user_role.user,
                "role": user_role.role,
                "administration": user_role.administration,
            }
            for user_role in user_roles
        ]
        return user_roles

    class Meta:
        db_table = "batch"


class DataBatchComments(models.Model):
    batch = models.ForeignKey(
        to=DataBatch,
        on_delete=models.CASCADE,
        related_name="batch_batch_comment",
    )
    user = models.ForeignKey(
        to=SystemUser,
        on_delete=models.CASCADE,
        related_name="user_batch_comment",
    )
    comment = models.TextField()
    file_path = models.CharField(
        max_length=255,
        null=True,
        default=None,
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.comment  # pragma: no cover

    class Meta:
        db_table = "batch_comment"


class DataBatchAttachments(models.Model):
    batch = models.ForeignKey(
        to=DataBatch,
        on_delete=models.CASCADE,
        related_name="batch_batch_attachment",
    )
    name = models.CharField(max_length=255, default=None, null=True)
    file_path = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name  # pragma: no cover

    class Meta:
        db_table = "batch_attachment"


# Batch Form with list of FormData
class DataBatchList(models.Model):
    batch = models.ForeignKey(
        to=DataBatch,
        on_delete=models.CASCADE,
        related_name="batch_data_list",
    )
    data = models.OneToOneField(
        to=FormData,
        on_delete=models.CASCADE,
        related_name="data_batch_list",
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.batch.name} - {self.data.name}"  # pragma: no cover

    class Meta:
        db_table = "batch_data"


class DataApproval(models.Model):
    batch = models.ForeignKey(
        to=DataBatch,
        on_delete=models.CASCADE,
        related_name="batch_approval",
    )
    administration = models.ForeignKey(
        to=Administration,
        on_delete=models.PROTECT,
        related_name="administration_data_approval",
    )
    role = models.ForeignKey(
        to=Role,
        on_delete=models.PROTECT,
        related_name="role_data_approval",
    )
    user = models.ForeignKey(
        to=SystemUser,
        on_delete=models.CASCADE,
        related_name="data_approval_user",
    )
    status = models.IntegerField(
        choices=DataApprovalStatus.FieldStr.items(),
        default=DataApprovalStatus.pending,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return self.user.email  # pragma: no cover

    class Meta:
        db_table = "data_approval"
