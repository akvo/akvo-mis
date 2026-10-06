from django.core.validators import FileExtensionValidator
from rest_framework import serializers
from utils.custom_serializer_fields import CustomFileField


class UploadImagesSerializer(serializers.Serializer):
    file = CustomFileField(
        validators=[
            FileExtensionValidator(["jpg", "png", "jpeg", "svg"])
        ]
    )


class AttachmentsSerializer(serializers.Serializer):
    file = CustomFileField(
        allow_empty_file=False,
        required=True,
    )

    def validate_file(self, value):
        allowed_file_types = self.context.get("allowed_file_types", [])
        # Skip validation if no allowed file types are provided
        if not allowed_file_types:
            return value
        """
        Validate the file extension against the allowed file types
        provided in the context.
        If the file type is not allowed, raise a ValidationError.
        The allowed file types should be a list of strings.
        Example: ["pdf", "docx", "doc"]
        The file extension should be in lowercase.
        """
        validator = FileExtensionValidator(allowed_file_types)
        try:
            validator(value)
            return value
        except serializers.ValidationError as e:
            raise serializers.ValidationError(
                f"File type not allowed. {str(e)}"
            )

    class Meta:
        fields = ["file"]
