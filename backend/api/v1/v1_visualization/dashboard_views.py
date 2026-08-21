from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework.generics import get_object_or_404
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_visualization.dashboard_serializers import (
    ValuesFilterSerializer,
    ValuesResponseSerializer,
    EscalationResponseSerializer,
    ProgressResponseSerializer,
)
from api.v1.v1_visualization.dashboard_examples import (
    VALUES_EXAMPLES,
    ESCALATION_EXAMPLES,
    PROGRESS_EXAMPLES,
)
from api.v1.v1_visualization.values_functions import (
    handle_count_mode,
    handle_option_question,
    handle_number_question,
)
from api.v1.v1_visualization.escalation_functions import (
    handle_escalation,
)
from api.v1.v1_visualization.progress_functions import (
    handle_progress,
)
from api.v1.v1_visualization.functions import (
    resolve_default_administration_id,
    split_criteria_by_form,
)
from api.v1.v1_visualization.dashboard_serializers import (
    EscalationFilterSerializer,
    ProgressFilterSerializer,
)
from utils.custom_serializer_fields import (
    validate_serializers_message,
)


@extend_schema(
    description="Generic visualization values endpoint",
    tags=["Visualization"],
    responses={
        200: OpenApiResponse(
            response=ValuesResponseSerializer,
            description=(
                "Aggregated data shaped by group_by / stack_by."
                " See examples for per-use-case shapes."
            ),
        ),
        400: OpenApiResponse(
            description="Invalid query parameters.",
        ),
    },
    examples=VALUES_EXAMPLES,
    parameters=[
        OpenApiParameter(
            name="form_id", required=True,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="monitoring", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=["latest", "all"],
        ),
        OpenApiParameter(
            name="group_by", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=[
                "date", "month", "id",
                "parent_id", "option",
            ],
        ),
        OpenApiParameter(
            name="stack_by", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=["option", "parent_id"],
        ),
        OpenApiParameter(
            name="sum_by", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=["id", "parent_id"],
        ),
        OpenApiParameter(
            name="value_type", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=["number", "percentage"],
        ),
        OpenApiParameter(
            name="repeat_agg", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            enum=[
                "average", "sum", "max", "min", "last",
            ],
        ),
        OpenApiParameter(
            name="from_date", required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="to_date", required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="date_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="administration_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="option_value", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="criteria", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                "AND-joined multi-criteria filter. Format: "
                "'type:qid:value,...'. Types: option_equals, "
                "option_contains, option_in (pipe-delimited "
                "values), threshold_gt, threshold_lt."
            ),
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visualization_values(request, version):
    """Generic visualization values endpoint.

    Returns aggregated data for charts, KPIs, and tables.
    All configuration via query parameters.
    """
    serializer = ValuesFilterSerializer(
        data=request.query_params
    )
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(
                serializer.errors
            )},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated = serializer.validated_data
    form = get_object_or_404(
        Forms, pk=validated["form_id"]
    )
    question = validated.get("question")

    params = {
        "monitoring": validated.get(
            "monitoring", "latest"
        ),
        "group_by": validated.get("group_by"),
        "stack_by": validated.get("stack_by"),
        "sum_by": validated.get("sum_by"),
        "value_type": validated.get(
            "value_type", "number"
        ),
        "repeat_agg": validated.get(
            "repeat_agg", "average"
        ),
        "from_date": validated.get("from_date"),
        "to_date": validated.get("to_date"),
        "date_question_id": validated.get(
            "date_question_id"
        ),
        "administration_id": resolve_default_administration_id(
            validated.get("administration_id"),
        ),
        "option_value": validated.get("option_value"),
        "criteria": validated.get("criteria"),
        "parent_criteria": validated.get("parent_criteria"),
        "include_unanswered": validated.get(
            "include_unanswered", False
        ),
        "include_empty": validated.get(
            "include_empty", False
        ),
    }

    # Route to handler
    if not question:
        result = handle_count_mode(form, params)
    elif question.type == QuestionTypes.number:
        result = handle_number_question(
            form, question, params
        )
    elif question.type in [
        QuestionTypes.option,
        QuestionTypes.multiple_option,
    ]:
        result = handle_option_question(
            form, question, params
        )
    else:
        result = handle_count_mode(form, params)

    # Format response
    if isinstance(result, dict):
        return Response(result, status=status.HTTP_200_OK)
    data, labels = result
    return Response(
        {"data": data, "labels": labels},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    description="Escalation table with dynamic criteria and columns",
    tags=["Visualization"],
    responses={
        200: OpenApiResponse(
            response=EscalationResponseSerializer,
            description=(
                "Paginated escalation results. Column keys in"
                " `results[]` follow the request's `columns=` spec."
            ),
        ),
        400: OpenApiResponse(
            description="Invalid query parameters.",
        ),
        404: OpenApiResponse(
            description="form_id not found.",
        ),
    },
    examples=ESCALATION_EXAMPLES,
    parameters=[
        OpenApiParameter(
            name="monitoring_form_id", required=True,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="criteria", required=True,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="columns", required=True,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="page", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="page_size", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="administration_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="from_date", required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="to_date", required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="date_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="filter_criteria", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                "Optional AND-narrowing criteria layered "
                "on top of the OR escalation criteria "
                "(shared grammar with /values)."
            ),
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visualization_escalation(request, form_id, version):
    """Escalation table with query-param-driven criteria."""
    parent_form = get_object_or_404(Forms, pk=form_id)

    serializer = EscalationFilterSerializer(
        data=request.query_params
    )
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(
                serializer.errors
            )},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated = serializer.validated_data
    result = handle_escalation(
        parent_form=parent_form,
        monitoring_form_id=validated["monitoring_form_id"],
        criteria=validated["criteria"],
        columns=validated["columns"],
        params={
            "page": validated.get("page", 1),
            "page_size": validated.get("page_size", 20),
            "administration_id": resolve_default_administration_id(
                validated.get("administration_id"),
            ),
            "from_date": validated.get("from_date"),
            "to_date": validated.get("to_date"),
            "date_question_id": validated.get(
                "date_question_id"
            ),
            "filter_criteria": validated.get("filter_criteria"),
            "query_string": [
                (k, v)
                for k, values in request.query_params.lists()
                for v in values
            ],
        },
    )
    return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    description="Progress computation with configurable formulas",
    tags=["Visualization"],
    responses={
        200: OpenApiResponse(
            response=ProgressResponseSerializer,
            description=(
                "Progress computation result. Shape depends on "
                "requested components and formula. See examples."
            ),
        ),
        400: OpenApiResponse(
            description="Invalid query parameters.",
        ),
        404: OpenApiResponse(
            description="form_id not found.",
        ),
    },
    examples=PROGRESS_EXAMPLES,
    parameters=[
        OpenApiParameter(
            name="monitoring_form_id", required=True,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="components", required=True,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="filter_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="filter_option_value", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="scope_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description=(
                "Question whose answer determines which "
                "components apply per datapoint (e.g. "
                "project type). Components with "
                "applicable_types are filtered to match."
            ),
        ),
        OpenApiParameter(
            name="administration_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="from_date", required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="to_date", required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="date_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="criteria", required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                "AND-joined multi-criteria filter "
                "(same grammar as /values)."
            ),
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visualization_progress(request, form_id, version):
    """Progress computation endpoint."""
    parent_form = get_object_or_404(Forms, pk=form_id)

    serializer = ProgressFilterSerializer(
        data=request.query_params
    )
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(
                serializer.errors
            )},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated = serializer.validated_data
    mon_criteria, parent_criteria = split_criteria_by_form(
        validated.get("criteria"),
        validated["monitoring_form_id"],
        parent_form.id,
    )
    result = handle_progress(
        parent_form=parent_form,
        monitoring_form_id=validated["monitoring_form_id"],
        components=validated["components"],
        params={
            "filter_question_id": validated.get(
                "filter_question_id"
            ),
            "filter_option_value": validated.get(
                "filter_option_value"
            ),
            "scope_question_id": validated.get(
                "scope_question_id"
            ),
            "administration_id": resolve_default_administration_id(
                validated.get("administration_id"),
            ),
            "from_date": validated.get("from_date"),
            "to_date": validated.get("to_date"),
            "date_question_id": validated.get(
                "date_question_id"
            ),
            "criteria": mon_criteria,
            "parent_criteria": parent_criteria,
        },
    )
    return Response(result, status=status.HTTP_200_OK)
