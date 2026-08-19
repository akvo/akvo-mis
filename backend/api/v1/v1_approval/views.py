from math import ceil
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiParameter,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q
# from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_approval.models import (
    DataBatch,
    DataBatchAttachments,
)
from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_approval.serializers import (
    ApproveDataRequestSerializer,
    ListBatchSerializer,
    CreateBatchSerializer,
    ListDataBatchSerializer,
    ListPendingFormDataSerializer,
    BatchDataFilterSerializer,
    ListBatchSummarySerializer,
    ListBatchCommentSerializer,
    BatchListRequestSerializer,
    BatchAttachmentsSerializer,
)
from api.v1.v1_forms.constants import (
    QuestionTypes
)
from api.v1.v1_forms.models import Questions
from api.v1.v1_users.models import SystemUser
from api.v1.v1_data.models import Answers, FormData
from mis.settings import REST_FRAMEWORK
from utils.custom_permissions import (
    IsSuperAdmin,
    IsSubmitter,
    IsApprover,
)
from api.v1.v1_profile.constants import DataAccessTypes
from utils.custom_serializer_fields import validate_serializers_message
from utils.default_serializers import DefaultResponseSerializer

period_length = 60 * 15


def batch_for(request, batch_id):
    """The batch behind a URL id, or 404 if it is not the caller's.

    Every batch endpoint takes an id straight from the URL and those ids are
    sequential, so the ownership question has to be asked in one place rather
    than remembered at five call sites.
    """
    return get_object_or_404(
        DataBatch.objects.for_user(request.user), pk=batch_id
    )


@extend_schema(
    responses={
        (200, "application/json"): inline_serializer(
            "DataBatchResponse",
            fields={
                "current": serializers.IntegerField(),
                "total": serializers.IntegerField(),
                "total_page": serializers.IntegerField(),
                "batch": ListDataBatchSerializer(many=True),
            },
        )
    },
    tags=["Pending Data"],
    parameters=[
        OpenApiParameter(
            name="page",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="approved",
            required=False,
            default=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="subordinate",
            required=False,
            default=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
    ],
    summary="To get list of pending batch",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsApprover])
