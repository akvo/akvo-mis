"""Serializers for the platform console.

Separate from `serializers.py` because these read across every
workspace, which nothing else in this app is allowed to do. Keeping
them apart makes the unscoped surface one file a reviewer can hold in
their head.
"""
from rest_framework import serializers

from api.v1.v1_profile.constants import FeatureFlags
from api.v1.v1_users.models import Tenant


class TenantListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ["id", "subdomain", "name", "state", "features",
                  "created_at"]

    def get_name(self, instance):
        """The workspace's human label.

        Taken from the root administration unit that
        /register/configure creates, rather than a column of its own:
        the subdomain is the name, and a second field would be a
        synonym that drifts.
        """
        root = instance.administrations.filter(parent__isnull=True).first()
        return root.name if root else ""

    def get_state(self, instance):
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
