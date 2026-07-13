from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django_q.tasks import async_task

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.v1.v1_data.models import (
    FormData,
    Answers,
    AnswerHistory,
)
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import (
    Questions,
)
from api.v1.v1_profile.models import Administration, EntityData
from api.v1.v1_users.models import Organisation
from utils.custom_serializer_fields import (
    CustomPrimaryKeyRelatedField,
    UnvalidatedField,
    CustomListField,
    CustomCharField,
    CustomIntegerField,
)
from utils.functions import update_date_time_format, get_answer_value
from utils.functions import get_answer_history


class SubmitFormDataSerializer(serializers.ModelSerializer):
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none()
    )
    name = CustomCharField()
    geo = CustomListField(required=False, allow_null=True)
    submitter = CustomCharField(required=False)
    duration = CustomIntegerField(required=False)
    uuid = serializers.CharField(required=False)
    submission_key = serializers.CharField(
        required=False, allow_null=True, max_length=64
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get(
            "administration"
        ).queryset = Administration.objects.all()

    class Meta:
        model = FormData
        fields = [
            "name",
            "geo",
            "administration",
            "submitter",
            "duration",
            "uuid",
            "submission_key",
        ]


class SubmitFormDataAnswerSerializer(serializers.ModelSerializer):
    value = UnvalidatedField(allow_null=False)
    question = CustomPrimaryKeyRelatedField(queryset=Questions.objects.none())
    index = CustomIntegerField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("question").queryset = Questions.objects.all()

    def validate_value(self, value):
        return value

    def validate(self, attrs):
        # Skip validation if this is a draft
        is_draft = self.context.get("is_draft", False)
        if is_draft:
            # If the form is a draft, skip validation for value
            # but ensure that the question is provided and
            # value is correct type
            if not attrs.get("question"):
                raise ValidationError(
                    "Question is required for Answer"
                )
            if attrs.get("value") is None:
                attrs["value"] = ""
            question = attrs.get("question")
            if question.type in [
                QuestionTypes.geo,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ] and not isinstance(attrs.get("value"), list):
                raise ValidationError(
                    "Valid list value is required for Question:{0}".format(
                        question.id
                    )
                )
            if isinstance(attrs.get("value"), list) and question.type in [
                QuestionTypes.input,
                QuestionTypes.text,
                QuestionTypes.image,
                QuestionTypes.date,
                QuestionTypes.attachment,
                QuestionTypes.signature,
                QuestionTypes.autofield,
                QuestionTypes.number,
                QuestionTypes.cascade,
            ]:
                raise ValidationError(
                    "Valid string value is required for Question:{0}".format(
                        question.id
                    )
                )
            return attrs

        if attrs.get("value") == "":
            raise ValidationError(
                "Value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )

        if (
            isinstance(attrs.get("value"), list)
            and len(attrs.get("value")) == 0
        ):
            raise ValidationError(
                "Value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )

        if not isinstance(attrs.get("value"), list) and attrs.get(
            "question"
        ).type in [
            QuestionTypes.geo,
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            raise ValidationError(
                "Valid list value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )
        elif not isinstance(attrs.get("value"), str) and attrs.get(
            "question"
        ).type in [
            QuestionTypes.input,
            QuestionTypes.text,
            QuestionTypes.image,
            QuestionTypes.date,
            QuestionTypes.attachment,
            QuestionTypes.signature,
        ]:
            raise ValidationError(
                "Valid string value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )
        elif not (
            isinstance(attrs.get("value"), int)
            or isinstance(attrs.get("value"), float)
        ) and attrs.get("question").type in [
            QuestionTypes.number,
            QuestionTypes.cascade,
        ]:
            raise ValidationError(
                "Valid number value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )

        if attrs.get("question").type == QuestionTypes.cascade:
            attrs["value"] = int(float(attrs.get("value")))

        return attrs

    class Meta:
        model = Answers
        fields = ["question", "value", "index"]


class SubmitFormSerializer(serializers.Serializer):
    data = SubmitFormDataSerializer()
    answer = SubmitFormDataAnswerSerializer(many=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        data = validated_data.get("data")
        data["form"] = self.context.get("form")
        data["created_by"] = self.context.get("user")
        data["updated_by"] = self.context.get("user")
        obj_data = self.fields.get("data").create(data)
        # Answer value based on Question type
        # - geo = 1 #option
        # - administration = 2 #value
        # - text = 3 #name
        # - number = 4 #value
        # - option = 5 #option
        # - multiple_option = 6 #option
        # - cascade = 7 #option
        # - photo = 8 #name
        # - date = 9 #name
        # - autofield = 10 #name
        # - attachment = 11 #name

        for answer in validated_data.get("answer"):
            name = None
            value = None
            option = None

            if answer.get("question").type in [
                QuestionTypes.geo,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]:
                option = answer.get("value")
            elif answer.get("question").type in [
                QuestionTypes.input,
                QuestionTypes.text,
                QuestionTypes.image,
                QuestionTypes.date,
                QuestionTypes.autofield,
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            elif answer.get("question").type == QuestionTypes.cascade:
                id = answer.get("value")
                q_api = answer.get("question").api or {}
                ep = q_api.get("endpoint", "")
                extra_type = (answer.get("question").extra or {}).get("type")
                val = None
                if "organisation" in ep:
                    obj = Organisation.objects.filter(pk=id).first()
                    val = obj.name if obj else None
                elif "entity-data" in ep or extra_type == "entity":
                    obj = EntityData.objects.filter(pk=id).first()
                    val = obj.name if obj else None
                else:
                    # administration cascade: store both name and integer value
                    obj = Administration.objects.filter(pk=id).first()
                    val = obj.name if obj else None
                    value = id
                name = val
            else:
                # for number question type
                value = answer.get("value")

            Answers.objects.create(
                data=obj_data,
                question=answer.get("question"),
                name=name,
                value=value,
                options=option,
                created_by=self.context.get("user"),
            )
        # Refresh materialized view via async task
        async_task("api.v1.v1_data.tasks.seed_approved_data", obj_data)

        return object


class AnswerHistorySerializer(serializers.Serializer):
    value = serializers.FloatField()
    created = CustomCharField()
    created_by = CustomCharField()


class ListDataAnswerSerializer(serializers.ModelSerializer):
    history = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    @extend_schema_field(AnswerHistorySerializer(many=True))
    def get_history(self, instance):
        answer_history = AnswerHistory.objects.filter(
            data=instance.data, question=instance.question
        ).all()
        history = []
        for h in answer_history:
            history.append(get_answer_history(h))
        return history if history else None

    @extend_schema_field(OpenApiTypes.ANY)
    def get_value(self, instance: Answers):
        return get_answer_value(instance)

    class Meta:
        model = Answers
        fields = ["history", "question", "value", "index"]


class FormDataSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()

    @extend_schema_field(ListDataAnswerSerializer(many=True))
    def get_answers(self, instance):
        return ListDataAnswerSerializer(
            instance=instance.data_answer.all(),
            many=True,
        ).data

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "name",
            "form",
            "administration",
            "geo",
            "created_by",
            "updated_by",
            "created",
            "updated",
            "submitter",
            "duration",
            "answers",
        ]


class ListPendingFormDataRequestSerializer(serializers.Serializer):
    search = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_from": "date_from must be before or equal to date_to"}
            )
        return attrs


class ListFormDataRequestSerializer(serializers.Serializer):
    SORT_BY_CHOICES = [
        ("created", "created"),
        ("updated", "updated"),
        ("name", "name"),
        ("total_children", "total_children"),
        ("latest_activity", "latest_activity"),
    ]
    SORT_TYPE_CHOICES = [
        ("ascend", "ascend"),
        ("descend", "descend"),
    ]

    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )
    parent = serializers.CharField(required=False)
    search = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    sort_by = serializers.ChoiceField(
        choices=SORT_BY_CHOICES, required=False, default="created"
    )
    sort_type = serializers.ChoiceField(
        choices=SORT_TYPE_CHOICES, required=False, default="descend"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get(
            "administration"
        ).queryset = Administration.objects.all()

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_from": "date_from must be before or equal to date_to"}
            )
        return attrs


class ListFormDataSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    updated = serializers.SerializerMethodField()
    latest_activity = serializers.SerializerMethodField()
    latest_activity_source = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()
    pending_data = serializers.SerializerMethodField()
    total_children = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by(self, instance: FormData):
        return instance.created_by.get_full_name()

    @extend_schema_field(OpenApiTypes.STR)
    def get_updated_by(self, instance: FormData):
        if instance.updated_by:
            return instance.updated_by.get_full_name()
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_created(self, instance: FormData):
        return update_date_time_format(instance.created)

    @extend_schema_field(OpenApiTypes.STR)
    def get_updated(self, instance: FormData):
        return update_date_time_format(instance.updated)

    @extend_schema_field(OpenApiTypes.STR)
    def get_latest_activity(self, instance: FormData):
        latest_activity = getattr(instance, "latest_activity", None)
        if latest_activity:
            return update_date_time_format(latest_activity)
        if instance.updated:
            return update_date_time_format(instance.updated)
        return update_date_time_format(instance.created)

    @extend_schema_field(OpenApiTypes.STR)
    def get_latest_activity_source(self, instance: FormData):
        return getattr(instance, "latest_activity_source", None)

    @extend_schema_field(
        inline_serializer(
            "HasPendingData",
            fields={
                "id": serializers.IntegerField(),
                "created_by": serializers.CharField(),
            },
        )
    )
    def get_pending_data(self, instance: FormData):
        pending_data = instance.children.filter(
            is_pending=True,
        ).first()
        if pending_data:
            return {
                "id": pending_data.id,
                "created_by": pending_data.created_by.get_full_name(),
            }
        return None

    def get_administration(self, instance: FormData):
        return " - ".join(instance.administration.full_name.split("-")[1:])

    @extend_schema_field(OpenApiTypes.INT)
    def get_total_children(self, instance: FormData):
        return getattr(instance, "total_children", 0)

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "name",
            "form",
            "administration",
            "geo",
            "created_by",
            "updated_by",
            "created",
            "updated",
            "latest_activity",
            "latest_activity_source",
            "pending_data",
            "submitter",
            "total_children",
        ]


class ListOptionsChartCriteriaSerializer(serializers.Serializer):
    question = CustomPrimaryKeyRelatedField(queryset=Questions.objects.none())
    option = CustomListField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("question").queryset = Questions.objects.all()


class ListPendingDataAnswerSerializer(serializers.ModelSerializer):
    history = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()
    last_value = serializers.SerializerMethodField()

    @extend_schema_field(AnswerHistorySerializer(many=True))
    def get_history(self, instance):
        answer_history = AnswerHistory.objects.filter(
            data=instance.data, question=instance.question
        ).all()
        history = []
        for h in answer_history:
            history.append(get_answer_history(h))
        return history if history else None

    @extend_schema_field(OpenApiTypes.ANY)
    def get_value(self, instance: Answers):
        return get_answer_value(instance)

    @extend_schema_field(OpenApiTypes.ANY)
    def get_last_value(self, instance: Answers):
        if self.context["last_data"]:
            parent_question = None
            if instance.question.form.parent:
                # If the question is from a parent form,
                # get the parent question from the parent form
                qg = instance.question.form.parent \
                    .form_question_group.filter(
                        name=instance.question.question_group.name
                    ).first()
                if qg:
                    parent_question = qg.question_group_question.filter(
                        name=instance.question.name
                    ).first()
            answer = (
                self.context["last_data"]
                .data_answer.filter(
                    Q(
                        question=instance.question,
                        index=instance.index,
                    ) |
                    Q(
                        question=parent_question,
                        index=instance.index,
                    )
                )
                .first()
            )
            if answer:
                return get_answer_value(answer=answer)
        return None

    class Meta:
        model = Answers
        fields = [
            "history",
            "question",
            "value",
            "last_value",
            "index",
        ]


class ParentFormDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormData
        fields = [
            "id",
            "name",
            "form",
            "is_pending",
        ]


class ListPendingFormDataSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    administration = serializers.ReadOnlyField(source="administration.name")
    answer_history = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by(self, instance: FormData):
        return instance.created_by.get_full_name()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created(self, instance: FormData):
        return update_date_time_format(instance.created)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_answer_history(self, instance: FormData):
        # Check for history in answer_history table
        history = AnswerHistory.objects.filter(
            data=instance
        ).count()
        return True if history > 0 else False

    @extend_schema_field(ParentFormDataSerializer)
    def get_parent(self, instance: FormData):
        if instance.parent:
            return ParentFormDataSerializer(instance=instance.parent).data
        if instance.form.parent and not instance.parent:
            return {
                "id": None,
                "name": None,
                "form": None,
                "is_pending": None,
            }
        return None

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "name",
            "form",
            "administration",
            "geo",
            "submitter",
            "duration",
            "created_by",
            "created",
            "answer_history",
            "parent",
        ]


class SubmitPendingFormSerializer(serializers.Serializer):
    data = SubmitFormDataSerializer()
    answer = SubmitFormDataAnswerSerializer(many=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def create(self, validated_data):
        data = validated_data.get("data")
        data["form"] = self.context.get("form")
        data["created_by"] = self.context.get("user")
        is_draft = self.context.get("is_draft", False)

        # Idempotency: a client that resends the same submission -- after a
        # killed process or a lost HTTP response -- must not create a second
        # row. Returning early also skips the answer loop below, so a replay
        # writes nothing at all.
        #
        # _base_manager, not objects: the default manager filters
        # deleted_at__isnull=True, but the unique index does not. A
        # soft-deleted row still owns its submission_key.
        submission_key = data.get("submission_key")
        if submission_key:
            existing = FormData._base_manager.filter(
                submission_key=submission_key
            ).first()
            if existing:
                return existing

        # check user role and form type
        user = self.context.get("user")
        is_super_admin = user.is_superuser

        direct_to_data = is_super_admin

        try:
            # The savepoint keeps a losing INSERT from poisoning an outer
            # transaction, so the recovery query below can still run. Without
            # it this breaks the moment ATOMIC_REQUESTS is turned on.
            with transaction.atomic():
                obj_data = self.fields.get("data").create(data)
        except IntegrityError:
            # Lost the race with a concurrent retry. The unique index is the
            # real guard; the lookup above can be passed by both racers.
            if not submission_key:
                raise
            return FormData._base_manager.get(submission_key=submission_key)
        # If the form is a child form, it should have a parent
        if data.get("uuid") and obj_data.form.parent:
            obj_data.uuid = data["uuid"]
            # find parent data by uuid and parent form
            parent_data = FormData.objects.filter(
                uuid=data["uuid"],
                form__parent__isnull=True,
            ).first()
            if parent_data:
                # if parent data exists, link the child data
                obj_data.parent = parent_data
                obj_data.geo = parent_data.geo
                obj_data.administration = parent_data.administration
            obj_data.save()

        if not direct_to_data and obj_data.has_approval:
            # If the form has approval
            obj_data.is_pending = True
            obj_data.save()

        if is_draft:
            # Mark as draft
            obj_data.mark_as_draft()
            direct_to_data = False

        answers = []

        for answer in validated_data.get("answer"):
            question = answer.get("question")
            name = None
            value = None
            option = None

            if question.type in [
                QuestionTypes.geo,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]:
                option = answer.get("value")
            elif question.type in [
                QuestionTypes.input,
                QuestionTypes.text,
                QuestionTypes.image,
                QuestionTypes.date,
                QuestionTypes.autofield,
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            elif question.type == QuestionTypes.cascade:
                id = answer.get("value")
                extra_type = (question.extra or {}).get("type")
                q_api = question.api or {}
                ep = q_api.get("endpoint", "")
                val = None
                if "organisation" in ep:
                    val = Organisation.objects.filter(pk=id).values_list(
                        'name', flat=True).first()
                elif "entity-data" in ep or extra_type == "entity":
                    val = EntityData.objects.filter(pk=id).values_list(
                        'name', flat=True).first()
                else:
                    # administration cascade: store both name and integer value
                    val = Administration.objects.filter(pk=id).values_list(
                        'name', flat=True).first()
                    value = id
                name = val
            else:
                # for number question type
                value = answer.get("value")

            answers.append(Answers(
                data=obj_data,
                question=question,
                name=name,
                value=value,
                options=option,
                created_by=self.context.get("user"),
                index=answer.get("index", 0)
            ))

        Answers.objects.bulk_create(answers)

        if (
            not is_draft and
            not obj_data.is_pending
        ):
            # Refresh materialized view via async task
            async_task("api.v1.v1_data.tasks.seed_approved_data", obj_data)

        return obj_data

    def represent(self, instance, validated_data):
        """
        Represent the instance in a way that can be used in the response.
        This method is called after the create method.
        """
        data = {
            "id": instance.id,
            "uuid": instance.uuid,
            "name": instance.name,
            "form": instance.form.id,
            "administration": instance.administration.id,
            "geo": instance.geo,
            "is_pending": instance.is_pending,
            "is_draft": instance.is_draft,
        }
        if instance.parent:
            data["parent"] = {
                "id": instance.parent.id,
                "name": instance.parent.name,
                "form": instance.parent.form.id,
            }
        return data

    class Meta:
        fields = ["data", "answer"]


class SubmitUpdateDraftFormSerializer(SubmitPendingFormSerializer):
    """
    Serializer for updating existing draft form data.
    """

    def update(self, instance, validated_data):
        data = validated_data.get("data")
        if not instance.parent:
            # If the instance is a parent form, update its fields
            admin_id = data.get("administration", instance.administration_id)
            instance.administration_id = admin_id
            instance.geo = data.get("geo", instance.geo)
        instance.name = data.get("name", instance.name)
        instance.updated = timezone.now()
        instance.updated_by = self.context.get("user")
        instance.submitter = data.get("submitter", instance.submitter)
        instance.duration = data.get("duration", instance.duration)
        instance.save()

        # Clear existing answers and create new ones
        instance.data_answer.all().delete()

        answers = []
        for answer in validated_data.get("answer"):
            question = answer.get("question")
            name = None
            value = None
            option = None

            if question.type in [
                QuestionTypes.geo,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]:
                option = answer.get("value")
            elif question.type in [
                QuestionTypes.input,
                QuestionTypes.text,
                QuestionTypes.image,
                QuestionTypes.date,
                QuestionTypes.autofield,
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            elif question.type == QuestionTypes.cascade:
                id = answer.get("value")
                extra_type = (question.extra or {}).get("type")
                q_api = question.api or {}
                ep = q_api.get("endpoint", "")
                val = None
                if "organisation" in ep:
                    val = Organisation.objects.filter(pk=id).values_list(
                        'name', flat=True).first()
                elif "entity-data" in ep or extra_type == "entity":
                    val = EntityData.objects.filter(pk=id).values_list(
                        'name', flat=True).first()
                else:
                    # administration cascade: store both name and integer value
                    val = Administration.objects.filter(pk=id).values_list(
                        'name', flat=True).first()
                    value = id
                name = val
            else:
                # for number question type
                value = answer.get("value")

            answers.append(Answers(
                data=instance,
                question=question,
                name=name,
                value=value,
                options=option,
                created_by=self.context.get("user"),
                index=answer.get("index", 0)
            ))

        Answers.objects.bulk_create(answers)
        return instance


class FilterDraftFormDataSerializer(serializers.Serializer):
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )
    page = CustomIntegerField(
        required=False,
        allow_null=True,
        default=1,
        min_value=1,
        help_text="Page number for pagination",
    )
    search = CustomCharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=225,
        help_text="Search by name",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get(
            "administration"
        ).queryset = Administration.objects.all()

    class Meta:
        fields = ["administration", "page", "search"]


class DraftFormDataDetailSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()
    datapoint_name = CustomCharField(source="name")
    geolocation = CustomListField(
        source="geo",
        required=False,
        allow_null=True
    )

    @extend_schema_field(OpenApiTypes.ANY)
    def get_answers(self, instance):
        data_answers = instance.data_answer.all()
        answers = {}
        for a in data_answers:
            answers.update(a.to_key)
        return answers

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "form",
            "administration",
            "datapoint_name",
            "geolocation",
            "answers",
        ]
