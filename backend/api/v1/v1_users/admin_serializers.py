"""Serializers for the platform console.

Separate from `serializers.py` because these read across every
workspace, which nothing else in this app is allowed to do. Keeping
them apart makes the unscoped surface one file a reviewer can hold in
their head.
"""

from rest_framework import serializers

from api.v1.v1_profile.constants import FeatureFlags
from api.v1.v1_users.models import SystemUser, Tenant
from utils.workspace_name import host_collision_reason


# The three states a workspace can be in, and the rows each one selects.
# `TenantListSerializer.get_state` maps a row to one of these names and
# `list_tenants` maps a name back to a queryset -- the two are inverses
# of each other, so `tests_admin_tenants` asserts the round trip rather
# than trusting them to stay in step.
#
# `deleted` ignores `is_active` deliberately: deletion is an ending, and
# a deleted workspace is deleted whether or not it was suspended first.
TENANT_STATES = {
    "active": {"is_active": True, "deleted_at": None},
    "suspended": {"is_active": False, "deleted_at": None},
    "deleted": {"deleted_at__isnull": False},
}


class TenantListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "subdomain",
            "name",
            "language",
            "state",
            "features",
            "created_at",
        ]

    def get_name(self, instance):
        """The workspace's human label.

        Taken from the root administration unit that
        /register/configure creates, rather than a column of its own:
        the subdomain is the name, and a second field would be a
        synonym that drifts.

        Filtered in Python rather than with `.filter(parent=None)` on
        purpose. A queryset filter on a related manager ignores the
        prefetch cache and issues its own query, which is one query per
        workspace on a list -- exactly the N+1 the callers prefetch to
        avoid. `.all()` is what reads the cache.
        """
        roots = [
            unit
            for unit in instance.administrations.all()
            if unit.parent_id is None
        ]
        return roots[0].name if roots else ""

    def get_state(self, instance):
        # The inverse of TENANT_STATES; keep the two in step.
        if instance.deleted_at:
            return "deleted"
        return "active" if instance.is_active else "suspended"


class TenantFeaturesSerializer(serializers.Serializer):
    """Validates an entitlement payload against the known flags.

    This is the whole of what a JSON column gives up and the reason it
    is acceptable: an unknown key is a 400 here rather than a row that
    stores a flag nothing will ever read.
    """

    def validate(self, attrs):
        payload = self.initial_data
        if not isinstance(payload, dict):
            raise serializers.ValidationError(
                "Expected an object of feature keys."
            )
        unknown = set(payload) - set(FeatureFlags.FieldStr)
        if unknown:
            raise serializers.ValidationError(
                "Unknown feature(s): {0}. Accepted: {1}.".format(
                    ", ".join(sorted(unknown)),
                    ", ".join(sorted(FeatureFlags.FieldStr)),
                )
            )
        return {key: bool(value) for key, value in payload.items()}


class TenantSummarySerializer(TenantListSerializer):
    """One row per workspace: identity, state, and five counts.

    The counts arrive already annotated onto the queryset, so this
    serializer must never compute one itself -- a SerializerMethodField
    that queried would reintroduce the N+1 the annotation exists to
    avoid.
    """

    # Sourced from `*_count` aliases: Django refuses an annotation whose
    # name collides with a field or reverse accessor, and `users`,
    # `forms` and `dashboards` are all reverse accessors on Tenant. The
    # wire names stay what the console reads.
    users = serializers.IntegerField(read_only=True, source="users_count")
    forms = serializers.IntegerField(read_only=True, source="forms_count")
    dashboards = serializers.IntegerField(
        read_only=True, source="dashboards_count"
    )
    datapoints = serializers.IntegerField(
        read_only=True, source="datapoints_count"
    )
    devices = serializers.IntegerField(read_only=True, source="devices_count")

    class Meta(TenantListSerializer.Meta):
        fields = TenantListSerializer.Meta.fields + [
            "users",
            "forms",
            "dashboards",
            "datapoints",
            "devices",
        ]


class TenantRenameSerializer(serializers.Serializer):
    """The same rules registration applies, applied again.

    A rename reaches the same namespace by a different door, so the
    DNS-label shape, the console's reserved label and the embed-host
    collision all have to be re-checked here. Uniqueness is left to the
    database, exactly as `register()` leaves it: a pre-check would only
    be a read before a write.
    """

    subdomain = serializers.RegexField(
        regex=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$",
        max_length=63,
        error_messages={
            "invalid": (
                "Subdomain may only contain lowercase letters, digits "
                "and hyphens, and cannot start or end with a hyphen"
            )
        },
    )

    def validate_subdomain(self, value):
        """Only the host checks, deliberately.

        The console is where a withheld name gets granted: an operator
        may rename a workspace to a country name or a two-character
        name, and `self_service_reason` is never called from here. See
        the design doc, "How a country workspace actually gets
        created".
        """
        reason = host_collision_reason(value)
        if reason:
            raise serializers.ValidationError(reason)
        return value


class TenantUserSerializer(serializers.ModelSerializer):
    """A person in a workspace, as the console sees them.

    Identity and status only. Nothing here touches what they submitted.
    """

    name = serializers.CharField(read_only=True)
    devices = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    class Meta:
        model = SystemUser
        fields = ["id", "name", "email", "state", "devices", "last_login"]

    def get_devices(self, instance):
        return instance.mobile_assignments.count()

    def get_state(self, instance):
        if instance.deleted_at:
            return "deleted"
        return "active" if instance.is_active else "deactivated"


class OperatorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = SystemUser
        fields = ["id", "name", "email", "state", "date_joined", "last_login"]

    def get_state(self, instance):
        # An invited operator is inactive until the activation link is
        # followed, which is the same state a registrant sits in.
        return "active" if instance.is_active else "pending"


class OperatorInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if SystemUser.objects_with_deleted.filter(
            email=value, tenant__isnull=True
        ).exists():
            raise serializers.ValidationError(
                "A tenant-less account already exists for this address."
            )
        return value
