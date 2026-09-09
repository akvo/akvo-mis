from rest_framework import serializers
from api.v1.v1_visualization.constants import (
    VALID_GROUP_BY,
    VALID_MONITORING,
    VALID_VALUE_TYPE,
    VALID_REPEAT_AGG,
    VALID_STACK_BY,
    STACK_QUESTION_TYPES,
    VALID_CRITERIA_TYPES,
    VALID_VALUES_CRITERIA_TYPES,
    VALID_COLUMN_SOURCES,
    SUPPORTED_QUESTION_TYPES,
)
from api.v1.v1_visualization.functions import parse_criteria_string
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions


class ValuesFilterSerializer(serializers.Serializer):
    """Validates query parameters for /visualization/values endpoint."""

    form_id = serializers.IntegerField(required=True)
    question_id = serializers.IntegerField(required=False)
    monitoring = serializers.ChoiceField(
        choices=list(VALID_MONITORING),
        default="latest",
    )
    group_by = serializers.ChoiceField(
        choices=list(VALID_GROUP_BY),
        required=False,
        allow_null=True,
    )
    stack_by = serializers.ChoiceField(
        choices=list(VALID_STACK_BY),
        required=False,
        allow_null=True,
    )
    # The question whose options become the stacks. Absent means "the
    # widget's own question", which is what stack_by=option has always
    # meant, so every stored dashboard keeps its current behaviour.
    stack_question_id = serializers.IntegerField(required=False)
    # The number question whose aggregate becomes the bar height.
    # Absent means "count rows", which is what every stored dashboard
    # does (VIZ-015.b).
    value_question_id = serializers.IntegerField(required=False)
    sum_by = serializers.ChoiceField(
        choices=["id", "parent_id"],
        required=False,
        allow_null=True,
    )
    value_type = serializers.ChoiceField(
        choices=list(VALID_VALUE_TYPE),
        default="number",
    )
    repeat_agg = serializers.ChoiceField(
        choices=list(VALID_REPEAT_AGG),
        default="average",
    )
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    date_question_id = serializers.IntegerField(required=False)
    administration_id = serializers.IntegerField(required=False)
    mode = serializers.ChoiceField(
        choices=["scatter"], required=False,
    )
    question_y = serializers.IntegerField(required=False)
    option_value = serializers.CharField(required=False)
    criteria = serializers.CharField(required=False)
    include_unanswered = serializers.BooleanField(
        required=False,
        default=False,
    )
    include_empty = serializers.BooleanField(
        required=False,
        default=False,
    )

    def validate_criteria(self, value):
        try:
            return parse_criteria_string(
                value, VALID_VALUES_CRITERIA_TYPES,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_form_id(self, value):
        if not Forms.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                f"Form {value} not found."
            )
        return value

    def validate(self, data):
        form_id = data.get("form_id")
        question_id = data.get("question_id")
        stack_by = data.get("stack_by")
        group_by = data.get("group_by")

        # Validate question belongs to form and is supported type
        if question_id:
            question = Questions.objects.filter(
                pk=question_id,
                form_id=form_id,
            ).first()
            if not question:
                raise serializers.ValidationError({
                    "question_id": (
                        f"Question {question_id} not found"
                        f" on form {form_id}."
                    ),
                })
            if question.type not in SUPPORTED_QUESTION_TYPES:
                raise serializers.ValidationError({
                    "question_id": (
                        f"Question type {question.type}"
                        " is not supported."
                    ),
                })
            data["question"] = question

        # Validate question_y for scatter mode
        question_y_id = data.get("question_y")
        if question_y_id:
            question_y = Questions.objects.filter(
                pk=question_y_id,
                form_id=form_id,
            ).first()
            if not question_y:
                raise serializers.ValidationError({
                    "question_y": (
                        f"Question {question_y_id} not found"
                        f" on form {form_id}."
                    ),
                })
            if question_y.type != QuestionTypes.number:
                raise serializers.ValidationError({
                    "question_y": (
                        f"Question {question_y_id} must be"
                        " a number type for scatter plots."
                    ),
                })
            data["question_y_obj"] = question_y

        # Split criteria into same-form and parent-form buckets.
        # qids on form_id → criteria; qids on parent form → parent_criteria.
        criteria = data.get("criteria") or []
        if criteria:
            qids = {c["parts"][0] for c in criteria}
            on_form = set(
                Questions.objects.filter(
                    pk__in=qids, form_id=form_id,
                ).values_list("pk", flat=True)
            )
            remaining = qids - on_form
            parent_form = Forms.objects.filter(
                pk=form_id,
            ).values_list("parent_id", flat=True).first()
            on_parent = set()
            if remaining and parent_form:
                on_parent = set(
                    Questions.objects.filter(
                        pk__in=remaining,
                        form_id=parent_form,
                    ).values_list("pk", flat=True)
                )
            unknown = remaining - on_parent
            if unknown:
                raise serializers.ValidationError({
                    "criteria": (
                        "question_id(s) not on form "
                        f"{form_id} or its parent: "
                        f"{sorted(unknown)}"
                    ),
                })
            data["criteria"] = [
                c for c in criteria
                if c["parts"][0] in on_form
            ] or None
            data["parent_criteria"] = [
                c for c in criteria
                if c["parts"][0] in on_parent
            ] or None

        # stack_by requires group_by and question_id
        if stack_by:
            if not group_by:
                raise serializers.ValidationError({
                    "stack_by": "stack_by requires group_by.",
                })
            if not question_id:
                raise serializers.ValidationError({
                    "stack_by": "stack_by requires question_id.",
                })

        stack_question_id = data.get("stack_question_id")
        if stack_question_id and stack_question_id == question_id:
            # The self-stack that plain stack_by=option already means.
            # Normalised away first, and unconditionally: naming your own
            # question is not the cross-tab, so none of the cross-tab's
            # rules below should judge it.
            data.pop("stack_question_id", None)
            stack_question_id = None
        if stack_question_id:
            if stack_by != "option":
                # stack_by=parent_id stacks by site, not by options.
                # Ignoring the field would ship a chart that is not
                # what the config says.
                raise serializers.ValidationError({
                    "stack_question_id": (
                        "stack_question_id requires stack_by=option."
                    ),
                })
            if group_by != "option":
                # The cross-tab is the only shape where BOTH questions
                # are read. Grouping by month or by site makes the
                # measured question contribute nothing, so the chart is
                # entirely about the stacking question -- which is the
                # same chart as measuring that question directly, and
                # leaves the Question control looking broken.
                raise serializers.ValidationError({
                    "stack_question_id": (
                        "stack_question_id requires group_by=option."
                    ),
                })
            if data.get("option_value"):
                # handle_option_question returns from its option_value
                # branches before it reaches the stack_by test, so the
                # pair would silently drop the stacking.
                raise serializers.ValidationError({
                    "stack_question_id": (
                        "option_value cannot be combined with"
                        " stack_question_id."
                    ),
                })
            stack_question = Questions.objects.filter(
                pk=stack_question_id,
                form_id=form_id,
            ).first()
            if not stack_question:
                raise serializers.ValidationError({
                    "stack_question_id": (
                        f"Question {stack_question_id} not found"
                        f" on form {form_id}."
                    ),
                })
            if stack_question.type not in STACK_QUESTION_TYPES:
                raise serializers.ValidationError({
                    "stack_question_id": (
                        "stack question must be an option or"
                        " multiple_option question."
                    ),
                })
            data["stack_question"] = stack_question

        value_question_id = data.get("value_question_id")
        if value_question_id:
            if not question or question.type not in STACK_QUESTION_TYPES:
                # The value supplies the HEIGHT; the measured question
                # supplies the bars. With a number question there are no
                # bars to give a height to, and the two would fight.
                raise serializers.ValidationError({
                    "value_question_id": (
                        "value_question_id requires an option or"
                        " multiple_option question_id."
                    ),
                })
            if (
                data.get("value_type") == "percentage"
                and data.get("repeat_agg") != "sum"
            ):
                # A percentage needs a denominator that is a total of the
                # same quantity. Under `sum` the bar's own total is one:
                # "of the households this agency serves, 85% are under an
                # approved plan". Under average/max/min/last there is no
                # such total -- a sum of averages is not a quantity -- so
                # the only honest denominators left are submission
                # counts, which would divide money by rows (D-2).
                raise serializers.ValidationError({
                    "value_question_id": (
                        "value_type=percentage requires repeat_agg=sum"
                        " when a value_question_id is given."
                    ),
                })
            if data.get("include_unanswered") or data.get("include_empty"):
                # Both add a bucket of PARENTS -- "No information
                # available" -- to a chart whose other bars are sums of a
                # number question, and both make the percentage
                # denominator a parent count. A row of sites cannot join
                # a chart of households at any aggregation.
                raise serializers.ValidationError({
                    "value_question_id": (
                        "value_question_id cannot be combined with"
                        " include_unanswered or include_empty."
                    ),
                })
            value_question = Questions.objects.filter(
                pk=value_question_id,
                form_id=form_id,
            ).first()
            if not value_question:
                raise serializers.ValidationError({
                    "value_question_id": (
                        f"Question {value_question_id} not found"
                        f" on form {form_id}."
                    ),
                })
            if value_question.type != QuestionTypes.number:
                raise serializers.ValidationError({
                    "value_question_id": (
                        "value question must be a number question."
                    ),
                })
            stack_question = data.get("stack_question")
            stack_is_multi = (
                stack_question.type == QuestionTypes.multiple_option
                if stack_question
                else question.type == QuestionTypes.multiple_option
            )
            if (
                data.get("repeat_agg") == "sum"
                and stack_by
                and stack_is_multi
            ):
                # A submission selecting three options contributes its
                # full value to each, which is right for an average and
                # wrong for a sum: the bar would total three times the
                # money that exists, and a stacked bar reads as a
                # partition of a whole (D-1).
                raise serializers.ValidationError({
                    "repeat_agg": (
                        "sum cannot be combined with a multiple_option"
                        " split; use average, max or min."
                    ),
                })
            data["value_question"] = value_question

        return data


