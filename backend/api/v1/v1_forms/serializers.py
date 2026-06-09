import numpy as np
from collections import OrderedDict

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from api.v1.v1_data.models import Answers
from api.v1.v1_forms.constants import QuestionTypes, AttributeTypes, FormStatus
from api.v1.v1_forms.models import (
    FormPublishedVersion,
    Forms,
    QuestionGroup,
    Questions,
    QuestionOptions,
    QuestionAttribute,
)
from api.v1.v1_profile.models import (
    Administration,
    Entity,
    DataAccessTypes,
)
from api.v1.v1_users.models import SystemUser
from mis.settings import FORM_GEO_VALUE
from utils.custom_serializer_fields import (
    CustomChoiceField,
    CustomPrimaryKeyRelatedField,
    CustomMultipleChoiceField,
)
from utils.default_serializers import CommonDataSerializer, GeoFormatSerializer


def _question_type_str(instance: Questions) -> str:
    """Return the semantic type string for a question.
    """
    return QuestionTypes.FieldStr.get(instance.type, "").lower()


class ListOptionSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        result = super(ListOptionSerializer, self).to_representation(instance)
        return OrderedDict(
            [(key, result[key]) for key in result if result[key] is not None]
        )

    class Meta:
        model = QuestionOptions
        fields = ["id", "value", "label", "order", "color", "translations"]


class ListQuestionSerializer(serializers.ModelSerializer):
    option = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    center = serializers.SerializerMethodField()
    api = serializers.SerializerMethodField()
    rule = serializers.SerializerMethodField()
    extra = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    tooltip = serializers.SerializerMethodField()
    fn = serializers.SerializerMethodField()
    pre = serializers.SerializerMethodField()
    displayOnly = serializers.BooleanField(source="display_only")

    @extend_schema_field(ListOptionSerializer(many=True))
    def get_option(self, instance: Questions):
        if instance.type in [
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            return ListOptionSerializer(
                instance=instance.options.all(), many=True
            ).data
        if instance.type == QuestionTypes.tree:
            return instance.tree_option
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance: Questions):
        return _question_type_str(instance)

    @extend_schema_field(
        inline_serializer(
            "CascadeApiFormat",
            fields={
                "endpoint": serializers.CharField(),
                "list": serializers.CharField(),
                "initial": serializers.CharField(),
                "query_params": serializers.CharField(),
            },
        )
    )
    def get_api(self, instance: Questions):
        if instance.type == QuestionTypes.cascade:
            extra_type = (instance.extra or {}).get("type")
            if extra_type == "entity":
                return instance.api
            # Administration cascade: generate dynamic user-scoped endpoint.
            user = self.context.get("user")
            administration = Administration.objects.filter(
                parent__isnull=True
            ).first()
            user_role = user.user_user_role.filter(
                administration__parent__isnull=False
            ).order_by("administration__level__level").first()
            if user_role:
                administration = user_role.administration
            max_level = instance.api.get("max_level") \
                if instance.api else None
            extra_objects = {}
            if max_level:
                extra_objects = {
                    "query_params": f"?max_level={max_level}",
                }
            if not user.is_superuser:
                if max_level:
                    extra_objects = {
                        "query_params": f"&max_level={max_level}",
                    }
                initial = administration.id
                if administration.parent:
                    filter_children = "&".join([
                        f"filter_children={ur.administration.id}"
                        for ur in user.user_user_role.filter(
                            administration__parent=administration.parent
                        ).all()
                    ])
                    initial = f"{administration.parent.id}?{filter_children}"
                return {
                    "endpoint": "/api/v1/administration",
                    "list": "children",
                    "initial": initial,
                    **extra_objects,
                }
            return {
                "endpoint": "/api/v1/administration",
                "list": "children",
                "initial": administration.id,
                **extra_objects,
            }
        if instance.type == QuestionTypes.attachment:
            return instance.api
        return None

    @extend_schema_field(GeoFormatSerializer)
    def get_center(self, instance: Questions):
        if instance.type == QuestionTypes.geo:
            return FORM_GEO_VALUE
        if instance.type in (QuestionTypes.geoshape, QuestionTypes.geotrace):
            return instance.center
        return None

    @extend_schema_field(
        inline_serializer(
            "QuestionRuleFormat",
            fields={
                "min": serializers.FloatField(),
                "max": serializers.FloatField(),
                "allowDecimal": serializers.BooleanField(),
            },
        )
    )
    def get_rule(self, instance: Questions):
        return instance.rule

    @extend_schema_field(
        inline_serializer(
            "QuestionExtraFormat",
            fields={"allowOther": serializers.BooleanField()},
        )
    )
    def get_extra(self, instance: Questions):
        return instance.extra

    @extend_schema_field(
        inline_serializer(
            "QuestionTooltipFormat", fields={"text": serializers.CharField()}
        )
    )
    def get_tooltip(self, instance: Questions):
        return instance.tooltip

    @extend_schema_field(
        inline_serializer(
            "QuestionFnFormat",
            fields={
                "fnColor": serializers.JSONField(),
                "fnString": serializers.CharField(),
                "multiline": serializers.BooleanField(),
            },
        )
    )
    def get_fn(self, instance: Questions):
        return instance.fn

    @extend_schema_field(
        inline_serializer(
            "QuestionPreFormat",
            fields={
                "answer": serializers.CharField(),
                "fill": serializers.JSONField(),
            },
        )
    )
    def get_pre(self, instance: Questions):
        return instance.pre

    def to_representation(self, instance):
        result = super(ListQuestionSerializer, self).to_representation(
            instance
        )
        return OrderedDict(
            [(key, result[key]) for key in result if result[key] is not None]
        )

    @extend_schema_field(
        inline_serializer(
            "QuestionSourceFormat",
            fields={
                "file": serializers.CharField(),
                "parent": serializers.ListField(
                    child=serializers.IntegerField()
                ),
                "max_level": serializers.IntegerField(),
            },
        )
    )
    def get_source(self, instance: Questions):
        user = self.context.get("user")
        assignment = self.context.get("mobile_assignment")
        if instance.type == QuestionTypes.cascade:
            extra_type = (instance.extra or {}).get("type")
            if extra_type == "entity":
                cascade_name = (instance.extra or {}).get("name")
                entity_type = Entity.objects.filter(
                    name=cascade_name
                ).first()
                entity_id = entity_type.id if entity_type else None
                return {
                    "file": "entity_data.sqlite",
                    "cascade_type": entity_id,
                    "cascade_parent": "administrator.sqlite",
                }
            # Administration cascade (extra.type="administration" or null).
            return {
                "file": "administrator.sqlite",
                "parent_id": [a.id for a in assignment.administrations.all()]
                if assignment
                else [
                    ur.administration.id
                    for ur in user.user_user_role.all()
                ],
            }
        return None

    class Meta:
        model = Questions
        fields = [
            "id",
            "order",
            "name",
            "label",
            "short_label",
            "type",
            "required",
            "dependency",
            "dependency_rule",
            "option",
            "center",
            "api",
            "meta",
            "rule",
            "extra",
            "source",
            "tooltip",
            "fn",
            "pre",
            "displayOnly",
            "translations",
            "columns",
            "limit",
        ]


