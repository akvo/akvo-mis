from django.db import models

from api.v1.v1_data_onboarding.constants import DataOnboardingStatus
from api.v1.v1_users.models import SystemUser
from utils.tenant_model import tenant_fk
from utils.tenant_scoped_model import TenantManager


class DataOnboarding(models.Model):
    TENANT_PATH = "tenant"
    objects = TenantManager()
    tenant = tenant_fk("data_onboardings")
    status = models.IntegerField(
        choices=DataOnboardingStatus.FieldStr.items(),
        default=DataOnboardingStatus.drafting,
    )
    # Storage path of the upload, in a folder nginx does not serve.
    file = models.CharField(max_length=255, null=True, default=None)
    file_name = models.CharField(max_length=255)
    profile = models.JSONField(null=True, default=None)
    proposal = models.JSONField(null=True, default=None)
    report = models.JSONField(null=True, default=None)
    error = models.TextField(null=True, default=None)
    created_by = models.ForeignKey(
        to=SystemUser,
        on_delete=models.PROTECT,
        related_name="data_onboardings",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_onboarding"