class EscalationFilterSerializer(serializers.Serializer):
    """Validates query parameters for /visualization/escalation.

    Criteria format: comma-separated, colon-delimited.
      option_equals:{qid}:{value}
      threshold_gt:{qid}:{value}
      threshold_lt:{qid}:{value}
      overdue:{completion_qid}:{deadline_qid}

    Columns format: comma-separated, colon-delimited.
      {key}:parent_name
      {key}:administration
      {key}:answer:{qid}
      {key}:latest_date:{date_qid}
    """

    monitoring_form_id = serializers.IntegerField(required=True)
    # Optional: the criteria grammar NARROWS a list of datapoints, it does
    # not define one. Requiring it came from the Fiji escalation table,
    # whose only question was "which sites need attention"; a dashboard
    # table asks for the plain list just as often. The compute layer has
    # always handled it — build_escalation_criteria_filter([]) is an empty
    # Q() — so this only stops the request being refused before it gets
    # there. Malformed criteria are still rejected.
    criteria = serializers.CharField(
        required=False, allow_blank=True, default="",
    )
    columns = serializers.CharField(required=True)
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(
        default=20, min_value=1, max_value=100,
    )
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    date_question_id = serializers.IntegerField(required=False)
    administration_id = serializers.IntegerField(required=False)
    filter_criteria = serializers.CharField(required=False)

    def validate_filter_criteria(self, value):
        try:
            return parse_criteria_string(
                value, VALID_VALUES_CRITERIA_TYPES,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_criteria(self, value):
        """Parse and validate criteria string."""
        if not value:
            # Not a malformed criteria string — the absence of one.
            # Splitting "" on "," yields [""], which would fail the
            # format check below and turn "no conditions" into a 400.
            return []
        parsed = []
        for item in value.split(","):
            parts = item.strip().split(":")
            if len(parts) < 3:
                raise serializers.ValidationError(
                    f"Invalid criteria format: '{item}'."
                    " Expected type:qid:value"
                )
            ctype = parts[0]
            if ctype not in VALID_CRITERIA_TYPES:
                raise serializers.ValidationError(
                    f"Invalid criteria type: '{ctype}'."
                    f" Options: {VALID_CRITERIA_TYPES}"
                )

            try:
                if ctype == "option_equals":
                    qid = int(parts[1])
                    normalized = [qid, parts[2]]
                elif ctype in ("threshold_gt", "threshold_lt"):
                    qid = int(parts[1])
                    threshold = float(parts[2])
                    normalized = [qid, threshold]
                elif ctype == "overdue":
                    completion_qid = int(parts[1])
                    deadline_qid = int(parts[2])
                    normalized = [completion_qid, deadline_qid]
            except ValueError:
                raise serializers.ValidationError(
                    f"Invalid numeric value in criteria: '{item}'."
                )

            parsed.append({
                "type": ctype,
                "parts": normalized,
            })
        return parsed

    def validate_columns(self, value):
        """Parse and validate columns string."""
        qid_required_sources = {
            "answer", "parent_answer", "latest_date",
        }
        parsed = []
        for item in value.split(","):
            parts = item.strip().split(":")
            if len(parts) < 2:
                raise serializers.ValidationError(
                    f"Invalid column format: '{item}'."
                    " Expected key:source[:qid]"
                )
            key = parts[0]
            source = parts[1]
            if source not in VALID_COLUMN_SOURCES:
                raise serializers.ValidationError(
                    f"Invalid column source: '{source}'."
                    f" Options: {VALID_COLUMN_SOURCES}"
                )
            col = {"key": key, "source": source}
            if source in qid_required_sources and len(parts) < 3:
                raise serializers.ValidationError(
                    f"Column source '{source}' requires a"
                    f" question_id: '{item}'"
                )
            if len(parts) > 2:
                try:
                    col["question_id"] = int(parts[2])
                except ValueError:
                    raise serializers.ValidationError(
                        f"Invalid question_id in column: '{item}'."
                    )
            parsed.append(col)
        return parsed


# -- Response serializers (documentation only) --------------------
#
# These serializers describe the shape of JSON bodies returned by
# the dashboard endpoints. They are referenced from @extend_schema
# `responses=...` to replace Swagger's "No response body" with a
# concrete schema, and live alongside the request serializers for
# locality. None of them are used for actual DRF serialization —
# the views build plain dicts — so they only need field + type
# metadata that drf-spectacular can introspect.


class ValuesDataItemSerializer(serializers.Serializer):
    """One row in the /values `data` array.

    Shape varies with `group_by`:
    - none / stack_by: extra numeric columns are keyed dynamically,
      so downstream readers should treat unknown keys as stack cells.
    - option: `group` + `color` are populated.
    - month / date: `group` is the machine-readable bucket key.
    """

    value = serializers.FloatField(
        required=False, allow_null=True,
        help_text="Numeric aggregate (or percentage when requested).",
    )
    label = serializers.CharField(
        required=False,
        help_text="Human-readable label for this row.",
    )
    group = serializers.CharField(
        required=False,
        help_text=(
            "Machine-readable key (option value, YYYY-MM, parent id,"
            " …). Stable across translations."
        ),
    )
    color = serializers.CharField(
        required=False,
        help_text=(
            "Hex color from QuestionOptions.color"
            " (only when group_by=option)."
        ),
    )


class ValuesResponseSerializer(serializers.Serializer):
    """/visualization/values response envelope.

    For stacked responses (`stack_by=option|parent_id`), each row in
    `data` additionally carries one numeric column per stack — those
    keys are dynamic and therefore not enumerable here. `stack_labels`
    and `colors` are only present in that mode.
    """

    data = ValuesDataItemSerializer(many=True)
    labels = serializers.ListField(
        child=serializers.CharField(),
        help_text=(
            "Ordered axis / legend labels — parallel to `data[].label`."
        ),
    )
    stack_labels = serializers.ListField(
        child=serializers.CharField(), required=False,
        help_text="Legend entries. Present only when stack_by is set.",
    )
    colors = serializers.ListField(
        child=serializers.CharField(), required=False,
        help_text="Per-stack colors when stack_by=option.",
    )


class EscalationResultItemSerializer(serializers.Serializer):
    """One row from /escalation `results`.

    Column keys are driven by the request's `columns=` param, so only
    `id` is guaranteed. Other keys are documented per column in the
    API spec; values are strings, numbers, or null.
    """

    id = serializers.IntegerField()


class EscalationResponseSerializer(serializers.Serializer):
    """/visualization/escalation paginated envelope."""

    count = serializers.IntegerField()
    next = serializers.CharField(
        allow_null=True, required=False,
    )
    previous = serializers.CharField(
        allow_null=True, required=False,
    )
    results = EscalationResultItemSerializer(many=True)
