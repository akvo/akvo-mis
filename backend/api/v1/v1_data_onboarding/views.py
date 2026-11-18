import tempfile
from uuid import uuid4

from django.shortcuts import get_object_or_404
from django_q.tasks import async_task
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_data_onboarding.constants import DataOnboardingStatus
from api.v1.v1_data_onboarding.models import DataOnboarding
from api.v1.v1_data_onboarding.profile import (
    MAX_FILE_SIZE,
    OnboardingError,
    check_rows,
    extension,
    read_sheets,
)
from utils import storage
from utils.custom_permissions import DataOnboardingAccess


def _detail(onboarding):
    return {
        "id": onboarding.id,
        "status": DataOnboardingStatus.FieldStr[onboarding.status],
        "file_name": onboarding.file_name,
        "proposal": onboarding.proposal,
        "error": onboarding.error,
        "created": onboarding.created,
        "created_by": onboarding.created_by.get_full_name(),
    }


def _create(request):
    file_obj = request.FILES.get("file")
    if not file_obj:
        return Response(
            {"message": "file is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ext = extension(file_obj.name)
    try:
        if ext not in ("csv", "xlsx"):
            raise OnboardingError("Upload a CSV or xlsx file.")
        if file_obj.size > MAX_FILE_SIZE:
            raise OnboardingError("The file is over 10 MB. Trim it and retry.")
        with tempfile.NamedTemporaryFile(suffix=f".{ext}") as tmp:
            for chunk in file_obj.chunks():
                tmp.write(chunk)
            tmp.flush()
            check_rows(read_sheets(tmp.name, file_obj.name))
            filename = f"{uuid4().hex}.{ext}"
            storage.upload(
                file=tmp.name, folder="data_onboarding", filename=filename
            )
    except OnboardingError as exc:
        return Response(
            {"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST
        )
    onboarding = DataOnboarding.objects.create(
        tenant=request.user.tenant,
        created_by=request.user,
        file=f"data_onboarding/{filename}",
        file_name=file_obj.name,
    )
    async_task(
        "api.v1.v1_data_onboarding.tasks.draft_proposal",
        onboarding.id,
        hook="api.v1.v1_data_onboarding.tasks.draft_proposal_result",
    )
    return Response(_detail(onboarding), status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Data Onboarding"],
    summary="List Data Onboardings, or upload a spreadsheet to draft one",
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, DataOnboardingAccess])
def data_onboarding_list(request, version):
    if request.method == "POST":
        return _create(request)
    # The list itself lands with the report history.
    return Response([])


@extend_schema(tags=["Data Onboarding"], summary="Get a Data Onboarding")
@api_view(["GET"])
@permission_classes([IsAuthenticated, DataOnboardingAccess])
def data_onboarding_detail(request, version, pk):
    onboarding = get_object_or_404(
        DataOnboarding.objects.for_user(request.user), pk=pk
    )
    return Response(_detail(onboarding))