def list_pending_batch(request, version):
    serializer = BatchDataFilterSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user: SystemUser = request.user
    page_size = REST_FRAMEWORK.get("PAGE_SIZE")

    subordinate = serializer.validated_data.get("subordinate")
    approved = serializer.validated_data.get("approved")
    approval_status = DataApprovalStatus.pending
    if approved:
        approval_status = DataApprovalStatus.approved
    role_approver = user.user_user_role.filter(
        role__role_role_access__data_access=DataAccessTypes.approve
    )
    # Base query to get batches for the current user
    queryset = DataBatch.objects.filter(
        batch_approval__user=user,
        batch_approval__status=approval_status,
    ).order_by("-id")

    # Get my administration levels
    my_levels = role_approver.values_list(
        'administration__level__level', flat=True
    ).distinct()

    if role_approver.exists() and not approved and not subordinate:
        # For higher level administrators, implement level checking
        # Get all batch IDs that should be visible
        valid_batch_ids = []
        for batch in queryset:
            # For each batch, check if all lower levels have approved
            batch_levels = batch.batch_approval.values_list(
                'administration__level__level', flat=True
            ).distinct().order_by('administration__level__level')
            # Check if this batch should be visible
            is_valid = True
            for my_level in my_levels:
                for batch_level in batch_levels:
                    # If there's a lower level than mine in this batch
                    if batch_level > my_level:
                        # Check if that lower level has approved this batch
                        has_lower_approval = batch.batch_approval.filter(
                            administration__level__level=batch_level,
                            status=DataApprovalStatus.approved
                        ).exists()
                        if not has_lower_approval:
                            is_valid = False
                            break
                if not is_valid:
                    break
            if is_valid:
                # Exclude if a peer at the user's same Administration for THIS
                # batch has already approved (OR semantics per level).
                # DataApproval records are not mutated — filtering only.
                user_approval = batch.batch_approval.filter(
                    user=user
                ).first()
                if user_approval and batch.batch_approval.filter(
                    administration=user_approval.administration,
                    status=DataApprovalStatus.approved,
                ).exclude(user=user).exists():
                    is_valid = False
            if is_valid:
                valid_batch_ids.append(batch.id)
        # Set unique valid batch IDs
        valid_batch_ids = set(valid_batch_ids)
        # Filter queryset to only include valid batches
        queryset = queryset.filter(id__in=valid_batch_ids)
    if subordinate:
        adm_level = Q()
        for level in my_levels:
            adm_level |= Q(
                batch_approval__administration__level__level=level + 1,
                batch_approval__status=DataApprovalStatus.pending,
            )
        batch_ids = DataBatch.objects.filter(
            batch_approval__user=user,
        ).values_list("id", flat=True)
        queryset = DataBatch.objects.filter(
            adm_level,
            id__in=batch_ids,
            approved=approved,
        )
    queryset = queryset.distinct().order_by("-id")
    paginator = PageNumberPagination()
    paginator.paginate_queryset(queryset, request)
    total = queryset.count()

    data = {
        "current": int(request.GET.get("page", "1")),
        "total": total,
        "total_page": ceil(total / page_size),
        "batch": ListDataBatchSerializer(
            instance=queryset,
            context={
                "user": user,
                "approved": approved,
                "subordinate": subordinate,
            },
            many=True,
        ).data,
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: ListPendingFormDataSerializer(many=True)},
    tags=["Pending Data"],
    summary="To get list of pending data by batch",
)
@api_view(["GET"])
@permission_classes(
    [IsAuthenticated, IsSuperAdmin | IsSubmitter | IsApprover]
)
def list_data_batch(request, version, batch_id):
    batch = batch_for(request, batch_id)
    batch_list = batch.batch_data_list.order_by("-created")
    data = [
        d.data for d in batch_list
    ]
    return Response(
        ListPendingFormDataSerializer(
            instance=data,
            many=True
        ).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=ApproveDataRequestSerializer(),
    responses={200: DefaultResponseSerializer},
    tags=["Pending Data"],
    summary="Approve pending data",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsApprover | IsSubmitter | IsSuperAdmin])
def approve_pending_data(request, version):
    serializer = ApproveDataRequestSerializer(
        data=request.data, context={"user": request.user}
    )
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.save()
    return Response({"message": "Ok"}, status=status.HTTP_200_OK)


class BatchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            (200, "application/json"): inline_serializer(
                "ListDataBatchResponse",
                fields={
                    "current": serializers.IntegerField(),
                    "total": serializers.IntegerField(),
                    "total_page": serializers.IntegerField(),
                    "data": ListBatchSerializer(many=True),
                },
            )
        },
        tags=["Pending Data"],
        summary="To get list of batch",
        parameters=[
            OpenApiParameter(
                name="page",
                required=True,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="form",
                required=False,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="approved",
                default=False,
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
        ],
    )
    def get(self, request, version):
        serializer = BatchListRequestSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = DataBatch.objects.filter(
            user=request.user,
            approved=serializer.validated_data.get("approved"),
        ).order_by("-id")
        form = serializer.validated_data.get("form")
        if form:
            forms = [form] + list(form.children.all())
            queryset = queryset.filter(form__in=forms)
        paginator = PageNumberPagination()
        instance = paginator.paginate_queryset(queryset, request)
        page_size = REST_FRAMEWORK.get("PAGE_SIZE")
        data = {
            "current": int(request.GET.get("page", "1")),
            "total": queryset.count(),
            "total_page": ceil(queryset.count() / page_size),
            "data": ListBatchSerializer(instance=instance, many=True).data,
        }
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        request=CreateBatchSerializer(),
        tags=["Pending Data"],
        summary="To create batch",
    )
    def post(self, request, version):
        serializer = CreateBatchSerializer(
            data=request.data, context={"user": request.user}
        )
        if not serializer.is_valid():
            return Response(
                {"detail": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(user=request.user)
        return Response(
            {
                "message": "Batch created successfully",
            },
            status=status.HTTP_201_CREATED
        )


class BatchSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ListBatchSummarySerializer(many=True)},
        tags=["Pending Data"],
        summary="To get batch summary",
    )
    def get(self, request, batch_id, version):
        batch = batch_for(request, batch_id)
        # Get form IDs from data in this batch
        batch_form_ids = FormData.objects.filter(
            data_batch_list__batch=batch
        ).values_list("form_id", flat=True).distinct()
        # Get questions scoped to batch forms
        questions = Questions.objects.filter(
            form_id__in=batch_form_ids,
            type__in=[
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ],
        )
        # Get all answers for these questions in the batch
        answers = Answers.objects.filter(
            data__data_batch_list__batch=batch,
            question__in=questions,
        ).distinct("question")
        return Response(
            ListBatchSummarySerializer(
                instance=answers, many=True, context={"batch": batch}
            ).data,
            status=status.HTTP_200_OK,
        )


class BatchCommentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ListBatchCommentSerializer(many=True)},
        tags=["Pending Data"],
        summary="To get batch comment",
    )
    def get(self, request, batch_id, version):
        batch = batch_for(request, batch_id)
        instance = batch.batch_batch_comment.all().order_by("-id")
        return Response(
            ListBatchCommentSerializer(instance=instance, many=True).data,
            status=status.HTTP_200_OK,
        )


class BatchAttachmentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: BatchAttachmentsSerializer(many=True)},
        tags=["Batch Attachments"],
        summary="To get batch attachments",
    )
    def get(self, request, batch_id, version):
        batch = batch_for(request, batch_id)
        instance = batch.batch_batch_attachment.all().order_by("-id")
        return Response(
            BatchAttachmentsSerializer(instance=instance, many=True).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BatchAttachmentsSerializer(),
        responses={201: DefaultResponseSerializer},
        tags=["Batch Attachments"],
        summary="To create batch attachments",
    )
    def post(self, request, batch_id, version):
        batch = batch_for(request, batch_id)
        serializer = BatchAttachmentsSerializer(
            data=request.data, context={"user": request.user, "batch": batch}
        )
        if not serializer.is_valid():
            return Response(
                {"detail": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(user=request.user, batch=batch)
        return Response(
            {
                "message": "Batch attachment created successfully",
            },
            status=status.HTTP_201_CREATED
        )


@extend_schema(
    responses={200: DefaultResponseSerializer},
    tags=["Batch Attachments"],
    summary="To delete batch attachment",
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_batch_attachment(request, version, attachment_id):
    attachment = get_object_or_404(DataBatchAttachments, pk=attachment_id)
    if attachment.batch.user != request.user:
        return Response(
            {
                "message": (
                    "You do not have permission to delete this attachment"
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    batch = attachment.batch
    batch.batch_batch_comment.create(
        user=request.user,
        comment=f"Attachment deleted: {attachment.name}",
        file_path=attachment.file_path
    )
    attachment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=BatchAttachmentsSerializer(),
    responses={200: BatchAttachmentsSerializer},
    tags=["Batch Attachments"],
    summary="To update batch attachments",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_batch_attachments(request, version, attachment_id):
    attachment = get_object_or_404(DataBatchAttachments, pk=attachment_id)
    if attachment.batch.user != request.user:
        return Response(
            {
                "message": (
                    "You do not have permission to update this attachment"
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    batch = attachment.batch
    serializer = BatchAttachmentsSerializer(
        instance=attachment,
        data=request.data,
        context={"user": request.user, "batch": batch}
    )
    if not serializer.is_valid():
        return Response(
            {"detail": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.save(user=request.user, batch=batch)
    return Response(
        data=serializer.data,
        status=status.HTTP_200_OK
    )
