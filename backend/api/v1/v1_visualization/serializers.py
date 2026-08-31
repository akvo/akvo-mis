import json
from rest_framework import serializers
from api.v1.v1_data.models import (
    FormData,
    Administration,
)
from api.v1.v1_forms.models import (
    Questions,
    QuestionOptions,
    QuestionTypes,
)
from utils.custom_serializer_fields import (
    CustomPrimaryKeyRelatedField,
    CustomIntegerField,
)
from api.v1.v1_visualization.formula import validate_shape


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOptions
        fields = ["id", "label", "color"]


class FormDataAnswerSerializer(serializers.Serializer):
    id = CustomIntegerField()
    value = CustomIntegerField()

    class Meta:
        fields = ["id", "value"]


class FormDataStatSerializer(serializers.Serializer):
    options = serializers.ListField(
        child=OptionSerializer()
    )
    data = serializers.ListField(
        child=FormDataAnswerSerializer()
    )

    class Meta:
        fields = ["options", "data"]


class FormDataStatsFilterSerializer(serializers.Serializer):
    question_id = CustomPrimaryKeyRelatedField(
        queryset=Questions.objects.none(),
        required=True,
    )

    def validate_question_id(self, value):
        valid_types = [
            QuestionTypes.number,
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]
        if value.type not in valid_types:
            raise serializers.ValidationError(
                "Question type must be one of: "
                "number, option, multiple_option."
            )
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        form = self.context.get('form')
        self.fields['question_id'].queryset = Questions.objects.filter(
            form=form,
            type__in=[
                QuestionTypes.number,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]
        ).all()

    class Meta:
        fields = [
            "question_id",
        ]


class MonitoringStatSerializer(serializers.Serializer):
    date = serializers.DateField()
    value = serializers.FloatField()


class GeoLocationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormData
        fields = ["id", "name", "geo", "administration_id"]


class GeoLocationFilterSerializer(serializers.Serializer):
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )
    criteria = serializers.CharField(required=False)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    include_monitoring = serializers.BooleanField(
        required=False, default=False
    )
    monitoring_form_id = serializers.IntegerField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get(
            "administration"
        ).queryset = Administration.objects.all()

    def validate_criteria(self, value):
        from api.v1.v1_visualization.constants import (
            VALID_VALUES_CRITERIA_TYPES,
        )
        from api.v1.v1_visualization.functions import (
            parse_criteria_string,
        )
        try:
            return parse_criteria_string(
                value, VALID_VALUES_CRITERIA_TYPES,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    class Meta:
        fields = [
            "administration", "criteria",
            "from_date", "to_date",
            "include_monitoring", "monitoring_form_id",
        ]


class FormulaValuesSerializer(serializers.Serializer):
    """Validates query params for the formula evaluator endpoint.

    The ``formula`` param arrives as a URL-encoded JSON string; the
    ``validate_formula`` hook parses and structurally validates it.
    """

    form_id = serializers.IntegerField(required=True)
    group_by = serializers.ChoiceField(
        choices=["parent_id"], required=True,
    )
    monitoring = serializers.ChoiceField(
        choices=["latest"], required=False, default="latest",
    )
    formula = serializers.CharField(required=True)
    criteria = serializers.CharField(required=False)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)

    def validate_formula(self, value):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                f"formula is not valid JSON: {exc}"
            )
        try:
            return validate_shape(parsed)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_criteria(self, value):
        from api.v1.v1_visualization.constants import (
            VALID_VALUES_CRITERIA_TYPES,
        )
        from api.v1.v1_visualization.functions import (
            parse_criteria_string,
        )
        try:
            return parse_criteria_string(
                value, VALID_VALUES_CRITERIA_TYPES,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    class Meta:
        fields = [
            "form_id", "group_by", "monitoring", "formula",
            "criteria", "from_date", "to_date",
        ]
