# Create your views here.
import re

from wsgiref.util import FileWrapper

from uuid import uuid4
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.http import HttpResponse
from django.utils import timezone
from django_q.tasks import async_task
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    inline_serializer,
)
from rest_framework import status, serializers
from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.fields import ChoiceField

from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.constants import JobStatus, JobTypes, DataDownloadTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.serializers import (
    DownloadDataRequestSerializer,
    DownloadListSerializer,
    UploadExcelSerializer,
    FormDataReportSerializer,
)
from api.v1.v1_profile.models import Administration
from utils import storage
from utils.custom_serializer_fields import validate_serializers_message


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="administration_id",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="form_id",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="type",
            required=False,
            type=OpenApiTypes.STR,
            enum=DataDownloadTypes.FieldStr.values(),
            default=DataDownloadTypes.recent,
        ),
        OpenApiParameter(
            name="use_label",
            required=False,
            type=OpenApiTypes.BOOL,
            default=False,
        ),
        OpenApiParameter(
            name="child_form_ids",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="date_from",
            required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="date_to",
            required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="selection_ids",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
            description="Registration FormData IDs to download",
        ),
    ],
    responses={
        (200, "application/json"): inline_serializer(
            "GenerateDownload",
            fields={
                "task_id": serializers.CharField(),
                "file_url": serializers.CharField(),
            },
        )
    },
    tags=["Job"],
    summary="To generate download",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_generate(request, version):
    serializer = DownloadDataRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    administration = serializer.validated_data.get("administration_id")
    child_forms = [
        child.id
        for child in serializer.validated_data.get("child_form_ids", [])
    ]
    selection_ids = [
        fd.id
        for fd in serializer.validated_data.get("selection_ids", [])
    ]
    cmd_args = [
        "job_download",
        serializer.validated_data.get("form_id").id,
        request.user.id,
        "-a",
        administration.id if administration else 0,
        "-t",
        serializer.validated_data.get("type"),
        "-l",
        1 if serializer.validated_data.get("use_label") else 0,
        "-c",
        *child_forms,
    ]
    if selection_ids:
        cmd_args.extend(["-s", *selection_ids])
    date_from = serializer.validated_data.get("date_from")
    date_to = serializer.validated_data.get("date_to")
    if date_from:
        cmd_args.extend(["-df", str(date_from)])
    if date_to:
        cmd_args.extend(["-dt", str(date_to)])
    result = call_command(*cmd_args)
    job = Jobs.objects.get(pk=result)
    data = {
        "task_id": job.task_id,
        "file_url": "/download/file/{0}".format(job.result),
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    description="To get the status of download",
    tags=["Job"],
    responses={
        (200, "application/json"): inline_serializer(
            "DownloadStatus",
            fields={
                "status": ChoiceField(
                    choices=[JobStatus.FieldStr[d] for d in JobStatus.FieldStr]
                )
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_status(request, version, task_id):
    job = get_object_or_404(Jobs, task_id=task_id)
    return Response(
        {"status": JobStatus.FieldStr.get(job.status)},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Job"],
    summary="Download file",
    parameters=[
        OpenApiParameter(
            name="type",
            required=True,
            enum=JobTypes.FieldStr.values(),
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_file(request, version, file_name):
    job = get_object_or_404(Jobs, result=file_name)
    type = request.GET.get("type") if request.GET.get("type") else "download"
    url = f"{type}/{job.result}"
    filepath = storage.download(url)
    filename = job.result
    zip_file = open(filepath, "rb")
    # Set content type based on file extension
    if filename.endswith('.zip'):
        content_type = "application/zip"
    elif filename.endswith('.docx'):
        content_type = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
    else:
        content_type = (
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        )
    response = HttpResponse(FileWrapper(zip_file), content_type=content_type)
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    return response


@extend_schema(
    tags=["Job"],
    summary="Download list",
    responses=DownloadListSerializer(many=True),
    parameters=[
        OpenApiParameter(
            name="page",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="type",
            required=False,
            enum=JobTypes.FieldStr.values(),
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_list(request, version):
    job_types = [
        JobTypes.download,
        JobTypes.download_administration,
        JobTypes.download_entities,
        JobTypes.download_datapoint_report,
    ]
    if request.GET.get("type"):
        job_types = [getattr(JobTypes, request.GET.get("type"))]
    queryset = request.user.user_jobs.filter(type__in=job_types).order_by(
        "-created"
    )
    paginator = PageNumberPagination()
    paginator.page_size = 5
    try:
        instance = paginator.paginate_queryset(queryset, request)
        return Response(
            DownloadListSerializer(instance=instance, many=True).data,
            status=status.HTTP_200_OK,
        )
    except NotFound:
        return Response([], status=status.HTTP_200_OK)


@extend_schema(
    tags=["Job"],
    summary="Upload Excel",
    request=UploadExcelSerializer,
    responses={
        (200, "application/json"): inline_serializer(
            "UploadExcel", fields={"task_id": serializers.CharField()}
        )
    },
)
@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_excel(request, form_id, version):
    form = get_object_or_404(Forms, pk=form_id)
    serializer = UploadExcelSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    is_update = serializer.validated_data.get("is_update")
    fs = FileSystemStorage()
    file = fs.save(
        f"./tmp/{serializer.validated_data.get('file').name}",
        serializer.validated_data.get("file"),
    )
    file_path = fs.path(file)
    # filename format: form_name--user_name-<4_digit_autogerated>
    uuid = "_".join(str(uuid4()).split("-")[:-1])
    user_name = "{0}_{1}".format(
        request.user.first_name, request.user.last_name
    )
    form_name = re.sub(r"[\W_]+", "_", form.name)
    filename = f"{form_name}-{user_name}-{uuid}.xlsx"
    storage.upload(file=file_path, filename=filename, folder="upload")
    adm = Administration.objects.for_user(request.user).filter(
        parent__isnull=True
    ).first()
    if (
        not request.user.is_superuser and
        request.user.user_user_role.count()
    ):
        adm = request.user.user_user_role.first().administration
    job = Jobs.objects.create(
        type=JobTypes.validate_data,
        status=JobStatus.on_progress,
        user=request.user,
        info={
            "file": filename,
            "form": form_id,
            "administration": adm.id,
            "is_update": is_update,
        },
    )
    task_id = async_task(
        "api.v1.v1_jobs.job.validate_excel",
        job.id,
        hook="api.v1.v1_jobs.job.validate_excel_result",
    )
    job.task_id = task_id
    job.save()

    return Response({"task_id": task_id}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Job"],
    summary="Bulk Upload Administrations",
    request=UploadExcelSerializer,
    responses={
        (200, "application/json"): inline_serializer(
            "UploadExcel",
            fields={
                "task_id": serializers.CharField(),
                "filename": serializers.CharField(),
            },
        )
    },
)
@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_bulk_administrators(request, version):
    serializer = UploadExcelSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    fs = FileSystemStorage()
    file = fs.save(
        f"./tmp/{serializer.validated_data.get('file').name}",
        serializer.validated_data.get("file"),
    )
    file_path = fs.path(file)
    uuid = "_".join(str(uuid4()).split("-")[:-1])
    filename = f"administration-bulk-upload-{request.user.id}-{uuid}.xlsx"
    storage.upload(file=file_path, filename=filename, folder="upload")
    task_id = async_task(
        "api.v1.v1_jobs.job.handle_administrations_bulk_upload",
        filename,
        request.user.id,
        timezone.now(),
        task_name="administrator_bulk_upload",
        hook=("api.v1.v1_jobs.job." "handle_master_data_bulk_upload_failure"),
    )
    return Response(
        {
            "task_id": task_id,
            "filename": filename,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Job"],
    summary="Bulk Upload Entities",
    request=UploadExcelSerializer,
    responses={
        (200, "application/json"): inline_serializer(
            "UploadExcel",
            fields={
                "task_id": serializers.CharField(),
                "filename": serializers.CharField(),
            },
        )
    },
)
@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_bulk_entities(request, version):
    serializer = UploadExcelSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    fs = FileSystemStorage()
    file = fs.save(
        f"./tmp/{serializer.validated_data.get('file').name}",
        serializer.validated_data.get("file"),
    )
    file_path = fs.path(file)
    uuid = "_".join(str(uuid4()).split("-")[:-1])
    filename = f"entities-bulk-upload-{request.user.id}-{uuid}.xlsx"
    storage.upload(file=file_path, filename=filename, folder="upload")
    task_id = async_task(
        "api.v1.v1_jobs.job.handle_entities_bulk_upload",
        filename,
        request.user.id,
        timezone.now(),
        task_name="entities_bulk_upload",
        hook=("api.v1.v1_jobs.job." "handle_master_data_bulk_upload_failure"),
    )
    return Response(
        {
            "task_id": task_id,
            "filename": filename,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Job"],
    summary="Generate Datapoint Report",
    parameters=[
        OpenApiParameter(
            name="form_id",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="child_form_ids",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="selection_ids",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        (200, "application/json"): inline_serializer(
            "DatapointReport",
            fields={
                "task_id": serializers.CharField(),
                "file_url": serializers.CharField(),
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_data_report(request, version):
    serializer = FormDataReportSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    form = serializer.validated_data.get("form_id")
    datapoints = serializer.validated_data.get("selection_ids")

    # Convert datapoints to list of IDs if provided
    selection_ids = [dp.id for dp in datapoints] if datapoints else []
    child_forms = [
        child.id
        for child in serializer.validated_data.get("child_form_ids", [])
    ]
    result = call_command(
        "job_data_report",
        form.id,
        request.user.id,
        "-s",
        *selection_ids,
        "-c",
        *child_forms,
    )
    job = Jobs.objects.get(pk=result)
    data = {
        "task_id": job.task_id,
        "file_url": "/download/file/{0}?type=download_datapoint_report".format(
            job.result
        ),
    }
    return Response(data, status=status.HTTP_200_OK)
