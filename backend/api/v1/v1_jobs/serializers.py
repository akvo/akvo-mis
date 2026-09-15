from django.core.validators import FileExtensionValidator
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.constants import JobTypes, JobStatus, DataDownloadTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_profile.models import Administration, AdministrationAttribute
from api.v1.v1_data.models import FormData
from utils.custom_serializer_fields import (
    CustomFileField,
    CustomChoiceField,
    CustomListField,
    TenantScopedPrimaryKeyRelatedField,
)


class DownloadDataRequestSerializer(serializers.Serializer):
    form_id = TenantScopedPrimaryKeyRelatedField(queryset=Forms.objects.none())
    administration_id = TenantScopedPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )
    type = CustomChoiceField(
        choices=[
            DataDownloadTypes.FieldStr[d] for d in DataDownloadTypes.FieldStr
        ],
        required=False,
    )
    use_label = serializers.BooleanField(required=False)
    child_form_ids = CustomListField(
        child=TenantScopedPrimaryKeyRelatedField(
            queryset=Forms.objects.none()
        ),
        required=False,
    )
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    selection_ids = CustomListField(
        child=TenantScopedPrimaryKeyRelatedField(
            queryset=FormData.objects.none()
        ),
        required=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("form_id").queryset = Forms.objects.all()
        self.fields.get(
            "administration_id"
        ).queryset = Administration.objects.all()
        self.fields.get("child_form_ids").child.queryset = Forms.objects.all()
        self.fields.get(
            "selection_ids"
        ).child.queryset = FormData.objects.filter(
            form__parent__isnull=True
        ).all()

    def validate(self, data):
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "date_from must be before or equal to date_to"
            )
        selection_ids = data.get("selection_ids", [])
        form_id = data.get("form_id")
        if selection_ids and form_id:
            invalid = [
                fd for fd in selection_ids if fd.form_id != form_id.id
            ]
            if invalid:
                raise serializers.ValidationError(
                    "selection_ids must belong to the requested form_id"
                )
        return data


class DownloadListSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()
    date = serializers.DateTimeField(
        source="available", format="%B %d, %Y %I:%M %p"
    )
    form = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()
    download_type = serializers.SerializerMethodField()

    @extend_schema_field(
        CustomChoiceField(
            choices=[JobTypes.FieldStr[d] for d in JobTypes.FieldStr]
        )
    )
    def get_category(self, instance):
        job_type = JobTypes.FieldStr.get(instance.type)
        if job_type == "download_administration":
            return "Administration List"
        if job_type == "download_entities":
            return "Entities"
        if job_type == "download_datapoint_report":
            return "Data Report"
        return "Form Data"

    @extend_schema_field(
        CustomChoiceField(
            choices=[JobStatus.FieldStr[d] for d in JobStatus.FieldStr]
        )
    )
    def get_status(self, instance):
        return JobStatus.FieldStr.get(instance.status)

    @extend_schema_field(OpenApiTypes.STR)
    def get_administration(self, instance):
        admin_id = instance.info.get("administration") or instance.info.get(
            "adm_id"
        )
        if admin_id:
            adm = Administration.objects.filter(pk=admin_id).first()
            if adm:
                return adm.full_name
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_form(self, instance):
        form_id = instance.info.get("form_id")
        if form_id:
            return Forms.objects.get(pk=form_id).name
        return None

    @extend_schema_field(
        CustomChoiceField(
            choices=[JobTypes.FieldStr[d] for d in JobTypes.FieldStr]
        )
    )
    def get_type(self, instance):
        return JobTypes.FieldStr.get(instance.type)

    @extend_schema_field(OpenApiTypes.ANY)
    def get_attributes(self, instance):
        if instance.type == JobTypes.download_entities:
            return instance.info.get("entities")
        if instance.type == JobTypes.download_administration:
            attributes = AdministrationAttribute.objects.filter(
                pk__in=instance.info.get("attributes")
            ).values("id", "name")
            attributes = [a for a in attributes]
            return attributes
        if instance.type == JobTypes.download_datapoint_report:
            selection_ids = instance.info.get("selection_ids", [])
            form_id = instance.info.get("form_id")
            if selection_ids:
                fd = FormData.objects.filter(
                    pk__in=selection_ids,
                    form_id=form_id,
                ).values("id", "name", "form_id")
                return list(fd)
        if instance.type == JobTypes.download:
            selection_ids = instance.info.get("selection_ids", [])
            form_id = instance.info.get("form_id")
            if selection_ids:
                fd = FormData.objects.filter(
                    pk__in=selection_ids,
                    form_id=form_id,
                ).values("id", "name", "form_id")
                return list(fd)
            items = []
            child_form_ids = instance.info.get("child_form_ids")
            if child_form_ids:
                forms = Forms.objects.filter(
                    pk__in=child_form_ids
                ).values("id", "name")
                items.extend(list(forms))
            return items

        return instance.info.get("attributes")

    @extend_schema_field(OpenApiTypes.STR)
    def get_download_type(self, instance):
        if instance.info.get("selection_ids"):
            return None
        return instance.info.get("download_type")

    class Meta:
        model = Jobs
        fields = [
            "id",
            "task_id",
            "type",
            "status",
            "form",
            "category",
            "administration",
            "date",
            "result",
            "attributes",
            "download_type",
        ]


class UploadExcelSerializer(serializers.Serializer):
    file = CustomFileField(validators=[FileExtensionValidator(["xlsx"])])
    is_update = serializers.BooleanField(default=False)


class FormDataReportSerializer(serializers.Serializer):
    form_id = TenantScopedPrimaryKeyRelatedField(queryset=Forms.objects.none())
    child_form_ids = CustomListField(
        child=TenantScopedPrimaryKeyRelatedField(
            queryset=Forms.objects.none()
        ),
        required=False,
    )
    selection_ids = CustomListField(
        child=TenantScopedPrimaryKeyRelatedField(
            queryset=FormData.objects.none()
        ),
        required=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("form_id").queryset = Forms.objects.filter(
            parent__isnull=True
        ).all()
        self.fields.get("child_form_ids").child.queryset = Forms.objects.all()
        selection_ids_field = self.fields.get("selection_ids")
        selection_ids_field.child.queryset = FormData.objects.all()
