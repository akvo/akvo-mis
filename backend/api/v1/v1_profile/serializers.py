import random
import string
from typing import Any, Dict, cast
from rest_framework import serializers
from utils.custom_serializer_fields import (
    TenantScopedPrimaryKeyRelatedField,
    CustomPrimaryKeyRelatedField,
    CustomListField,
)
from utils.custom_generator import update_sqlite
from utils.tenant_scoped_model import TenantStampedSerializerMixin
from utils.custom_generator import (
    administration_csv_add,
    administration_csv_update,
)
from django.db.models import F, Value
from django.db.models.functions import Substr, Concat, Length
from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttribute,
    AdministrationAttributeValue,
    Entity,
    EntityData,
    Levels,
    Role,
    RoleAccess,
    RoleFeatureAccess,
)
from api.v1.v1_profile.constants import (
    DataAccessTypes,
    FeatureAccessTypes,
    FeatureTypes,
)


class RelatedAdministrationField(TenantScopedPrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value: Administration):
        return {
            "id": value.pk,
            "name": value.name,
            "full_name": value.full_name,
            "code": value.code,
        }


class AdministrationLevelsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Levels
        fields = ["id", "name"]


class LevelSerializer(serializers.ModelSerializer):
    # A tier's depth is append-only, so `level` is derived server-side from
    # the tenant's current maximum rather than bound from the payload; the
    # tenant itself is stamped from the request user. Only `name` is input.
    class Meta:
        model = Levels
        fields = ["id", "name", "level"]
        read_only_fields = ["level"]


class AdministrationAttributeSerializer(TenantStampedSerializerMixin,
                                        serializers.ModelSerializer):
    class Meta:
        model = AdministrationAttribute
        fields = ["id", "name", "type", "options"]

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        type = data.get("type", AdministrationAttribute.Type.VALUE)
        options = data.get("options", [])
        if type == AdministrationAttribute.Type.VALUE and len(options) > 0:
            error = (
                f'Attribute of type "{AdministrationAttribute.Type.VALUE}" '
                "should not have any options"
            )
            raise serializers.ValidationError(error)
        if type != AdministrationAttribute.Type.VALUE and len(options) < 1:
            error = f'Attribute of type "{type}" should have at least 1 option'
            raise serializers.ValidationError(error)

        return super().validate(data)


class AdministrationAttributeValueSerializer(serializers.ModelSerializer):
    INVALID_VALUE_ERROR = 'Invalid value for attribute "%s"'
    type = serializers.ReadOnlyField(source="attribute.type")

    class Meta:
        model = AdministrationAttributeValue
        fields = ["attribute", "type", "value"]

    def to_internal_value(self, data: Dict):
        value = data.get("value", None)
        if value:
            data["value"] = {"value": value}
        return super().to_internal_value(data)

    def validate(self, data):
        attribute = cast(AdministrationAttribute, data.get("attribute"))
        value = data.get("value", {}).get("value", None)
        if value:
            if attribute.type == AdministrationAttribute.Type.VALUE:
                self._validate_value_attribute(attribute, value)
            if attribute.type == AdministrationAttribute.Type.OPTION:
                self._validate_option_attribute(attribute, value)
            if attribute.type == AdministrationAttribute.Type.MULTIPLE_OPTION:
                self._validate_multiple_option_attribute(attribute, value)
            if attribute.type == AdministrationAttribute.Type.AGGREGATE:
                self._validate_aggregate_attribute(attribute, value)
        return data

    def _validate_value_attribute(self, attribute, value):
        if isinstance(value, dict):
            raise serializers.ValidationError(
                self.INVALID_VALUE_ERROR.format(attribute.name)
            )
        if isinstance(value, list) and len(value) > 0:
            raise serializers.ValidationError(
                self.INVALID_VALUE_ERROR.format(attribute.name)
            )

    def _validate_option_attribute(self, attribute, value):
        if value not in attribute.options:
            raise serializers.ValidationError(
                self.INVALID_VALUE_ERROR.format(attribute.name)
            )

    def _validate_multiple_option_attribute(self, attribute, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                self.INVALID_VALUE_ERROR.format(attribute.name)
            )
        for val in value:
            if val not in attribute.options:
                raise serializers.ValidationError(
                    self.INVALID_VALUE_ERROR.format(attribute.name)
                )

    def _validate_aggregate_attribute(self, attribute, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                self.INVALID_VALUE_ERROR.format(attribute.name)
            )
        for key in value:
            if key not in attribute.options:
                raise serializers.ValidationError(
                    self.INVALID_VALUE_ERROR.format(attribute.name)
                )

    def to_representation(self, instance: AdministrationAttributeValue):
        data = super().to_representation(instance)
        value = self._present_value(data, instance.attribute.type)
        data["value"] = value
        return data

    def _present_value(self, data: Dict, type: str):
        value = data.get("value", {}).get("value", None)
        if (
            value is None
            and type == AdministrationAttribute.Type.MULTIPLE_OPTION
        ):
            return []
        if value is None and type == AdministrationAttribute.Type.AGGREGATE:
            return {}
        return value


