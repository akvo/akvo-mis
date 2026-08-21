from rest_framework import serializers
from api.v1.v1_visualization.constants import (
    VALID_GROUP_BY,
    VALID_MONITORING,
    VALID_VALUE_TYPE,
    VALID_REPEAT_AGG,
    VALID_STACK_BY,
    VALID_CRITERIA_TYPES,
    VALID_VALUES_CRITERIA_TYPES,
    VALID_COLUMN_SOURCES,
    VALID_PROGRESS_FORMULAS,
    SUPPORTED_QUESTION_TYPES,
)
from api.v1.v1_visualization.functions import parse_criteria_string
from api.v1.v1_forms.models import Forms, Questions
from utils.tenant_scoped_model import acting_user


# =========================================================
# The form family
# =========================================================
# /escalation and /progress both name a registration form in the URL
# and a monitoring form in the query string. The view resolves the
# first through Forms.objects.for_user() before building its
# serializer, and the family below narrows the second to that form's
# children.
#
# Membership takes TWO conditions, not one. Being a child of a
# tenant-resolved parent does NOT imply the same tenant: Forms.tenant
# is an independent column rather than something inherited through
# `parent`, and FormViewSet.update() repoints a form's parent FK
# straight from request data with no tenant check
# (v1_forms/functions.py). So another tenant's form can be made a
# child of the caller's, and a family derived from `children` alone
# would accept it — both as monitoring_form_id and as a home for
# question ids. The tenant filter here is what closes that; it is not
# redundant with the view's for_user(). Same cause as the comment in
# views.py on the monitoring-stats question family.
#
# The view's ordering is still load-bearing, which is why callers read
# parent_form out of the context with no fallback.


