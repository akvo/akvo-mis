from typing import Any, Dict
from mis.settings import WEBDOMAIN
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from api.v1.v1_forms.models import Forms
from drf_spectacular.types import OpenApiTypes
from django.db.models import Q
from api.v1.v1_mobile.authentication import MobileAssignmentToken
from api.v1.v1_profile.models import Administration, Entity
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import FormStatus
from utils.custom_serializer_fields import (
    CustomCharField,
    CustomIntegerField,
    CustomListField,
    CustomDateTimeField,
    CustomPrimaryKeyRelatedField,
)
from api.v1.v1_mobile.models import MobileAssignment, MobileApk
from utils.custom_helper import CustomPasscode, generate_random_string


class MobileDataPointDownloadListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    form_id = serializers.IntegerField()
    name = serializers.CharField()
    administration_id = serializers.IntegerField()
    url = serializers.SerializerMethodField()
    last_updated = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.URI)
    def get_url(self, obj):
        return f"{WEBDOMAIN}/datapoints/{obj.get('uuid')}.json"

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_last_updated(self, obj):
        return obj["updated"] if obj["updated"] else obj["created"]

    class Meta:
        fields = [
            "id",
            "form_id",
            "name",
            "administration_id",
            "url",
            "last_updated",
        ]


class MobileFormSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    parentId = serializers.ReadOnlyField(source="parent_id")
    version = serializers.CharField()
    url = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.URI)
    def get_url(self, obj):
        return f"/form/{obj.id}"

    class Meta:
        model = Forms
        fields = ["id", "version", "parentId", "url"]


class MobileAssignmentFormsSerializer(serializers.Serializer):
    code = CustomCharField(max_length=255, write_only=True)
    name = serializers.CharField(read_only=True)
    syncToken = serializers.SerializerMethodField()
    formsUrl = serializers.SerializerMethodField()

    @extend_schema_field(MobileFormSerializer(many=True))
    def get_formsUrl(self, obj):
        # Return only explicitly assigned forms (no auto-include of children)
        forms = obj.forms.filter(
            status=FormStatus.published
        ).order_by("id")
        return MobileFormSerializer(instance=forms, many=True).data

    def get_syncToken(self, obj):
        return str(MobileAssignmentToken.for_assignment(obj))

    def validate_code(self, value):
        passcode = CustomPasscode().encode(value)
        if not MobileAssignment.objects.filter(passcode=passcode).exists():
            raise serializers.ValidationError("Invalid passcode")
        return value

    class Meta:
        fields = ["name", "syncToken", "formsUrl", "code"]


class IdAndNameRelatedField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self) -> bool:
        return False

    def to_representation(self, value):
        return {
            "id": value.pk,
            "name": value.name,
        }


class FormsAndEntityValidation(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self) -> bool:
        return False

    def to_representation(self, value):
        return {
            "id": value.pk,
            "name": value.name,
            "type": "monitoring" if value.parent_id else "registration",
        }

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")
        selected_adm = request.data.get("administrations") if request else None
        selected_forms = request.data.get("forms") if request else None

        # Validate monitoring forms have their parent registration included
        # Use the filtered queryset (published forms only) for validation
        if selected_forms:
            selected_form_objs = queryset.filter(pk__in=selected_forms)
            monitoring_forms = selected_form_objs.filter(
                parent__isnull=False
            ).select_related("parent")
            registration_ids = set(
                selected_form_objs.filter(
                    parent__isnull=True
                ).values_list("id", flat=True)
            )

            missing_parents = []
            for mf in monitoring_forms:
                if mf.parent_id not in registration_ids:
                    missing_parents.append({
                        "form": mf.id,
                        "monitoring_form": mf.name,
                        "required_registration": mf.parent.name,
                        "required_registration_id": mf.parent_id,
                    })

            if missing_parents:
                raise serializers.ValidationError(missing_parents)

        entity_forms = queryset.filter(
            pk__in=selected_forms, form_questions__extra__icontains="entity"
        ).distinct()
        if entity_forms.exists():
            forms = entity_forms.all()
            no_data = []
            for f in forms:
                questions = f.form_questions.filter(extra__icontains="entity")
                for q in questions:
                    entity = Entity.objects.filter(
                        name=q.extra.get("name")
                    ).first()
                    if not entity:
                        no_data.append(
                            {
                                "form": f.id,
                                "entity": q.extra.get("name"),
                                "exists": False,
                            }
                        )
                    if entity and selected_adm:
                        # Build query for all selected administrations
                        query = Q()
                        for adm_id in selected_adm:
                            adm = Administration.objects.filter(
                                id=adm_id
                            ).first()
                            if adm:
                                adm_path = adm.path if adm.parent else adm.id
                                # Add OR condition for this administration
                                query |= Q(administration__id=adm_id) | Q(
                                    administration__path__startswith=adm_path
                                )

                        # Check if entity has data in any of
                        # the selected administrations or their children
                        entity_has_data = entity.entity_data.filter(query)
                        if not entity_has_data.exists():
                            no_data.append(
                                {
                                    "form": f.id,
                                    "entity": entity.name,
                                    "exists": True,
                                }
                            )
            if len(no_data) > 0:
                raise serializers.ValidationError(no_data)

        return queryset


