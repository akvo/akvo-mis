from django.db.models import Avg, Sum, Max, Min, Aggregate, FloatField
from api.v1.v1_forms.constants import QuestionTypes


class Last(Aggregate):
    """Aggregate returning the value at the highest repeat index.

    Uses PostgreSQL ARRAY_AGG with ORDER BY to pick the value from
    the last repeat (Answers.index DESC). Intended for use on
    Answers.value within an Answers queryset grouped per data/parent.
    """

    name = "Last"
    function = ""
    template = (
        '(ARRAY_AGG(%(expressions)s ORDER BY "index" DESC))[1]'
    )
    output_field = FloatField()


VALID_GROUP_BY = {"date", "month", "id", "parent_id", "option"}
VALID_MONITORING = {"latest", "all"}
VALID_VALUE_TYPE = {"number", "percentage"}
VALID_REPEAT_AGG = {"average", "sum", "max", "min", "last"}
VALID_STACK_BY = {"option", "parent_id"}
SUPPORTED_QUESTION_TYPES = {
    QuestionTypes.number,
    QuestionTypes.option,
    QuestionTypes.multiple_option,
    QuestionTypes.date,
}
AGG_FUNCS = {
    "average": Avg,
    "sum": Sum,
    "max": Max,
    "min": Min,
    "last": Last,
}

# Escalation criteria types
VALID_CRITERIA_TYPES = {
    "option_equals",
    "threshold_gt",
    "threshold_lt",
    "overdue",
}

# /visualization/values multi-criteria filter types. Shares grammar
# with escalation; `overdue` is excluded because it is table-specific,
# and `option_contains` / `option_in` are added for multiple_option
# filtering. Criteria combine with AND semantics.
VALID_VALUES_CRITERIA_TYPES = {
    "option_equals",
    "option_contains",
    "option_in",
    "threshold_gt",
    "threshold_lt",
}

# Escalation column source types
VALID_COLUMN_SOURCES = {
    "parent_name",
    "administration",
    "answer",
    "parent_answer",
    "latest_date",
}

# Progress formula types
VALID_PROGRESS_FORMULAS = {
    "any_yes",
    "completed_binary",
    "ratio",
    "multi_select_proportion",
}


class DashboardStatus:
    draft = 1
    published = 2

    FieldStr = {
        draft: "draft",
        published: "published",
    }


class DashboardVisibility:
    """Who may read a published dashboard.

    `internal` is every dashboard that exists today and the default for
    every new one: published to the tenant, and a login is required.
    `public` opens it to anonymous readers on the workspace's own
    subdomain — see VIZ-010. Publication and visibility are independent:
    a public draft is visible to nobody until it is published.
    """

    internal = 1
    public = 2

    FieldStr = {
        internal: "internal",
        public: "public",
    }


class WidgetTypes:
    kpi = 1
    bar = 2
    line = 3
    pie = 4
    table = 5
    map = 6
    section_title = 7

    FieldStr = {
        kpi: "kpi",
        bar: "bar",
        line: "line",
        pie: "pie",
        table: "table",
        map: "map",
        section_title: "section_title",
    }