def check_monitoring_form(parent_form, monitoring_form_id):
    """Assert monitoring_form_id is in parent_form's family.

    Returns the family ids so a caller can go on to validate question
    ids against them.
    """
    family_ids = [parent_form.id] + list(
        parent_form.children.filter(
            tenant_id=parent_form.tenant_id,
        ).values_list("id", flat=True)
    )
    if monitoring_form_id not in family_ids:
        raise serializers.ValidationError({
            "monitoring_form_id": (
                f"Form {monitoring_form_id} is not a monitoring"
                f" form of form {parent_form.id}."
            ),
        })
    return family_ids


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

    def validate(self, data):
        form_id = data.get("form_id")
        question_id = data.get("question_id")
        stack_by = data.get("stack_by")
        group_by = data.get("group_by")

        # Every question lookup below is scoped to the caller's tenant.
        # This serializer runs BEFORE the view resolves form_id through
        # Forms.objects.for_user(), so an unscoped lookup answers for
        # forms the caller cannot see: a foreign form's own question
        # would validate (the view then 404s) while a form that exists
        # nowhere could never match one (400). That 400-vs-404 split is
        # an existence oracle over other tenants' forms. Scoping the
        # questions makes both shapes answer 400.
        caller = acting_user(self.context)

        # Validate question belongs to form and is supported type
        if question_id:
            question = Questions.objects.for_user(caller).filter(
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

        # Split criteria into same-form and parent-form buckets.
        # qids on form_id → criteria; qids on parent form → parent_criteria.
        criteria = data.get("criteria") or []
        if criteria:
            qids = {c["parts"][0] for c in criteria}
            on_form = set(
                Questions.objects.for_user(caller).filter(
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
                    Questions.objects.for_user(caller).filter(
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
    criteria = serializers.CharField(required=True)
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

    def validate(self, data):
        """Reject every id that is not part of the form family.

        The family is the caller's registration form plus the
        monitoring children it shares a tenant with — see
        check_monitoring_form for why both halves are needed.

        parent_form is read from the context without a fallback so a
        caller that skips the view's tenant-scoped lookup fails loudly
        instead of validating nothing.
        """
        parent_form = self.context["parent_form"]
        family_ids = check_monitoring_form(
            parent_form, data["monitoring_form_id"]
        )

        # Group the question ids by the parameter that carried them, so
        # a rejection names the half that actually failed.
        by_field = {}

        # validate_criteria normalises each item to {"type", "parts"}.
        # option_equals and the two thresholds put their only question
        # id in parts[0], but "overdue" carries two — completion and
        # deadline — and a foreign deadline id rides through if only
        # the first is checked.
        criteria_ids = set()
        for criterion in data["criteria"]:
            if criterion["type"] == "overdue":
                criteria_ids.update(criterion["parts"][:2])
            else:
                criteria_ids.add(criterion["parts"][0])
        by_field["criteria"] = criteria_ids

        # validate_columns attaches question_id only for the answer,
        # parent_answer and latest_date sources. Tested against None
        # rather than truthiness: id 0 is falsy but still an id, and
        # skipping it would skip the check rather than the column.
        by_field["columns"] = {
            col["question_id"]
            for col in data["columns"]
            if col.get("question_id") is not None
        }

        # date_question_id names a question too, and it reaches the
        # same queries the others do.
        date_question_id = data.get("date_question_id")
        if date_question_id is not None:
            by_field["date_question_id"] = {date_question_id}

        question_ids = set().union(*by_field.values())
        found = set(
            Questions.objects.filter(
                pk__in=question_ids,
                form_id__in=family_ids,
            ).values_list("pk", flat=True)
        )
        errors = {}
        for field, ids in by_field.items():
            missing = ids - found
            if missing:
                errors[field] = (
                    "question_id(s) not on form"
                    f" {parent_form.id} or its monitoring forms:"
                    f" {sorted(missing)}"
                )
        if errors:
            raise serializers.ValidationError(errors)
        return data


class ProgressFilterSerializer(serializers.Serializer):
    """Validates query parameters for /visualization/progress.

    Components format: comma-separated, colon-delimited.
      {key}:{formula}:{qid1}:{qid2}:...:{total_items}

    Example:
      base:any_yes:111:222:333,tank:completed_binary:444,
      pipes:ratio:555,security:multi_select_proportion:666:3
    """

    monitoring_form_id = serializers.IntegerField(
        required=True
    )
    components = serializers.CharField(required=True)
    filter_question_id = serializers.IntegerField(
        required=False
    )
    filter_option_value = serializers.CharField(
        required=False
    )
    scope_question_id = serializers.IntegerField(
        required=False
    )
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    date_question_id = serializers.IntegerField(
        required=False
    )
    administration_id = serializers.IntegerField(
        required=False
    )
    criteria = serializers.CharField(required=False)

    def validate_criteria(self, value):
        try:
            return parse_criteria_string(
                value, VALID_VALUES_CRITERIA_TYPES,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_components(self, value):
        """Parse and validate components string.

        Format: key:formula:qid[:qid...][@type1|type2|...]
        The optional @-suffix lists applicable project types.
        """
        parsed = []
        for item in value.split(","):
            raw = item.strip()

            # Split off optional @applicable_types suffix
            applicable_types = None
            if "@" in raw:
                raw, types_str = raw.split("@", 1)
                applicable_types = [
                    t.strip() for t in types_str.split("|")
                    if t.strip()
                ]

            parts = raw.split(":")
            if len(parts) < 3:
                raise serializers.ValidationError(
                    f"Invalid component format: '{item}'."
                    " Expected key:formula:qid[:qid...]"
                )
            key = parts[0]
            formula = parts[1]
            if formula not in VALID_PROGRESS_FORMULAS:
                raise serializers.ValidationError(
                    f"Invalid formula: '{formula}'."
                    f" Options: {VALID_PROGRESS_FORMULAS}"
                )

            comp = {"key": key, "formula": formula}

            if formula == "multi_select_proportion":
                # Last segment is total_items
                if len(parts) < 4:
                    raise serializers.ValidationError(
                        f"{formula} requires total_items:"
                        f" '{item}'"
                    )
                comp["question_ids"] = [
                    int(q) for q in parts[2:-1]
                ]
                try:
                    total_items = int(parts[-1])
                except ValueError:
                    raise serializers.ValidationError(
                        f"Invalid total_items in component: '{item}'."
                    )
                if total_items < 1:
                    raise serializers.ValidationError(
                        f"total_items must be >= 1: '{item}'"
                    )
                comp["total_items"] = total_items
            elif formula == "ratio":
                # ratio requires implemented_qid:planned_qid
                if len(parts) != 4:
                    raise serializers.ValidationError(
                        f"{formula} requires exactly two"
                        " question ids"
                        " (implemented:planned):"
                        f" '{item}'"
                    )
                comp["question_ids"] = [
                    int(parts[2]), int(parts[3]),
                ]
            else:
                comp["question_ids"] = [
                    int(q) for q in parts[2:]
                ]

            if applicable_types:
                comp["applicable_types"] = applicable_types

            parsed.append(comp)
        return parsed

    def validate(self, data):
        """Reject a monitoring_form_id outside the form family.

        The spec requires this on /progress as well as /escalation.
        The component question ids are its documented residual and are
        deliberately not checked here — barrier two neuters them.

        "Family" means a child of the resolved parent that also shares
        its tenant; see check_monitoring_form for why the second half
        is not redundant.

        parent_form is read without a fallback for the same reason as
        on escalation: a caller that builds this serializer before
        resolving the form must fail loudly, not validate nothing.
        """
        check_monitoring_form(
            self.context["parent_form"], data["monitoring_form_id"]
        )
        return data


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


class ProgressHistogramBucketSerializer(serializers.Serializer):
    progress = serializers.CharField(
        help_text="Bucket label, e.g. '0-10%', '11-20%'.",
    )
    count = serializers.IntegerField()


class ProgressDetailItemSerializer(serializers.Serializer):
    """One EPS / parent in the /progress `details` array."""

    label = serializers.CharField()
    group = serializers.CharField(
        help_text="Parent FormData.id as string.",
    )
    components = serializers.DictField(
        child=serializers.FloatField(),
        help_text=(
            "Per-component percent score, keyed by the component"
            " `key` from the request."
        ),
    )
    overall = serializers.FloatField(
        help_text="Average across components, 0-100.",
    )


class ProgressResponseSerializer(serializers.Serializer):
    """/visualization/progress response envelope."""

    histogram = ProgressHistogramBucketSerializer(many=True)
    details = ProgressDetailItemSerializer(many=True)
