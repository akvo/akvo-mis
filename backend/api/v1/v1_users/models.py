import hashlib
import secrets

from api.v1.v1_profile.constants import OrganisationTypes
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core import signing
from django.db import models
from django.utils import timezone
from utils.soft_deletes_model import SoftDeletes
from utils.tenant_scoped_model import TenantManager
from utils.tenant_model import tenant_fk

# Create your models here.
from utils.custom_manager import UserManager


class Organisation(models.Model):
    TENANT_PATH = "tenant"
    objects = TenantManager()
    name = models.CharField(max_length=255)
    tenant = tenant_fk("organisations")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "organisation"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_organisation_name_per_tenant",
            )
        ]


class OrganisationAttribute(models.Model):
    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="organisation_organisation_attribute",
    )
    type = models.IntegerField(choices=OrganisationTypes.FieldStr.items())

    def __str__(self):
        return self.organisation

    class Meta:
        unique_together = ("organisation", "type")
        db_table = "organisation_attribute"


class Tenant(models.Model):
    # Free-tier registration creates one Tenant per sign-up. The
    # subdomain is also the workspace's name: there is deliberately no
    # separate display field, which would be a synonym that drifts out
    # of step with the address people actually type.
    subdomain = models.CharField(max_length=63, unique=True)
    # Three states on two columns. Suspension is an operational lever
    # an operator uses and undoes; deletion is an ending. They differ
    # in reversibility and visibility, not in enforcement -- both stop
    # the host resolving, at the one line in resolve_tenant_from_host.
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(default=None, null=True, blank=True)
    # Per-workspace commercial entitlements, keyed by FeatureFlags.
    # Unknown keys are rejected at the serializer rather than by the
    # column, which is the trade a JSON field makes.
    features = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subdomain

    class Meta:
        db_table = "tenant"


class SystemUser(AbstractBaseUser, PermissionsMixin, SoftDeletes):
    TENANT_PATH = "tenant"
    email = models.EmailField(max_length=254)
    date_joined = models.DateTimeField(auto_now_add=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15, default=None, null=True)
    trained = models.BooleanField(default=False)
    # Email verification. AbstractBaseUser already defines `is_active = True`
    # as a plain class attribute, so ModelBackend, simplejwt's get_user and
    # IsMobileAssignment have all been consulting it and always getting True.
    # Overriding it with a real column makes those three checks meaningful at
    # once. The default keeps every existing row, the seeders, createsuperuser
    # and invited users active; only registrants start inactive, until they
    # follow the activation link.
    is_active = models.BooleanField(default=True)
    # Platform operator, not workspace owner. Deliberately a second
    # flag rather than a reuse of is_superuser, which every permission
    # class in this codebase reads as "owns this workspace" -- an
    # operator holding it would pass those checks the moment a tenant
    # was in scope. An operator has tenant=None; the two flags are
    # independent and no code path sets both.
    is_platform_admin = models.BooleanField(default=False)
    updated = models.DateTimeField(default=None, null=True)
    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.SET_NULL,
        related_name="user_organisation",
        default=None,
        null=True,
    )
    tenant = models.ForeignKey(
        to=Tenant,
        # PROTECT: deleting a tenant that still owns users must be an
        # explicit future decision, not a silent cascade.
        on_delete=models.PROTECT,
        related_name="users",
        default=None,
        null=True,
    )
    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def delete(self, using=None, keep_parents=False, hard: bool = False):
        if hard:
            return super().delete(using, keep_parents)
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def soft_delete(self) -> None:
        self.delete(hard=False)

    def restore(self) -> None:
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    def get_full_name(self):
        return "{0} {1}".format(self.first_name, self.last_name)

    @property
    def name(self):
        return "{0} {1}".format(self.first_name, self.last_name)

    def get_sign_pk(self):
        return signing.dumps(self.pk)

    class Meta:
        db_table = "system_user"
        constraints = [
            models.UniqueConstraint(
                fields=["email", "tenant"],
                name="unique_email_per_tenant",
            )
        ]


class TenantInspection(models.Model):
    """Where a one-time hand-off code lives until it is exchanged.

    Every column here is functional; this is not an audit feature.
    Nothing reads these rows once the code is burned, and nothing in
    the console displays them.

    A table rather than a cache entry because CACHES is a FileBasedCache
    under /var/tmp/cache, which is per-pod: the mint and the exchange
    are different requests, and with more than one replica the second
    would miss. `operator` and `tenant` are here because the exchange
    receives nothing but a code and has to learn which token to build.

    That the rows remain afterwards gives a forensic trail for free.
    Free is the operative word -- it is a byproduct, not a control, and
    no decision elsewhere in this feature rests on it.
    """

    operator = models.ForeignKey(
        to=SystemUser,
        # PROTECT so that revoking an operator can clear their flag and
        # keep the account, rather than having to choose between losing
        # the account and orphaning these rows.
        on_delete=models.PROTECT,
        related_name="inspections",
    )
    tenant = models.ForeignKey(
        to=Tenant, on_delete=models.PROTECT, related_name="inspections"
    )
    # Hashed: it lives 60 seconds and is burned on first use, but in the
    # clear it would be a live credential in any dump taken in between.
    code_hash = models.CharField(max_length=64, unique=True)
    code_used_at = models.DateTimeField(default=None, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def digest(code):
        """How a code becomes the column. Both the mint and the
        exchange go through here, so they cannot hash differently."""
        return hashlib.sha256(str(code).encode()).hexdigest()

    @classmethod
    def mint(cls, operator, tenant):
        """Record the visit and return the code, which is the only time
        it exists in the clear."""
        code = secrets.token_urlsafe(32)
        cls.objects.create(
            operator=operator, tenant=tenant, code_hash=cls.digest(code)
        )
        return code

    class Meta:
        db_table = "tenant_inspection"
