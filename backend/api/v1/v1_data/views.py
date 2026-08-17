# Create your views here.
import pandas as pd
import os
import pathlib

from datetime import datetime, timedelta, time
from math import ceil
from wsgiref.util import FileWrapper
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q, Count, Max, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django_q.tasks import async_task
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiParameter,
    OpenApiResponse,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.v1_data.models import (
    FormData,
    Answers,
    AnswerHistory,
)
from api.v1.v1_data.serializers import (
    SubmitFormSerializer,
    ListFormDataSerializer,
    ListFormDataRequestSerializer,
    ListPendingFormDataRequestSerializer,
    ListDataAnswerSerializer,
    ListPendingDataAnswerSerializer,
    ListPendingFormDataSerializer,
    SubmitPendingFormSerializer,
    SubmitUpdateDraftFormSerializer,
    SubmitFormDataAnswerSerializer,
    FormDataSerializer,
    FilterDraftFormDataSerializer,
)
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_approval.constants import DataApprovalStatus
from mis.settings import REST_FRAMEWORK
from utils.custom_permissions import (
    IsSubmitter,
    IsEditor,
    IsSuperAdminOrFormUser,
    PublicGet,
)
from utils.custom_serializer_fields import validate_serializers_message
from utils.default_serializers import DefaultResponseSerializer
from utils.export_form import blank_data_template

period_length = 60 * 15


class FormDataAddListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), IsSuperAdminOrFormUser()]
        if self.request.method == "PUT":
            return [IsAuthenticated(), IsEditor()]
        return [IsAuthenticated()]

    @extend_schema(
        responses={
            (200, "application/json"): inline_serializer(
                "DataList",
                fields={
                    "current": serializers.IntegerField(),
                    "total": serializers.IntegerField(),
                    "total_page": serializers.IntegerField(),
                    "data": ListFormDataSerializer(many=True),
                },
            )
        },
        tags=["Data"],
        parameters=[
            OpenApiParameter(
                name="page",
                required=True,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="administration",
                required=False,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="parent",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="search",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Case-insensitive search on FormData name",
            ),
            OpenApiParameter(
                name="sort_by",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Field to sort by (created, updated, name, "
                    "total_children, latest_activity)"
                ),
                enum=[
                    "created",
                    "updated",
                    "name",
                    "total_children",
                    "latest_activity",
                ],
            ),
            OpenApiParameter(
                name="sort_type",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Sort direction (ascend, descend). Default: descend"
                ),
                enum=["ascend", "descend"],
            ),
            OpenApiParameter(
                name="date_from",
                required=False,
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description=(
                    "Lower bound date filter (YYYY-MM-DD). When "
                    "sort_by=latest_activity, matches on the latest "
                    "monitoring activity date; otherwise matches on "
                    "the registration created date."
                ),
            ),
            OpenApiParameter(
                name="date_to",
                required=False,
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description=(
                    "Upper bound date filter (YYYY-MM-DD). When "
                    "sort_by=latest_activity, matches on the latest "
                    "monitoring activity date; otherwise matches on "
                    "the registration created date."
                ),
            ),
        ],
        summary="To get list of form data",
    )
    def get(self, request, form_id, version):
        form = get_object_or_404(
            Forms.objects.for_user(request.user), pk=form_id
        )
        serializer = ListFormDataRequestSerializer(
            data=request.GET, context={"form_id": form_id}
        )
        if not serializer.is_valid():
            return Response(
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        page_size = REST_FRAMEWORK.get("PAGE_SIZE")

        paginator = PageNumberPagination()

        parent = serializer.validated_data.get("parent")
        search = serializer.validated_data.get("search")
        date_from = serializer.validated_data.get("date_from")
        date_to = serializer.validated_data.get("date_to")
        sort_by = serializer.validated_data.get("sort_by", "created")
        sort_type = serializer.validated_data.get("sort_type", "descend")

        # latest_activity sorting is not supported for monitoring data
        if parent and sort_by == "latest_activity":
            sort_by = "updated"

        order_by = f"-{sort_by}" if sort_type == "descend" else sort_by

        if parent:
            # Only get the children data
            queryset = (
                form.form_form_data.select_related("parent__form")
                .filter(
                    uuid=parent,
                    is_pending=False,
                    is_draft=False,
                )
                .annotate(
                    total_children=Count(
                        "children",
                        filter=Q(
                            children__is_pending=False,
                            children__is_draft=False,
                        ),
                    )
                )
            )
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search)
                    | Q(parent__name__icontains=search)
                    | Q(created_by__first_name__icontains=search)
                    | Q(created_by__last_name__icontains=search)
                    | Q(created_by__email__icontains=search)
                )
            if date_from:
                start_datetime = datetime.combine(date_from, time.min)
                if settings.USE_TZ:
                    start_datetime = timezone.make_aware(start_datetime)
                queryset = queryset.filter(created__gte=start_datetime)
            if date_to:
                end_datetime = datetime.combine(
                    date_to + timedelta(days=1), time.min
                )
                if settings.USE_TZ:
                    end_datetime = timezone.make_aware(end_datetime)
                queryset = queryset.filter(created__lt=end_datetime)
            queryset = queryset.order_by(order_by)
            instance = paginator.paginate_queryset(queryset, request)
            total = queryset.count()
            data = {
                "current": int(request.GET.get("page", "1")),
                "total": total,
                "total_page": ceil(total / page_size),
                "data": ListFormDataSerializer(
                    instance=instance,
                    many=True,
                ).data,
            }
            return Response(data, status=status.HTTP_200_OK)

        filter_data = {
            "is_pending": False,
            "is_draft": False,
        }

        if serializer.validated_data.get("administration"):
            filter_administration = serializer.validated_data.get(
                "administration"
            )
            if filter_administration.path:
                filter_path = "{0}{1}.".format(
                    filter_administration.path, filter_administration.id
                )
            else:
                filter_path = f"{filter_administration.id}."
            filter_descendants = list(
                Administration.objects.filter(
                    path__startswith=filter_path
                ).values_list("id", flat=True)
            )
            filter_descendants.append(filter_administration.id)
            filter_data["administration_id__in"] = filter_descendants
        else:
            # Filter data by user administration path. The root is looked
            # up within the tenant: an unscoped first() could pick another
            # tenant's root and scope the whole list to it.
            adm = (
                Administration.objects.for_user(request.user)
                .filter(
                    parent__isnull=True,
                )
                .first()
            )
            if not request.user.is_superuser:
                user_role = request.user.user_user_role.first()
                if user_role:
                    adm = user_role.administration
            user_path = adm.path if adm.path else f"{adm.pk}."
            filter_data["administration__path__startswith"] = user_path

        # Subquery to get the form name of the child with latest activity.
        # Order by Coalesce(updated, created) so NULL updated records are
        # ranked by created instead of being sorted first by PostgreSQL.
        latest_child_form_subquery = (
            FormData.objects.filter(
                parent=OuterRef("pk"), is_pending=False, is_draft=False
            )
            .annotate(child_activity=Coalesce("updated", "created"))
            .order_by("-child_activity")
            .values("form__name")[:1]
        )

        queryset = (
            form.form_form_data.select_related("parent__form")
            .filter(**filter_data)
            .annotate(
                total_children=Count(
                    "children",
                    filter=Q(
                        children__is_pending=False, children__is_draft=False
                    ),
                ),
                # Use Coalesce so flow-imported children with NULL updated
                # fall back to their created date for activity calculation.
                latest_child_activity=Max(
                    Coalesce("children__updated", "children__created"),
                    filter=Q(
                        children__is_pending=False, children__is_draft=False
                    ),
                ),
                latest_activity_source=Subquery(latest_child_form_subquery),
            )
            .annotate(
                latest_activity=Coalesce(
                    "latest_child_activity", "updated", "created"
                )
            )
        )
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(parent__name__icontains=search)
                | Q(created_by__first_name__icontains=search)
                | Q(created_by__last_name__icontains=search)
                | Q(created_by__email__icontains=search)
            )
        # When sorting by latest_activity, filter on that annotation so
        # registrations with recent monitoring children are not excluded.
        date_filter_field = (
            "latest_activity" if sort_by == "latest_activity" else "created"
        )
        if date_from:
            start_datetime = datetime.combine(date_from, time.min)
            if settings.USE_TZ:
                start_datetime = timezone.make_aware(start_datetime)
            queryset = queryset.filter(
                **{f"{date_filter_field}__gte": start_datetime}
            )
        if date_to:
            end_datetime = datetime.combine(
                date_to + timedelta(days=1), time.min
            )
            if settings.USE_TZ:
                end_datetime = timezone.make_aware(end_datetime)
            queryset = queryset.filter(
                **{f"{date_filter_field}__lt": end_datetime}
            )
        queryset = queryset.order_by(order_by)

        instance = paginator.paginate_queryset(queryset, request)
        total = queryset.count()
        data = {
            "current": int(request.GET.get("page", "1")),
            "total": total,
            "total_page": ceil(total / page_size),
            "data": ListFormDataSerializer(
                instance=instance,
                context={
                    "questions": serializer.validated_data.get("questions")
                },
                many=True,
            ).data,
        }
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SubmitFormSerializer,
        responses={200: DefaultResponseSerializer},
        tags=["Data"],
        summary="Submit form data",
    )
    def post(self, request, form_id, version):
        form = get_object_or_404(
            Forms.objects.for_user(request.user), pk=form_id
        )
        serializer = SubmitFormSerializer(
            data=request.data, context={"user": request.user, "form": form}
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response({"message": "ok"}, status=status.HTTP_200_OK)

    @extend_schema(
        request=SubmitFormDataAnswerSerializer(many=True),
        responses={200: DefaultResponseSerializer},
        tags=["Data"],
        parameters=[
            OpenApiParameter(
                name="data_id",
                required=True,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            )
        ],
        summary="Edit form data",
    )
    def put(self, request, form_id, version):
        data_id = request.GET["data_id"]
        user = request.user
        data = get_object_or_404(
            FormData.objects.for_user(request.user), pk=data_id
        )
        serializer = SubmitFormDataAnswerSerializer(
            data=request.data, many=True
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        answers = request.data

        # Direct update
        # move current answer to answer_history
        for answer in answers:
            index = answer.get("index", 0)
            form_answer = Answers.objects.filter(
                data=data, index=index, question=answer.get("question")
            ).first()
            if form_answer:
                AnswerHistory.objects.create(
                    data=form_answer.data,
                    question=form_answer.question,
                    name=form_answer.name,
                    value=form_answer.value,
                    options=form_answer.options,
                    created_by=user,
                )
            if not form_answer:
                form_answer = Answers(
                    data=data,
                    question_id=answer.get("question"),
                    created_by=user,
                )
            # prepare updated answer
            question_id = answer.get("question")
            question = Questions.objects.get(id=question_id)
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
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            else:
                # for administration,number question type
                value = answer.get("value")
            # Update answer
            form_answer.data = data
            form_answer.question = question
            form_answer.name = name
            form_answer.value = value
            form_answer.options = option
            form_answer.updated = timezone.now()
            form_answer.save()
        # update datapoint
        data.updated = timezone.now()
        data.updated_by = user
        data.save()
        # Refresh materialized view via async task
        async_task("api.v1.v1_data.tasks.seed_approved_data", data)
        return Response(
            {"message": "direct update success"}, status=status.HTTP_200_OK
        )


class DataAnswerDetailDeleteView(APIView):
    permission_classes = [PublicGet]

    @extend_schema(
        responses={200: ListDataAnswerSerializer(many=True)},
        tags=["Data"],
        summary="To get answers for form data",
    )
    def get(self, request, data_id, version):
        data = get_object_or_404(
            FormData.objects.for_user(request.user), pk=data_id
        )
        return Response(
            ListDataAnswerSerializer(
                instance=data.data_answer.all(), many=True
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deletion with no response")
        },
        tags=["Data"],
        summary="Delete datapoint include answer & history",
    )
    def delete(self, request, data_id, version):
        instance = get_object_or_404(
            FormData.objects.for_user(request.user), pk=data_id
        )
        answers = Answers.objects.filter(data_id=data_id)
        answers.delete()
        history = AnswerHistory.objects.filter(data_id=data_id)
        if history.count():
            history.delete()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PendingDataDetailDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ListPendingDataAnswerSerializer(many=True)},
        tags=["Pending Data"],
        summary="To get list of answers for pending data",
    )
    def get(self, request, pending_data_id, version):
        data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=pending_data_id,
            is_pending=True,
        )
        # Get the last data from the last children
        last_data = (
            data.parent.children.filter(is_pending=False).last()
            if data.parent
            else None
        )
        # Find the original FormData if this is an update
        if not last_data:
            last_data = FormData.objects.filter(
                uuid=data.uuid, is_pending=False
            ).first()
        return Response(
            ListPendingDataAnswerSerializer(
                context={"last_data": last_data},
                instance=data.data_answer.all(),
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deletion with no response")
        },
        tags=["Pending Data"],
        summary="To delete pending data",
    )
    def delete(self, request, pending_data_id, version):
        instance = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=pending_data_id,
            is_pending=True,
        )
        if instance.created_by_id != request.user.id:
            return Response(
                {"message": "You are not allowed to perform this action"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DataDetailDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=FormDataSerializer,
        tags=["Data"],
        summary="To get data by ID",
    )
    def get(self, request, data_id, version):
        data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=data_id,
            is_pending=False,
        )
        return Response(
            FormDataSerializer(instance=data).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deletion with no response")
        },
        tags=["Data"],
        summary="To delete data",
    )
    def delete(self, request, data_id, version):
        instance = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=data_id,
            is_pending=False,
        )
        if (
            not request.user.is_superuser
            or request.user.user_role.filter(
                role__role_role_access__data_access=DataAccessTypes.delete
            ).exists()
        ):
            return Response(
                {"message": "You are not allowed to perform this action"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["File"], summary="Export Form data")
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_form_data(request, version, form_id):
    form = get_object_or_404(Forms.objects.for_user(request.user), pk=form_id)
    form_name = form.name
    filename = f"{form.id}-{form_name}"
    directory = "tmp"
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
    filepath = f"./{directory}/{filename}.xlsx"
    if os.path.exists(filepath):
        os.remove(filepath)
    writer = pd.ExcelWriter(filepath, engine="xlsxwriter")
    blank_data_template(form=form, writer=writer)
    writer.save()
    filename = filepath.split("/")[-1].replace(" ", "-")
    zip_file = open(filepath, "rb")
    response = HttpResponse(
        FileWrapper(zip_file),
        content_type="application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    return response


class PendingFormDataView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SubmitPendingFormSerializer,
        responses={200: DefaultResponseSerializer},
        tags=["Pending Data"],
        summary="Submit pending form data",
    )
    def post(self, request, form_id, version):
        form = get_object_or_404(
            Forms.objects.for_user(request.user), pk=form_id
        )
        serializer = SubmitPendingFormSerializer(
            data=request.data, context={"user": request.user, "form": form}
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response({"message": "ok"}, status=status.HTTP_200_OK)

    @extend_schema(
        responses={
            (200, "application/json"): inline_serializer(
                "PendingDataListResponse",
                fields={
                    "current": serializers.IntegerField(),
                    "total": serializers.IntegerField(),
                    "total_page": serializers.IntegerField(),
                    "data": ListPendingFormDataSerializer(many=True),
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
                name="selection_ids",
                required=False,
                type={"type": "array", "items": {"type": "number"}},
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="search",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search by datapoint name",
            ),
            OpenApiParameter(
                name="date_from",
                required=False,
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter data created on or after this date "
                "(YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="date_to",
                required=False,
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter data created on or before this date "
                "(YYYY-MM-DD)",
            ),
        ],
        summary="To get list of pending form data",
    )
    def get(self, request, form_id, version):
        form = get_object_or_404(
            Forms.objects.for_user(request.user), pk=form_id
        )
        serializer = ListPendingFormDataRequestSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        page_size = REST_FRAMEWORK.get("PAGE_SIZE")

        # Get validated filters
        search = serializer.validated_data.get("search")
        date_from = serializer.validated_data.get("date_from")
        date_to = serializer.validated_data.get("date_to")

        # Get all child form IDs including the parent form
        form_ids = [form.id]
        if form.children.exists():
            child_form_ids = form.children.values_list("id", flat=True)
            form_ids.extend(list(child_form_ids))
        # Query for pending form data across parent and child forms
        queryset = FormData.objects.filter(
            form_id__in=form_ids,
            created_by=request.user,
            data_batch_list__isnull=True,
            is_pending=True,
            is_draft=False,
        )
        # Apply search filter (search in name or parent's name for monitoring)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(parent__name__icontains=search)
            )
        # Apply date filters
        if date_from:
            start_datetime = datetime.combine(date_from, time.min)
            if settings.USE_TZ:
                start_datetime = timezone.make_aware(start_datetime)
            queryset = queryset.filter(created__gte=start_datetime)
        if date_to:
            end_datetime = datetime.combine(
                date_to + timedelta(days=1), time.min
            )
            if settings.USE_TZ:
                end_datetime = timezone.make_aware(end_datetime)
            queryset = queryset.filter(created__lt=end_datetime)
        queryset = queryset.order_by("-created")
        # if selection_ids is provided, filter the queryset
        selection_ids = request.GET.getlist("selection_ids")
        if selection_ids:
            # Return without pagination if selection_ids are provided
            queryset = queryset.filter(id__in=selection_ids)
            return Response(
                ListPendingFormDataSerializer(
                    instance=queryset, many=True
                ).data,
                status=status.HTTP_200_OK,
            )

        paginator = PageNumberPagination()
        instance = paginator.paginate_queryset(queryset, request)

        data = {
            "current": int(request.GET.get("page", "1")),
            "total": queryset.count(),
            "total_page": ceil(queryset.count() / page_size),
            "data": ListPendingFormDataSerializer(
                instance=instance, many=True
            ).data,
        }
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SubmitFormDataAnswerSerializer(many=True),
        responses={200: DefaultResponseSerializer},
        tags=["Pending Data"],
        parameters=[
            OpenApiParameter(
                name="pending_data_id",
                required=True,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            )
        ],
        summary="Edit pending form data",
    )
    def put(self, request, form_id, version):
        get_object_or_404(Forms.objects.for_user(request.user), pk=form_id)
        pending_data_id = request.GET["pending_data_id"]
        user = request.user
        pending_data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=pending_data_id,
            is_pending=True,
        )
        serializer = SubmitFormDataAnswerSerializer(
            data=request.data, many=True
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pending_answers = request.data
        # move current pending_answer to answer_history
        for answer in pending_answers:
            form_answer = Answers.objects.get(
                data=pending_data, question=answer.get("question")
            )
            AnswerHistory.objects.create(
                data=form_answer.data,
                question=form_answer.question,
                name=form_answer.name,
                value=form_answer.value,
                options=form_answer.options,
                created_by=user,
            )
            # prepare updated answer
            question_id = answer.get("question")
            question = Questions.objects.get(id=question_id)
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
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            else:
                # for administration,number question type
                value = answer.get("value")
            # Update answer
            form_answer.data = pending_data
            form_answer.question = question
            form_answer.name = name
            form_answer.value = value
            form_answer.options = option
            form_answer.updated = timezone.now()
            form_answer.save()
        # update datapoint
        pending_data.updated = timezone.now()
        pending_data.updated_by = user
        pending_data.save()
        if (
            hasattr(pending_data, "data_batch_list")
            and not pending_data.data_batch_list.batch.approved
        ):
            # If this pending data is part of a batch,
            # update the batch approval status as pending
            approvals = pending_data.data_batch_list.batch.batch_approval.all()
            for approval in approvals:
                # Reset the approval status to pending if it was rejected
                if approval.status == DataApprovalStatus.rejected:
                    approval.status = DataApprovalStatus.pending
                # If the approval is by the user, set it to approved
                if approval.user == request.user:
                    approval.status = DataApprovalStatus.approved
                # Update the approval timestamp
                approval.updated = timezone.now()
                approval.save()
        return Response(
            {"message": "update success"}, status=status.HTTP_200_OK
        )


class DraftFormDataListView(APIView):
    permission_classes = [IsAuthenticated, IsSubmitter]

    @extend_schema(
        responses={
            (200, "application/json"): inline_serializer(
                "DraftDataListResponse",
                fields={
                    "current": serializers.IntegerField(),
                    "total": serializers.IntegerField(),
                    "total_page": serializers.IntegerField(),
                    "data": ListFormDataSerializer(many=True),
                },
            )
        },
        tags=["Draft Data"],
        parameters=[
            OpenApiParameter(
                name="page",
                required=False,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="search",
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="administration",
                required=False,
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
            ),
        ],
        summary="To get list of draft form data",
    )
    def get(self, request, form_id, version):
        form = get_object_or_404(
            Forms.objects.for_user(request.user), pk=form_id
        )
        page_size = REST_FRAMEWORK.get("PAGE_SIZE")

        serializer = FilterDraftFormDataSerializer(
            data=request.GET, context={"form_id": form_id}
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        page = serializer.validated_data.get("page", 1)

        # Filter draft data for this form and user
        queryset = (
            FormData.objects_draft.filter(form=form, created_by=request.user)
            .annotate(
                total_children=Count(
                    "children",
                    filter=Q(
                        children__is_pending=False, children__is_draft=False
                    ),
                )
            )
            .order_by("-created")
        )

        # Apply search filter if provided
        search = serializer.validated_data.get("search", None)
        if search:
            queryset = queryset.filter(name__icontains=search)

        # Apply administration filter if provided
        administration = serializer.validated_data.get("administration", None)
        if administration:
            adm = serializer.validated_data.get("administration")
            adm_path = adm.path if adm.path else f"{adm.pk}."
            queryset = queryset.filter(
                Q(administration__path__startswith=adm_path)
                | Q(administration=adm)
            )

        paginator = PageNumberPagination()
        instance = paginator.paginate_queryset(queryset, request)

        data = {
            "current": int(page),
            "total": queryset.count(),
            "total_page": ceil(queryset.count() / page_size),
            "data": ListFormDataSerializer(instance=instance, many=True).data,
        }
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SubmitPendingFormSerializer,
        responses={201: DefaultResponseSerializer},
        tags=["Draft Data"],
        summary="Submit draft form data",
    )
    def post(self, request, form_id, version):
        form = get_object_or_404(
            Forms.objects.for_user(request.user), pk=form_id
        )
        serializer = SubmitPendingFormSerializer(
            data=request.data,
            context={
                "user": request.user,
                "form": form,
                "is_draft": True,  # Indicate this is a draft submission
            },
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {"message": "Draft created successfully"},
            status=status.HTTP_201_CREATED,
        )


class DraftFormDataDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSubmitter]

    @extend_schema(
        responses=FormDataSerializer,
        tags=["Draft Data"],
        summary="Get draft form data by ID",
    )
    def get(self, request, data_id, version):
        draft_data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=data_id,
            is_draft=True,
        )
        if draft_data.created_by_id != request.user.id:
            return Response(
                {"message": "You are not allowed to perform this action"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FormDataSerializer(
                instance=draft_data, context={"webform": True}
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=SubmitUpdateDraftFormSerializer,
        responses={200: DefaultResponseSerializer},
        tags=["Draft Data"],
        summary="Edit draft form data",
    )
    def put(self, request, data_id, version):
        draft_data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=data_id,
            is_draft=True,
        )
        if draft_data.created_by_id != request.user.id:
            return Response(
                {"message": "You are not allowed to perform this action"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubmitUpdateDraftFormSerializer(
            instance=draft_data,
            data=request.data,
            context={"user": request.user, "form": draft_data.form},
        )
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {"message": "Draft updated successfully"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deletion with no response")
        },
        tags=["Draft Data"],
        summary="Delete draft form data",
    )
    def delete(self, request, data_id, version):
        draft_data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=data_id,
            is_draft=True,
        )
        if draft_data.created_by_id != request.user.id:
            return Response(
                {
                    "detail": "You do not have permission to perform this action."  # noqa: E501
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Hard delete the draft data
        draft_data.hard_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublishDraftFormDataView(APIView):
    permission_classes = [IsAuthenticated, IsSubmitter]

    @extend_schema(
        request=inline_serializer("PublishDraftRequestSerializer", fields={}),
        responses={200: DefaultResponseSerializer},
        tags=["Draft Data"],
        summary="Publish draft form data",
    )
    def post(self, request, data_id, version):
        draft_data = get_object_or_404(
            FormData.objects.for_user(request.user),
            pk=data_id,
            is_draft=True,
        )
        if draft_data.created_by_id != request.user.id:
            return Response(
                {
                    "detail": "You do not have permission to perform this action."  # noqa: E501
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if user is super admin or if form has approval
        user = request.user
        is_super_admin = user.is_superuser
        direct_to_data = is_super_admin or not draft_data.has_approval

        # Publish the draft data (mark as not draft)
        draft_data.publish()
        draft_data.is_pending = True if not direct_to_data else False

        draft_data.save()

        # Save to file if it's published and not pending
        if direct_to_data:
            async_task("api.v1.v1_data.tasks.seed_approved_data", draft_data)

        return Response(
            {"message": "Draft published successfully"},
            status=status.HTTP_200_OK,
        )