def validate_parent(obj: Administration):
    # Scope by the parent's own tenant: level numbers are unique per
    # tenant, not globally, so an unscoped get() matches one row per
    # tenant and raises MultipleObjectsReturned as soon as a second
    # tenant exists.
    sub_level = obj.level.level + 1
    if not Levels.objects.filter(
        level=sub_level, tenant=obj.tenant
    ).exists():
        raise serializers.ValidationError("Invalid parent level")


class AdministrationSerializer(TenantStampedSerializerMixin,
                               serializers.ModelSerializer):
    parent = RelatedAdministrationField(
        queryset=Administration.objects.all(), validators=[validate_parent]
    )  # type: ignore
    level = AdministrationLevelsSerializer(read_only=True)
    children = RelatedAdministrationField(
        source="parent_administration", read_only=True, many=True
    )
    attributes = AdministrationAttributeValueSerializer(
        many=True, required=False
    )

    class Meta:
        model = Administration
        fields = [
            "id",
            "name",
            "code",
            "path",
            "parent",
            "level",
            "children",
            "attributes",
        ]

    def __init__(self, *args, **kwargs):
        compact = kwargs.pop("compact", False)
        super().__init__(*args, **kwargs)
        if compact:
            allowed = set(["id", "name", "code", "parent", "level"])
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

    def create(self, validated_data):
        attributes = validated_data.pop("attributes", [])
        self._assign_level(validated_data)
        self._set_code(validated_data)
        instance = super().create(validated_data)
        update_sqlite(
            model=Administration,
            data={
                "id": instance.id,
                "name": instance.name,
                "code": instance.code,
                "parent": instance.parent.id,
                "level": instance.level.id,
                "path": instance.path,
            },
        )
        administration_csv_add(data=instance)
        for attribute in attributes:
            instance.attributes.create(**attribute)
        return instance

    def update(self, instance, validated_data):
        attributes = validated_data.pop("attributes", [])
        self._assign_level(validated_data)
        instance = super().update(instance, validated_data)

        adm_parent = validated_data.get("parent")
        if (adm_parent and str(adm_parent.id) not in instance.path):
            old_path = instance.path
            new_path = "{0}{1}.".format(
                adm_parent.path,
                adm_parent.id
            )
            instance.path = new_path
            instance.save()

            old_path_length = len(old_path)
            Administration.objects.filter(
                path__startswith=old_path
            ).update(
                path=Concat(
                    Value(new_path),
                    Substr(
                        F('path'),
                        old_path_length + 1,
                        Length(F('path')) - old_path_length
                    )
                )
            )
        for it in attributes:
            attribute = it.pop("attribute")
            data = dict(attribute=attribute)
            target, created = instance.attributes.get_or_create(
                **data, defaults=it
            )
            if not created:
                AdministrationAttributeValue.objects.filter(
                    id=target.id
                ).update(**it)
        update_sqlite(
            model=Administration,
            data={
                "name": instance.name,
                "code": instance.code,
                "parent": instance.parent.id,
                "level": instance.level.id,
                "path": instance.path,
            },
            id=instance.id,
        )
        administration_csv_update(data=instance)
        return instance

    def _set_code(self, validated_data):
        if len(validated_data.get("code", "")) > 0:
            return
        code = "".join(
            [
                random.choice(string.ascii_letters + string.digits + "-_")
                for _ in range(10)
            ]
        )
        validated_data.update({"code": code})

    def _assign_level(self, validated_data):
        # Resolve the child tier within the parent's tenant: level numbers
        # repeat across tenants, so an unscoped get() raises
        # MultipleObjectsReturned once a second tenant exists.
        parent = validated_data.get("parent")
        sublevel = Levels.objects.filter(
            level=parent.level.level + 1, tenant=parent.tenant
        ).first()
        if sublevel is None:
            raise ValueError()
        validated_data.update({"level": sublevel})


