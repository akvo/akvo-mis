from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework.generics import get_object_or_404
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_visualization.dashboard_serializers import (
    ValuesFilterSerializer,
    ValuesResponseSerializer,
    EscalationResponseSerializer,
)
from api.v1.v1_visualization.dashboard_examples import (
    VALUES_EXAMPLES,
    ESCALATION_EXAMPLES,
)
from api.v1.v1_visualization.values_functions import (
    handle_count_mode,
    handle_option_question,
    handle_number_question,
)
from api.v1.v1_visualization.escalation_functions import (
    handle_escalation,
)
from api.v1.v1_visualization.scatter_functions import (
    handle_scatter,
)
from api.v1.v1_visualization.functions import (
    resolve_default_administration_id,
    tenant_scoped_forms,
)
from api.v1.v1_visualization.dashboard_serializers import (
    EscalationFilterSerializer,
)
from api.v1.v1_visualization.public_scope import (
    check_ids,
    question_ids_in_columns,
    question_ids_in_criteria,
    resolve_view_scope,
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
            name="value_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description=(
                "Number question whose aggregate becomes the bar"
                " height. Omit to count submissions."
            ),
        ),
        OpenApiParameter(
            name="stack_question_id", required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description=(
                "Option question supplying the stacks; only with"
                " stack_by=option. Omit to stack by the measured"
                " question's own options."
            ),
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
def visualization_values(request, version):
    """Generic visualization values endpoint.

    Returns aggregated data for charts, KPIs, and tables.
    All configuration via query parameters.
    """
    # Scope first, exactly as visualization_escalation does. The
    # serializer's own validators run tenant-unscoped existence
    # queries, so resolving scope after them would let an anonymous
    # caller with no dashboard tell "form not found" from "no public
    # dashboard", and probe another workspace's schema by id.
    tenant, allowed = resolve_view_scope(request)

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
    # Every id the caller supplied, checked before any data query
    # runs. group_by and stack_by are absent on purpose: both are
    # choice fields over closed vocabularies and cannot name a
    # question. stack_question_id is present for exactly the opposite
    # reason -- it names one. Note that with a VALID dashboard_slug,
    # form/question existence is still probed by the serializer's own
    # validators above, before this runs -- this only bounds what a
    # caller who has already named a dashboard may then ask about.
    #
    # administration_id is absent too, and not an oversight:
    # resolve_default_administration_id() below returns it unchecked
    # against the dashboard's tenant. That is safe only because it
    # narrows a queryset already rooted at this tenant-scoped form, so
    # a foreign id can subtract rows, never widen the read -- see D-6
    # in the design doc. Do not assume it is guarded here.
    # criteria is read from the raw query params, not validated: its
    # validate_criteria hook replaces the string with a parsed
    # structure, and question_ids_in_criteria expects the string
    # (same reasoning as filter_criteria below, in the escalation
    # view).
    check_ids(
        allowed,
        form_ids=[validated["form_id"]],
        question_ids=[
            validated.get("question_id"),
            validated.get("question_y"),
            validated.get("stack_question_id"),
            validated.get("value_question_id"),
            validated.get("date_question_id"),
            *question_ids_in_criteria(
                request.query_params.get("criteria")
            ),
        ],
    )
    form = get_object_or_404(
        tenant_scoped_forms(tenant), pk=validated["form_id"]
    )
    question = validated.get("question")

    params = {
        "monitoring": validated.get(
            "monitoring", "latest"
        ),
        "group_by": validated.get("group_by"),
        "stack_by": validated.get("stack_by"),
        "stack_question": validated.get("stack_question"),
        "value_question": validated.get("value_question"),
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
            validated.get("administration_id"), tenant,
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

    # Scatter mode
    if validated.get("mode") == "scatter":
        data = handle_scatter(
            form, question,
            validated.get("question_y_obj"), params,
        )
        return Response(data, status=status.HTTP_200_OK)

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
def visualization_escalation(request, form_id, version):
    """Escalation table with query-param-driven criteria."""
    tenant, allowed = resolve_view_scope(request)

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
    # criteria and columns are read raw too, for the same reason as
    # filter_criteria: validate_criteria/validate_columns replace the
    # string with a parsed structure, and the extractors expect the
    # string (see the identical fix in visualization_values above).
    # administration_id is deliberately unchecked here too -- see the
    # comment above visualization_values's check_ids call.
    check_ids(
        allowed,
        form_ids=[form_id, validated["monitoring_form_id"]],
        question_ids=[
            validated.get("date_question_id"),
            *question_ids_in_criteria(
                request.query_params.get("criteria")
            ),
            *question_ids_in_columns(
                request.query_params.get("columns")
            ),
            *question_ids_in_criteria(
                request.query_params.get("filter_criteria")
            ),
        ],
    )
    parent_form = get_object_or_404(
        tenant_scoped_forms(tenant), pk=form_id
    )
    result = handle_escalation(
        parent_form=parent_form,
        monitoring_form_id=validated["monitoring_form_id"],
        criteria=validated["criteria"],
        columns=validated["columns"],
        params={
            "page": validated.get("page", 1),
            "page_size": validated.get("page_size", 20),
            "administration_id": resolve_default_administration_id(
                validated.get("administration_id"), tenant,
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