# TODO: confirm Order in QuestionGroup model
class ListQuestionGroupSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()

    @extend_schema_field(ListQuestionSerializer(many=True))
    def get_question(self, instance: QuestionGroup):
        return ListQuestionSerializer(
            instance=instance.question_group_question.filter(
                deleted_at__isnull=True
            ).order_by("order"),
            context=self.context,
            many=True,
        ).data

    class Meta:
        model = QuestionGroup
        fields = [
            "name",
            "label",
            "question",
            "repeatable",
            "repeat_text",
            "order",
            "translations",
        ]


class ListAdministrationCascadeSerializer(serializers.ModelSerializer):
    value = serializers.ReadOnlyField(source="id")
    label = serializers.ReadOnlyField(source="name")
    children = serializers.SerializerMethodField()

    @extend_schema_field(
        inline_serializer(
            "children",
            fields={
                "value": serializers.IntegerField(),
                "label": serializers.CharField(),
            },
            many=True,
        )
    )
    def get_children(self, instance: Administration):
        return ListAdministrationCascadeSerializer(
            instance=instance.parent_administration.all(), many=True
        ).data

    class Meta:
        model = Administration
        fields = ["value", "label", "children"]


class WebFormDetailSerializer(serializers.ModelSerializer):
    question_group = serializers.SerializerMethodField()
    cascades = serializers.SerializerMethodField()

    @extend_schema_field(ListQuestionGroupSerializer(many=True))
    def get_question_group(self, instance: Forms):
        return ListQuestionGroupSerializer(
            instance=instance.form_question_group.filter(
                deleted_at__isnull=True
            ).order_by("order"),
            many=True,
            context=self.context,
        ).data

    @extend_schema_field(serializers.ListField())
    def get_cascades(self, instance: Forms):
        cascade_questions = Questions.objects.filter(
            type=QuestionTypes.cascade,
            form=instance,
            deleted_at__isnull=True,
        ).all()
        source = []
        for cascade_question in cascade_questions:
            extra_type = (cascade_question.extra or {}).get("type")
            if extra_type == "entity":
                source.append("/sqlite/entity_data.sqlite")
            else:
                source.append("/sqlite/administrator.sqlite")
        return np.unique(source)

    class Meta:
        model = Forms
        fields = [
            "id",
            "name",
            "version",
            "cascades",
            "approval_instructions",
            "parent",
            "languages",
            "default_language",
            "translations",
            "question_group",
        ]


class ListFormSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    def get_status(self, obj):
        return FormStatus.FieldStr.get(obj.status, "draft")

    def get_created_by(self, obj):
        return obj.created_by.email if obj.created_by else None

    def get_updated_by(self, obj):
        return obj.updated_by.email if obj.updated_by else None

    class Meta:
        model = Forms
        fields = [
            "id",
            "name",
            "version",
            "status",
            "parent",
            "type",
            "created",
            "updated",
            "created_by",
            "updated_by",
        ]


class FormDataListQuestionSerializer(serializers.ModelSerializer):
    option = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()

    @extend_schema_field(ListOptionSerializer(many=True))
    def get_option(self, instance: Questions):
        if instance.type in [
            QuestionTypes.geo,
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            return ListOptionSerializer(
                instance=instance.options.all(), many=True
            ).data
        return None

    @extend_schema_field(
        CustomChoiceField(
            choices=[
                QuestionTypes.FieldStr[d].lower()
                for d in QuestionTypes.FieldStr
            ]
        )
    )
    def get_type(self, instance: Questions):
        return _question_type_str(instance)

    @extend_schema_field(
        CustomMultipleChoiceField(
            choices=[
                AttributeTypes.FieldStr[a] for a in AttributeTypes.FieldStr
            ]
        )
    )
    def get_attributes(self, instance: Questions):
        attribute_ids = (
            QuestionAttribute.objects.filter(question=instance)
            .values_list("attribute", flat=True)
            .distinct()
        )
        if attribute_ids:
            return [AttributeTypes.FieldStr.get(a) for a in attribute_ids]
        return []

    @extend_schema_field(GeoFormatSerializer)
    def to_representation(self, instance):
        result = super(FormDataListQuestionSerializer, self).to_representation(
            instance
        )
        return OrderedDict(
            [(key, result[key]) for key in result if result[key] is not None]
        )

    class Meta:
        model = Questions
        fields = [
            "id",
            "form",
            "question_group",
            "name",
            "label",
            "short_label",
            "order",
            "meta",
            "api",
            "type",
            "required",
            "rule",
            "option",
            "dependency",
            "dependency_rule",
            "display_only",
            "attributes",
        ]


class FormDataQuestionGroupSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    repeatable = serializers.BooleanField(default=False)
    repeat_text = serializers.CharField(required=False, allow_null=True)

    @extend_schema_field(FormDataListQuestionSerializer(many=True))
    def get_question(self, instance: QuestionGroup):
        return FormDataListQuestionSerializer(
            instance=instance.question_group_question.filter(
                deleted_at__isnull=True
            ).order_by("order"),
            many=True,
        ).data

    class Meta:
        model = QuestionGroup
        fields = [
            "id", "label", "name", "question", "repeatable", "repeat_text"
        ]


class FormDataSerializer(serializers.ModelSerializer):
    question_group = serializers.SerializerMethodField()

    @extend_schema_field(FormDataQuestionGroupSerializer(many=True))
    def get_question_group(self, instance: Forms):
        return FormDataQuestionGroupSerializer(
            instance=instance.form_question_group.filter(
                deleted_at__isnull=True
            ).order_by("order"),
            many=True,
        ).data

    class Meta:
        model = Forms
        fields = [
            "id",
            "name",
            "question_group",
            "approval_instructions",
            "parent",
        ]


class FormApproverRequestSerializer(serializers.Serializer):
    administration_id = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none()
    )
    form_id = CustomPrimaryKeyRelatedField(queryset=Forms.objects.none())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("form_id").queryset = Forms.objects.all()
        self.fields.get(
            "administration_id"
        ).queryset = Administration.objects.all()


class FormApproverUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemUser
        fields = ["id", "first_name", "last_name", "email"]


