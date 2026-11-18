import io
import tempfile
from uuid import uuid4

import openpyxl

from django.db import transaction
from django.http import Http404, HttpResponse
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
        "blocked": onboarding.blocked,
        "report": onboarding.report,
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
    # shortcut: unpaginated; drafts are capped per tenant per day, so the
    # history stays small. Paginate if it grows past a few hundred rows.
    return Response([
        {
            "id": o.id,
            "status": DataOnboardingStatus.FieldStr[o.status],
            "file_name": o.file_name,
            "created": o.created,
            "updated": o.updated,
            "created_by": o.created_by.get_full_name(),
        }
        for o in DataOnboarding.objects.for_user(request.user)
        .select_related("created_by").order_by("-created", "-id")
    ])


@extend_schema(tags=["Data Onboarding"], summary="Get a Data Onboarding")
@api_view(["GET"])
@permission_classes([IsAuthenticated, DataOnboardingAccess])
def data_onboarding_detail(request, version, pk):
    onboarding = get_object_or_404(
        DataOnboarding.objects.for_user(request.user), pk=pk
    )
    return Response(_detail(onboarding))


def _chosen_forms(onboarding, chosen):
    """(form keys to apply, error): all unblocked forms when not given."""
    blocked = {b["form"] for b in onboarding.blocked or []}
    forms = onboarding.proposal["forms"]
    ready = [f["key"] for f in forms if f["key"] not in blocked]
    if chosen is None:
        chosen = ready
    if not isinstance(chosen, list) or \
            not all(isinstance(k, str) and k in ready for k in chosen):
        return None, "Only unblocked forms of this Proposal can be applied."
    if not chosen:
        return None, "There is no unblocked form to apply."
    for f in forms:
        if f["key"] in chosen and f["parent"] and f["parent"] not in chosen:
            return None, (
                f"Form '{f['name']}' needs its registration form applied"
                " with it."
            )
    return chosen, None


@extend_schema(tags=["Data Onboarding"], summary="Apply the Proposal")
@api_view(["POST"])
@permission_classes([IsAuthenticated, DataOnboardingAccess])
def data_onboarding_apply(request, version, pk):
    with transaction.atomic():
        onboarding = get_object_or_404(
            DataOnboarding.objects.for_user(request.user)
            .select_for_update(),
            pk=pk,
        )
        if onboarding.status != DataOnboardingStatus.proposed:
            return Response(
                {"message": "Only a proposed Data Onboarding can be applied."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        forms, error = _chosen_forms(onboarding, request.data.get("forms"))
        if error:
            return Response(
                {"message": error}, status=status.HTTP_400_BAD_REQUEST
            )
        onboarding.status = DataOnboardingStatus.applying
        onboarding.save()
        transaction.on_commit(lambda: async_task(
            "api.v1.v1_data_onboarding.tasks.apply_onboarding",
            onboarding.id,
            forms=forms,
            hook="api.v1.v1_data_onboarding.tasks.apply_onboarding_result",
        ))
    return Response(_detail(onboarding))


@extend_schema(
    tags=["Data Onboarding"], summary="Download the Onboarding Report"
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, DataOnboardingAccess])
def data_onboarding_report(request, version, pk):
    onboarding = get_object_or_404(
        DataOnboarding.objects.for_user(request.user), pk=pk
    )
    report = onboarding.report
    if not report:
        raise Http404
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Onboarding Report"
    ws.append(["Form", "Records loaded"])
    for form in report["forms"]:
        ws.append([form["name"], form["loaded"]])
    ws.append([])
    ws.append(["Sheet", "Row", "Question", "Outcome", "Reason"])
    for issue in report["issues"]:
        ws.append([
            issue["sheet"], issue["row"], issue["question"],
            "Row skipped" if issue["kind"] == "skipped" else "Answer dropped",
            issue["reason"],
        ])
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # noqa
    )
    resp["Content-Disposition"] = (
        f'attachment; filename="onboarding-report-{onboarding.id}.xlsx"'
    )
    resp["Access-Control-Expose-Headers"] = "Content-Disposition"
    return resp
