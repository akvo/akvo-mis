from mis.settings import WEBDOMAIN
from .serializers import (
    UploadImagesSerializer,
    AttachmentsSerializer,
)
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiParameter,
)
from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .functions import handle_upload
from utils.custom_serializer_fields import validate_serializers_message


@extend_schema(
    tags=["Files"],
    summary="Upload Images",
    request=UploadImagesSerializer,
    responses={
        (200, "application/json"): inline_serializer(
            "UploadImages", fields={"task_id": serializers.CharField()}
        )
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_images(request, version):
    serializer = UploadImagesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            validate_serializers_message(serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )
    filename = handle_upload(request=request, folder="images")
    return Response(
        {
            "message": "File uploaded successfully",
            "file": f"{WEBDOMAIN}/images/{filename}",
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Files"],
    summary="Upload Logo",
    request=UploadImagesSerializer,
    responses={
        (200, "application/json"): inline_serializer(
            "UploadLogo",
            fields={
                "message": serializers.CharField(),
                "file": serializers.CharField(),
            },
        )
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_logo(request, version):
    is_super = getattr(request.user, "is_superuser", False)
    is_plat = getattr(request.user, "is_platform_admin", False)
    if not (is_super or is_plat):
        return Response(
            {"message": "Only Super Admin can upload logo."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = UploadImagesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            validate_serializers_message(serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )
    filename = handle_upload(request=request, folder="logo")
    return Response(
        {
            "message": "File uploaded successfully",
            "file": f"{WEBDOMAIN}/logo/{filename}",
        },
        status=status.HTTP_200_OK,
    )


class UploadAttachmentsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Files"],
        summary="Upload Attachments",
        request=AttachmentsSerializer,
        responses={
            (200, "application/json"): inline_serializer(
                "UploadAttachments",
                fields={
                    "message": serializers.CharField(),
                    "file": serializers.CharField(),
                },
            )
        },
        # add parameter allowed_file_types
        parameters=[
            OpenApiParameter(
                name="allowed_file_types",
                required=False,
                location=OpenApiParameter.QUERY,
                description=(
                    "List of allowed file types for the attachment. "
                ),
                type={"type": "array", "items": {"type": "string"}},
                enum=[
                    "pdf",
                    "docx",
                    "xlsx",
                    "pptx",
                    "txt",
                    "csv",
                    "zip",
                    "rar",
                    "jpg",
                    "jpeg",
                    "png",
                    "gif",
                    "bmp",
                    "doc",
                    "xls",
                    "ppt",
                    "mp4",
                    "avi",
                    "mov",
                    "mkv",
                    "flv",
                    "wmv",
                    "mp3",
                    "wav",
                    "ogg",
                    "flac",
                    "aac",
                    "wma",
                    "m4a",
                    "opus",
                    "webm",
                    "3gp",
                ],
            ),
            OpenApiParameter(
                name="question_id",
                required=False,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
        ],
        description="Upload attachments to the server.",
    )
    def post(self, request, version):
        # Get the allowed file types from the query parameter
        allowed_file_types = request.query_params.getlist("allowed_file_types")
        question_id = request.query_params.get("question_id")
        serializer = AttachmentsSerializer(
            data=request.data,
            context={
                "allowed_file_types": allowed_file_types,
            },
        )
        if not serializer.is_valid():
            return Response(
                validate_serializers_message(serializer.errors),
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            filename = handle_upload(request=request, folder="attachments")
            if not question_id:
                return Response(
                    {
                        "message": "File uploaded successfully",
                        "file": f"{WEBDOMAIN}/attachments/{filename}",
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(
                {
                    "message": "File uploaded successfully",
                    "file": f"{WEBDOMAIN}/attachments/{filename}",
                    "question_id": question_id,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "message": "File upload failed",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
