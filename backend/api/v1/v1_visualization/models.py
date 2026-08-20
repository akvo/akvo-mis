from django.db import models

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from api.v1.v1_visualization.constants import (
    DashboardStatus,
    WidgetTypes,
)
from utils.soft_deletes_model import SoftDeletes
from utils.tenant_model import tenant_fk
from utils.tenant_scoped_model import TenantManager


class ViewDataOptions(models.Model):
    id = models.BigIntegerField(primary_key=True)
    parent_data = models.ForeignKey(
        to=FormData,
        on_delete=models.DO_NOTHING,
        related_name="data_view_parent_data_options",
    )
    data = models.ForeignKey(
        to=FormData,
        on_delete=models.DO_NOTHING,
        related_name="data_view_data_options",
    )
    administration = models.ForeignKey(
        to=Administration,
        on_delete=models.PROTECT,
        related_name="administration_view_data_options",
    )
    form = models.ForeignKey(
        to=Forms,
        on_delete=models.DO_NOTHING,
        related_name="form_view_data_options",
    )
    options = models.JSONField(default=None, null=True)

    class Meta:
        managed = False
        db_table = "view_data_options"


# =========================================================
# Dashboard builder (VIZ-002)
# =========================================================
# A dashboard is a Dashboard row plus N DashboardWidget rows, not one
# JSON blob. Five widget fields are promoted out of the blob because
# they need referential integrity or need to be queried; everything
# type-specific stays in `config`.


class Dashboard(SoftDeletes):
    """A tenant-authored dashboard bound to one registration form."""

    # Definition root, like Forms: dashboards are owned outright, so the
    # tenant is a column rather than a join (MT-002).
    TENANT_PATH = "tenant"

    tenant = tenant_fk("dashboards")
    root_form = models.ForeignKey(
        to=Forms,
        on_delete=models.PROTECT,
        related_name="dashboards",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(null=True, default=None)
    status = models.IntegerField(
        choices=DashboardStatus.FieldStr.items(),
        default=DashboardStatus.draft,
    )
    # Snapshot of the widget rows, written by publish (VIZ-007). Viewers
    # read this; the builder edits the rows. Null while draft.
    published_config = models.JSONField(null=True, default=None)
    published_at = models.DateTimeField(null=True, default=None)
    default_filters = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True, default=None)
    created_by = models.ForeignKey(
        to=SystemUser,
        on_delete=models.SET_NULL,
        related_name="dashboards_created",
        null=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        # Scoped to live rows so a soft-deleted dashboard does not hold
        # its slug hostage — same reasoning as QuestionGroup's
        # unique_active_form_question_group.
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_tenant_dashboard_slug",
            )
        ]
        db_table = "dashboard"


class DashboardWidget(models.Model):
    """One visualisation on a dashboard."""

    # No tenant column of its own; ownership is derived from the parent.
    TENANT_PATH = "dashboard__tenant"
    objects = TenantManager()

    dashboard = models.ForeignKey(
        to=Dashboard,
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    order = models.IntegerField()
    type = models.IntegerField(choices=WidgetTypes.FieldStr.items())
    col_span = models.IntegerField(default=24)
    title = models.CharField(max_length=255, null=True, default=None)
    color = models.CharField(max_length=32, null=True, default=None)
    # root_form, or a monitoring form whose parent is root_form. The
    # family rule itself is enforced in the serializer (VIZ-005).
    form = models.ForeignKey(
        to=Forms,
        on_delete=models.PROTECT,
        related_name="dashboard_widgets",
        null=True,
        default=None,
    )
    # Null for section_title and for count-only KPIs. Questions
    # soft-delete, so PROTECT never fires on the normal delete path; the
    # FK exists to make "which dashboards use this question?" a plain
    # join for VIZ-007 and VIZ-009.
    question = models.ForeignKey(
        to=Questions,
        on_delete=models.PROTECT,
        related_name="dashboard_widgets",
        null=True,
        default=None,
    )
    config = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.dashboard.name} - {WidgetTypes.FieldStr[self.type]}"

    class Meta:
        ordering = ["dashboard", "order"]
        db_table = "dashboard_widget"