class FormApproverResponseSerializer(serializers.ModelSerializer):
    users = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()

    @extend_schema_field(FormApproverUserSerializer(many=True))
    def get_users(self, instance: Administration):
        approvers = instance.user_role_administration.filter(
            role__role_role_access__data_access=DataAccessTypes.approve,
            user__user_form__form=self.context.get("form"),
        ).select_related("user")
        approvers = [
            approver.user for approver in approvers
        ]
        return FormApproverUserSerializer(
            instance=approvers, many=True
        ).data

    @extend_schema_field(CommonDataSerializer)
    def get_administration(self, instance: Administration):
        return {"id": instance.id, "name": instance.name}

    class Meta:
        model = Administration
        fields = ["users", "administration"]


# ─── Form Builder CRUD Serializers ───────────────────────────────────────────


class FormDetailQuestionSerializer(serializers.ModelSerializer):
    """Question serializer for form builder detail/CRUD endpoints.

    Returns all editor-relevant fields including disable_delete.
    """
    type = serializers.SerializerMethodField()
    option = serializers.SerializerMethodField()
    disable_delete = serializers.SerializerMethodField()

    def get_type(self, instance: Questions):
        return _question_type_str(instance)

    def get_option(self, instance: Questions):
        if instance.type == QuestionTypes.tree:
            return instance.tree_option
        return ListOptionSerializer(
            instance=instance.options.all().order_by("order"), many=True
        ).data

    def get_disable_delete(self, instance: Questions):
        if Answers.objects.filter(question=instance).exists():
            return True
        return None

    def to_representation(self, instance):
        result = super().to_representation(instance)
        return OrderedDict(
            [(key, result[key]) for key in result if result[key] is not None]
        )

    class Meta:
        model = Questions
        fields = [
            "id",
            "order",
            "name",
            "label",
            "short_label",
            "type",
            "meta",
            "required",
            "rule",
            "dependency",
            "dependency_rule",
            "api",
            "extra",
            "tooltip",
            "fn",
            "pre",
            "display_only",
            "variable_name",
            "hidden_string",
            "required_double_entry",
            "disabled",
            "addon_before",
            "addon_after",
            "data_api_url",
            "center",
            "translations",
            "columns",
            "limit",
            "option",
            "disable_delete",
        ]


class FormDetailQuestionGroupSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()

    def get_question(self, instance: QuestionGroup):
        return FormDetailQuestionSerializer(
            instance=instance.question_group_question.filter(
                deleted_at__isnull=True
            ).order_by("order"),
            many=True,
        ).data

    class Meta:
        model = QuestionGroup
        fields = [
            "id", "name", "label", "order",
            "repeatable", "repeat_text", "translations", "question",
        ]


class FormDetailSerializer(serializers.ModelSerializer):
    """Extended form serializer for form builder endpoints."""
    status = serializers.SerializerMethodField()
    question_group = serializers.SerializerMethodField()
    latest_version = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    def get_status(self, obj):
        return FormStatus.FieldStr.get(obj.status, "draft")

    def get_latest_version(self, obj):
        last = obj.published_versions.order_by("-version").first()
        return last.version if last else obj.version

    def get_question_group(self, instance: Forms):
        return FormDetailQuestionGroupSerializer(
            instance=instance.form_question_group.filter(
                deleted_at__isnull=True
            ).order_by("order"),
            many=True,
        ).data

    def get_created_by(self, obj):
        return obj.created_by.email if obj.created_by else None

    def get_updated_by(self, obj):
        return obj.updated_by.email if obj.updated_by else None

    class Meta:
        model = Forms
        fields = [
            "id",
            "name",
            "description",
            "version",
            "latest_version",
            "status",
            "published_at",
            "active_version_id",
            "type",
            "approval_instructions",
            "parent",
            "languages",
            "default_language",
            "translations",
            "created",
            "updated",
            "created_by",
            "updated_by",
            "question_group",
        ]


class FormPublishedVersionSerializer(serializers.ModelSerializer):
    """Serializer for the published versions list endpoint."""
    published_by = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    def get_published_by(self, instance):
        return instance.published_by.email if instance.published_by else None

    def get_is_active(self, instance):
        return instance.form.active_version_id == instance.id

    class Meta:
        model = FormPublishedVersion
        fields = ["id", "version", "published_at", "published_by", "is_active"]


class FormUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    type = serializers.IntegerField(
        required=False,
        help_text="1 = registration, 2 = monitoring",
    )
    approval_instructions = serializers.CharField(
        required=False, allow_null=True
    )
    parent = serializers.IntegerField(required=False, allow_null=True)
    question_group = serializers.ListField(
        required=False,
        child=serializers.DictField(),
        help_text=(
            "Full question group array. Omit to skip group/question updates. "
            "Pass ?allow_delete=true to soft-delete removed groups/questions."
        ),
    )