class MobileAssignmentSerializer(serializers.ModelSerializer):
    forms = FormsAndEntityValidation(
        queryset=Forms.objects.filter(status=FormStatus.published).all(),
        many=True
    )
    administrations = IdAndNameRelatedField(
        queryset=Administration.objects.all(), many=True
    )
    passcode = serializers.SerializerMethodField()
    created_by = serializers.ReadOnlyField(source="user.email")

    class Meta:
        model = MobileAssignment
        fields = [
            "id",
            "name",
            "passcode",
            "forms",
            "administrations",
            "created_by",
        ]
        read_only_fields = ["passcode"]

    def create(self, validated_data: Dict[str, Any]):
        user = self.context.get("request").user
        passcode = CustomPasscode().encode(generate_random_string(8))
        validated_data.update({"user": user, "passcode": passcode})
        return super().create(validated_data)

    def get_passcode(self, obj):
        return CustomPasscode().decode(obj.passcode)


class MobileApkSerializer(serializers.Serializer):
    apk_version = serializers.CharField(max_length=50)
    apk_url = serializers.CharField(max_length=255)
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        return MobileApk.objects.create(**validated_data)

    class Meta:
        model = MobileApk
        fields = ["apk_version", "apk_url", "created_at"]


class SyncDeviceFormDataSerializer(serializers.Serializer):
    formId = CustomPrimaryKeyRelatedField(
        queryset=Forms.objects.none()
    )
    name = CustomCharField(max_length=255)
    duration = CustomIntegerField(
        min_value=0, max_value=86400000, default=0
    )
    submittedAt = CustomDateTimeField()
    geo = CustomListField(child=serializers.IntegerField())
    uuid = serializers.UUIDField(required=False, allow_null=True)
    submission_key = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=64,
        help_text=(
            "Per-submission idempotency token. Resending the same key stores "
            "nothing and still returns 200."
        ),
    )
    answers = serializers.DictField(required=False, default=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("formId").queryset = Forms.objects.all()

    class Meta:
        fields = [
            "formId",
            "name",
            "duration",
            "submittedAt",
            "geo",
            "uuid",
            "submission_key",
            "answers",
        ]


class SyncDeviceParamsSerializer(serializers.Serializer):
    id = CustomPrimaryKeyRelatedField(
        queryset=FormData.objects_draft.none(),
        required=False
    )
    is_draft = serializers.BooleanField(default=False)
    is_published = serializers.BooleanField(default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("id").queryset = FormData.objects_draft.all()

    class Meta:
        fields = [
            "id",
            "is_draft",
            "is_published",
        ]


class DraftFormDataSerializer(serializers.ModelSerializer):
    form = CustomPrimaryKeyRelatedField(
        queryset=Forms.objects.all(),
        source="form_id"
    )
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.all(),
        source="administration_id"
    )
    datapoint_name = CustomCharField(source="name")
    geolocation = CustomListField(
        source="geo",
        required=False,
        allow_null=True
    )
    submittedAt = CustomDateTimeField(
        source="created",
        read_only=True,
    )
    json = serializers.SerializerMethodField(
        read_only=True,
        help_text="JSON representation of the answers."
    )
    repeats = serializers.SerializerMethodField(
        read_only=True,
        help_text="Number of times the form has been repeated."
    )

    def get_json(self, obj):
        # Create a dictionary to hold the answers
        # question_id: answer_value pairs
        answers = {}
        for answer in obj.data_answer.order_by(
            "question__question_group_id", "question__order"
        ).all():
            answers.update(answer.to_key)
        return answers

    def get_repeats(self, obj):
        # Create a dictionary to count repeats based on question group IDs
        repeats_count = {}
        for answer in obj.data_answer.filter(
            question__question_group__repeatable=True
        ).all():
            group_id = answer.question.question_group_id
            if group_id:
                repeats_count[group_id] = repeats_count.get(group_id, 0) + 1
        return repeats_count

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "form",
            "administration",
            "datapoint_name",
            "geolocation",
            "submittedAt",
            "duration",
            "json",
            "repeats",
        ]
        read_only_fields = ["id", "submittedAt", "json", "repeats"]


class MobileAssignmentListRequestSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