class EntitySerializer(TenantStampedSerializerMixin,
                       serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = ["id", "name"]


class RelatedEntityField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return {
            "id": value.pk,
            "name": value.name,
        }


class EntityDataSerializer(serializers.ModelSerializer):
    administration = RelatedAdministrationField(
        queryset=Administration.objects.all()
    )
    entity = RelatedEntityField(queryset=Entity.objects.all())

    class Meta:
        model = EntityData
        fields = ["id", "name", "code", "administration", "entity"]

    def create(self, validated_data):
        instance = super().create(validated_data)
        update_sqlite(
            model=EntityData,
            data={
                "id": instance.id,
                "name": instance.name,
                "code": instance.code,
                "entity": instance.entity.id,
                "administration": instance.administration.id,
                "parent": instance.administration.id,
            },
        )
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        update_sqlite(
            model=EntityData,
            data={
                "name": instance.name,
                "code": instance.code,
                "entity": instance.entity.id,
                "administration": instance.administration.id,
                "parent": instance.administration.id,
            },
            id=instance.id,
        )
        return instance


class DownloadAdministrationRequestSerializer(serializers.Serializer):
    level = CustomPrimaryKeyRelatedField(queryset=Levels.objects.none())
    administration = RelatedAdministrationField(
        queryset=Administration.objects.all()
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("level").queryset = Levels.objects.all()


class DownloadEntityDataRequestSerializer(serializers.Serializer):
    entity_ids = serializers.CharField(required=False)
    adm_id = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("adm_id").queryset = Administration.objects.all()

    def validate_entity_ids(self, value):
        entity_ids = [
            int(entity_id.strip())
            for entity_id in value.split(",")
            if entity_id.strip()
        ]
        queryset = Entity.objects.filter(pk__in=entity_ids)
        if queryset.count() != len(entity_ids):
            raise serializers.ValidationError(
                "One or more entity IDs are invalid."
            )
        return entity_ids

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        entity_ids = representation.get("entity_ids")
        if entity_ids:
            representation["entity_ids"] = [
                int(entity_id) for entity_id in entity_ids.split(",")
            ]
        return representation


class ListEntityDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityData
        fields = ["id", "code", "name"]


class RoleFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleFeatureAccess
        fields = [
            "id",
            "type",
            "access",
        ]


class RoleFeatureItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=list(FeatureTypes.FieldStr.keys()),
        help_text="Type of the feature",
    )
    access = serializers.ChoiceField(
        choices=list(FeatureAccessTypes.FieldStr.keys()),
        help_text="Access level for the feature",
    )

    class Meta:
        fields = ["type", "access"]


class RoleSerializer(serializers.ModelSerializer):
    # Define role_access as a SerializerMethodField for serialization
    role_access = CustomListField(
        child=serializers.ChoiceField(
            choices=list(DataAccessTypes.FieldStr.keys()),
        ),
        write_only=True,
    )
    role_access_list = serializers.SerializerMethodField(
        source="role_role_access",
        read_only=True,
        help_text="List of data access types for this role",
    )
    role_features = serializers.ListField(
        child=RoleFeatureItemSerializer(),
        write_only=True,
        required=False,
        default=[],
        help_text="List of features and their access levels for this role",
    )
    role_features_list = RoleFeatureSerializer(
        source="role_role_feature_access",
        many=True,
        read_only=True,
        help_text="List of features and their access levels for this role",
    )
    administration_level = CustomPrimaryKeyRelatedField(
        queryset=Levels.objects.all(),
    )

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "role_access",
            "role_access_list",
            "role_features",
            "role_features_list",
            "administration_level",
        ]

    def get_role_access_list(self, obj):
        """Return list of data access values for this role"""
        return [access.data_access for access in obj.role_role_access.all()]

    def create(self, validated_data):
        role_access = validated_data.pop("role_access", [])
        role_features = validated_data.pop("role_features", [])
        instance = super().create(validated_data)
        # Create RoleAccess objects individually and save them
        for access in role_access:
            RoleAccess.objects.create(role=instance, data_access=access)

        # Create RoleFeatureAccess objects individually and save them
        for feature in role_features:
            RoleFeatureAccess.objects.create(
                role=instance,
                type=feature["type"],
                access=feature["access"],
            )
        return instance

    def update(self, instance, validated_data):
        role_access = validated_data.pop("role_access", [])
        role_features = validated_data.pop("role_features", [])
        instance = super().update(instance, validated_data)
        # Remove existing data access
        instance.role_role_access.all().delete()
        # Create new role access objects
        for access in role_access:
            RoleAccess.objects.create(role=instance, data_access=access)
        # Remove existing feature access
        instance.role_role_feature_access.all().delete()
        # Create new role feature access objects
        for feature in role_features:
            RoleFeatureAccess.objects.create(
                role=instance,
                type=feature["type"],
                access=feature["access"],
            )
        return instance


class RoleDetailSerializer(serializers.ModelSerializer):
    administration_level = AdministrationLevelsSerializer(read_only=True)
    role_access = serializers.SerializerMethodField()
    role_features = serializers.SerializerMethodField()
    total_users = serializers.SerializerMethodField()

    def get_total_users(self, obj: Role):
        # Use distinct to count unique users
        return obj.role_user_role.values('user').distinct().count()

    def get_role_access(self, obj: Role):
        return [
            {
                "id": access.id,
                "data_access": access.data_access,
                "data_access_name": (
                    DataAccessTypes.FieldStr[access.data_access]
                ),
            }
            for access in obj.role_role_access.all()
        ]

    def get_role_features(self, obj: Role):
        return [
            {
                "id": feature.id,
                "type": feature.type,
                "access": feature.access,
                "type_name": FeatureTypes.FieldStr[feature.type],
                "access_name": FeatureAccessTypes.FieldStr[feature.access],
            }
            for feature in obj.role_role_feature_access.all()
        ]

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "administration_level",
            "role_access",
            "role_features",
            "total_users",
        ]
