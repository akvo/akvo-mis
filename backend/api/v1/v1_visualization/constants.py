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


class DashboardStatus:
    draft = 1
    published = 2

    FieldStr = {
        draft: "draft",
        published: "published",
    }


class DashboardKind:
    """What a dashboard's content *is*.

    `widgets` is built here from DashboardWidget rows against a
    root_form. `embed` is rendered by an external tool from a stored
    snippet. The two are mutually exclusive, enforced by the
    `dashboard_kind_matches_source` check constraint.
    """

    widgets = 1
    embed = 2

    FieldStr = {
        widgets: "widgets",
        embed: "embed",
    }


# Upper bound on a stored embed snippet. Deliberately NOT a column
# limit -- embed_snippet is a TextField -- but a payload bound checked
# in validation, so an oversized paste is a 400 naming the field rather
# than a database error. It is a bound on storage, not an opinion about
# content (spec D-4).
EMBED_SNIPPET_MAX = 20000


class WidgetTypes:
    kpi = 1
    bar = 2
    line = 3
    pie = 4
    table = 5
    map = 6
    section_title = 7
    scatter = 8

    FieldStr = {
        kpi: "kpi",
        bar: "bar",
        line: "line",
        pie: "pie",
        table: "table",
        map: "map",
        section_title: "section_title",
        scatter: "scatter",
    }
