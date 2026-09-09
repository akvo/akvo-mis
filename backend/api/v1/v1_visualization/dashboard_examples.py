from drf_spectacular.utils import OpenApiExample

VALUES_EXAMPLES = [
    OpenApiExample(
        name="Count Mode — no grouping",
        summary="Total count; no question_id, no group_by",
        description=(
            "Request: ?form_id=6001\n"
            "Returns a single aggregate row. `labels` is always"
            " ['Total']."
        ),
        value={
            "data": [{"value": 150, "label": "Total"}],
            "labels": ["Total"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Count Mode — grouped by month",
        summary="Submissions per month",
        description=(
            "Request: ?form_id=6001&group_by=month. Each row has a"
            " machine-readable `group` (YYYY-MM) and a human"
            " `label`. Zero-filled if from_date and to_date set."
        ),
        value={
            "data": [
                {
                    "value": 12,
                    "label": "Jan 2025",
                    "group": "2025-01",
                },
                {
                    "value": 8,
                    "label": "Feb 2025",
                    "group": "2025-02",
                },
            ],
            "labels": ["Jan 2025", "Feb 2025"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Option Donut — group_by=option",
        summary="Option breakdown with color and zero-rows",
        description=(
            "Request: ?form_id=6002&question_id=600203"
            "&group_by=option. Every defined option is returned,"
            " including zero-count options (legend stability)."
            " `color` comes from QuestionOptions.color."
        ),
        value={
            "data": [
                {
                    "value": 5,
                    "label": "Active",
                    "group": "active",
                    "color": "#64A73B",
                },
                {
                    "value": 0,
                    "label": "Inactive",
                    "group": "inactive",
                    "color": "#e41a1c",
                },
            ],
            "labels": ["Active", "Inactive"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Option Percentage",
        summary="Donut with value_type=percentage",
        description=(
            "Slice values expressed as percentages summing to 100."
        ),
        value={
            "data": [
                {
                    "value": 66.67,
                    "label": "Active",
                    "group": "active",
                    "color": "#64A73B",
                },
                {
                    "value": 33.33,
                    "label": "Inactive",
                    "group": "inactive",
                    "color": "#e41a1c",
                },
            ],
            "labels": ["Active", "Inactive"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="KPI — filtered by option_value",
        summary="Single-number KPI for a specific option",
        description=(
            "Request: ?form_id=6002&question_id=600203"
            "&option_value=active. Returns a one-row count or"
            " percentage."
        ),
        value={
            "data": [{"value": 42, "label": "active"}],
            "labels": ["active"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Stacked Bar — stack_by=option",
        summary="Operational status per month, stacked",
        description=(
            "Request: ?form_id=6002&question_id=600203"
            "&group_by=month&stack_by=option&monitoring=all."
            " Each row carries one column per option;"
            " `stack_labels` + `colors` drive the legend."
        ),
        value={
            "data": [
                {
                    "group": "2025-01",
                    "label": "Jan 2025",
                    "Active": 3,
                    "Inactive": 1,
                },
                {
                    "group": "2025-02",
                    "label": "Feb 2025",
                    "Active": 5,
                    "Inactive": 2,
                },
            ],
            "labels": ["Jan 2025", "Feb 2025"],
            "stack_labels": ["Active", "Inactive"],
            "colors": ["#64A73B", "#e41a1c"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Cross-tab — stack_by=option + stack_question_id",
        summary="One question's options split by another's",
        description=(
            "Request: ?form_id=6002&question_id=600203"
            "&group_by=option&stack_by=option"
            "&stack_question_id=600204&monitoring=all."
            " Bars are the measured question's options, columns"
            " the stacking question's. Bars are ordered by total"
            " descending; `stack_labels` stays in the stacking"
            " question's own option order, so the legend does not"
            " move when the data does. Omitting"
            " `stack_question_id` stacks by the measured"
            " question's own options, which is the older"
            " behaviour and unchanged."
        ),
        value={
            "data": [
                {
                    "group": "active",
                    "label": "Active",
                    "Feature X": 1,
                    "Feature Y": 2,
                    "Feature Z": 1,
                },
                {
                    "group": "pending",
                    "label": "Pending",
                    "Feature X": 1,
                    "Feature Y": 1,
                    "Feature Z": 1,
                },
                {
                    "group": "inactive",
                    "label": "Inactive",
                    "Feature X": 1,
                    "Feature Y": 0,
                    "Feature Z": 1,
                },
            ],
            "labels": ["Active", "Pending", "Inactive"],
            "stack_labels": [
                "Feature X", "Feature Y", "Feature Z",
            ],
            "colors": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Multi-line — stack_by=parent_id",
        summary="Number question per parent over time",
        description=(
            "Request: ?form_id=6002&question_id=600202"
            "&group_by=month&stack_by=parent_id. Each row is a"
            " month; each parent's name becomes a column."
            " `stack_labels` lists the parents."
        ),
        value={
            "data": [
                {
                    "month": "Jan 2025",
                    "Site Alpha": 10.0,
                    "Site Beta": 30.0,
                },
                {
                    "month": "Feb 2025",
                    "Site Alpha": 12.5,
                    "Site Beta": 28.0,
                },
            ],
            "labels": ["Jan 2025", "Feb 2025"],
            "stack_labels": ["Site Alpha", "Site Beta"],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Validation error",
        summary="400 for malformed criteria / missing form",
        value={
            "message": (
                "Invalid criteria type: 'option_matches'."
            ),
        },
        response_only=True,
        status_codes=["400"],
    ),
]

ESCALATION_EXAMPLES = [
    OpenApiExample(
        name="Escalated sites — inactive",
        summary="Paginated table with criteria + columns",
        description=(
            "Request: ?monitoring_form_id=6002"
            "&criteria=option_equals:600203:inactive"
            "&columns=name:parent_name,status:answer:600203"
            ",date:latest_date:600201."
            " Column keys in `results[]` follow the request spec."
        ),
        value={
            "count": 2,
            "next": (
                "?monitoring_form_id=6002"
                "&criteria=option_equals:600203:inactive"
                "&page=2"
            ),
            "previous": None,
            "results": [
                {
                    "id": 7200,
                    "name": "Site Alpha",
                    "status": "inactive",
                    "date": "2025-03-10",
                },
                {
                    "id": 7201,
                    "name": "Site Beta",
                    "status": "inactive",
                    "date": "2025-03-15",
                },
            ],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Overdue criterion",
        summary="overdue:completion_qid:deadline_qid",
        description=(
            "Incomplete and past deadline, with admin column."
        ),
        value={
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 7201,
                    "name": "Site Beta",
                    "admin": "Fiji / Central / Suva",
                    "status": "no",
                },
            ],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Empty page",
        summary="No records match the criteria",
        value={
            "count": 0,
            "next": None,
            "previous": None,
            "results": [],
        },
        response_only=True,
    ),
    OpenApiExample(
        name="Validation error",
        summary="400 for missing/malformed criteria or columns",
        value={
            "message": (
                "Invalid criteria format: 'option_equals:600203'."
                " Expected type:qid:value"
            ),
        },
        response_only=True,
        status_codes=["400"],
    ),
]
