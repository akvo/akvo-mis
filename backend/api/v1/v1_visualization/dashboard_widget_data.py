"""One stored widget → its data.

VIZ-010 D-3. A public caller names a dashboard slug and a widget id and
nothing else: no `form_id`, no `question_id`, no criteria grammar. Every
parameter the aggregation needs is read from the widget the server already
holds, so there is nothing on the wire to enumerate and no query for an
anonymous caller to author.

That is the whole security argument for the public surface, and it is why
this module exists rather than the public views simply proxying
`/visualization/*`. Proxying would have put a tenant-scoped `form_id` back
on the wire, which is the hole VIZ-003 exists to close.

The same resolver serves the authenticated viewer (VIZ-010 D-4), so the
two paths cannot disagree about what a widget means.
"""
from django.db.models import Q

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_visualization.constants import WidgetTypes
from api.v1.v1_visualization.dashboard_measure import (
    MONITORING_LATEST,
    expand_measure,
)
from api.v1.v1_visualization.escalation_functions import handle_escalation
from api.v1.v1_visualization.formula import (
    evaluate as formula_evaluate,
    pick_latest_repeat,
)
from api.v1.v1_visualization.values_functions import (
    handle_count_mode,
    handle_number_question,
    handle_option_question,
)

# Widget types that carry no data at all.
NO_DATA_TYPES = {WidgetTypes.section_title}

# Column sources the backend refuses without a question id
# (EscalationFilterSerializer.validate_columns). Mirrors the frontend's
# QID_REQUIRED, and for the same reason: an entry the serializer would
# reject is dropped rather than sent, because sending it costs the widget.
QID_REQUIRED = ("answer", "parent_answer", "latest_date")


def _usable_column(col):
    if not (col.get("key") and col.get("source")):
        return False
    if col["source"] in QID_REQUIRED and not col.get("question"):
        return False
    return True


def _usable_criterion(crit):
    # `is not None and != ""` rather than a falsy test: 0 is a legitimate
    # threshold.
    value = crit.get("value")
    return bool(crit.get("type") and crit.get("question")) and (
        value is not None and value != ""
    )


def _parse_columns(config):
    """Columns in the shape handle_escalation expects."""
    parsed = []
    for col in config.get("columns") or []:
        if not _usable_column(col):
            continue
        entry = {"key": col["key"], "source": col["source"]}
        if col.get("question"):
            entry["question_id"] = int(col["question"])
        parsed.append(entry)
    return parsed


def _parse_criteria(config):
    """Criteria in the shape handle_escalation expects.

    Optional since VIZ-009's serializer change: no conditions means every
    datapoint, because the grammar narrows a list rather than defining one.
    """
    parsed = []
    for crit in config.get("criteria") or []:
        if not _usable_criterion(crit):
            continue
        parsed.append(
            {
                "type": crit["type"],
                "parts": [str(crit["question"]), str(crit["value"])],
            }
        )
    return parsed


def _base_params(filters):
    """The only parameters a caller may influence (VIZ-001 §4.4).

    Everything else comes from the stored widget. An administration id is
    validated by the caller against the dashboard's tenant before it gets
    here.
    """
    return {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "administration_id": filters.get("administration_id"),
    }


def _values_data(dashboard, widget, filters):
    form = Forms.objects.filter(pk=widget.get("form")).first()
    if not form:
        return None

    question = None
    if widget.get("question"):
        question = Questions.objects.filter(
            pk=widget["question"], form_id=form.id
        ).first()

    config = widget.get("config") or {}
    params = _base_params(filters)
    params.update(
        {
            "group_by": config.get("group_by"),
            "stack_by": config.get("stack_by"),
            "value_type": config.get("value_type", "number"),
            "repeat_agg": config.get("repeat_agg", "average"),
            "option_value": config.get("option_value"),
            "date_question_id": filters.get("date_question_id"),
            "monitoring": "latest",
            "include_empty": False,
            "include_unanswered": False,
        }
    )
    params.update(expand_measure(widget, dashboard.root_form_id))

    if not question:
        result = handle_count_mode(form, params)
    elif question.type == QuestionTypes.number:
        result = handle_number_question(form, question, params)
    elif question.type in (
        QuestionTypes.option,
        QuestionTypes.multiple_option,
    ):
        result = handle_option_question(form, question, params)
    else:
        result = handle_count_mode(form, params)

    if isinstance(result, dict):
        return result
    data, labels = result
    return {"data": data, "labels": labels}


def _table_data(dashboard, widget, filters):
    columns = _parse_columns(widget.get("config") or {})
    if not columns:
        # Columns are what the request asks for and what the grid draws;
        # without them there is nothing to return.
        return {"count": 0, "next": None, "previous": None, "results": []}

    config = widget.get("config") or {}
    params = _base_params(filters)
    params.update(
        {
            "page": filters.get("page") or 1,
            "page_size": config.get("page_size") or 20,
            "date_question_id": filters.get("date_question_id"),
        }
    )
    return handle_escalation(
        parent_form=dashboard.root_form,
        monitoring_form_id=widget.get("form"),
        criteria=_parse_criteria(config),
        columns=columns,
        params=params,
    )


def _map_points(dashboard, widget, filters):
    """Registration datapoints with coordinates.

    Always the registration form, never `widget.form`: `geo` is captured
    once, when a site is registered, so asking a monitoring form returns an
    empty list every time. The widget's own form is the colour source.

    The authenticated endpoint narrows by the caller's own administration
    role; there is no role to narrow by here, and a public dashboard is
    published for its whole tenant, so the only narrowing is the filter the
    viewer chose.
    """
    root = dashboard.root_form
    queryset = FormData.objects.filter(
        form=root, is_pending=False, is_draft=False, geo__isnull=False
    )

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    monitoring_form_id = widget.get("form")
    is_monitoring = bool(
        monitoring_form_id and monitoring_form_id != root.id
    )

    if is_monitoring and (from_date or to_date):
        child_q = Q(children__form_id=monitoring_form_id)
        if from_date:
            child_q &= Q(children__created__date__gte=from_date)
        if to_date:
            child_q &= Q(children__created__date__lte=to_date)
        queryset = queryset.filter(
            child_q, children__is_pending=False, children__is_draft=False
        ).distinct()
    else:
        if from_date:
            queryset = queryset.filter(created__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created__date__lte=to_date)

    administration_id = filters.get("administration_id")
    if administration_id:
        from api.v1.v1_profile.models import Administration

        adm = Administration.objects.filter(pk=administration_id).first()
        if adm:
            adm_path = f"{adm.path}{adm.id}." if adm.path else f"{adm.id}."
            queryset = queryset.filter(
                Q(administration=adm)
                | Q(administration__path__startswith=adm_path)
            )

    return list(
        queryset.values("id", "name", "geo", "administration_id")
    )


def _map_status(widget, points):
    """Join each point to its status bucket.

    A map draws coordinates from the registration form and colours them by
    an answer on the monitoring form, so it needs a second source. The
    bucket list comes from `config.status_colors`' own keys — they are
    option values, which is exactly what the formula needs — so no form
    metadata has to be fetched.

    This ran in the browser as a second request to /values/formula. It
    moves here for the same reason the measure expansion did: an anonymous
    caller cannot be trusted to author a formula, and a map whose pins are
    all one colour is a wrong answer that looks like a design choice.
    """
    config = widget.get("config") or {}
    values = list((config.get("status_colors") or {}).keys())
    question_id = widget.get("question")
    if not (values and question_id and points):
        # validate_shape() rejects an empty bucket list, and an uncoloured
        # map takes the widget's own accent for every pin.
        return points

    form = Forms.objects.filter(pk=widget.get("form")).first()
    if not form:
        return points

    is_registration = form.parent_id is None
    queryset = form.form_form_data.filter(
        is_pending=False, is_draft=False, parent__isnull=is_registration
    )

    if is_registration:
        id_to_group = {
            row: row for row in queryset.values_list("id", flat=True)
        }
    else:
        latest_by_parent = {}
        for row in queryset.order_by("parent_id", "-created").values(
            "id", "parent_id"
        ):
            latest_by_parent.setdefault(row["parent_id"], row["id"])
        id_to_group = {v: k for k, v in latest_by_parent.items()}

    if not id_to_group:
        return points

    formula = {
        "buckets": [
            {
                "value": value,
                "label": value,
                "all_of": [
                    {
                        "question_id": question_id,
                        "op": "option_equals",
                        "value": value,
                    }
                ],
            }
            for value in values
        ],
        "default": {"value": "_no_info", "label": "_no_info"},
    }

    answers_by_data = {}
    for answer in Answers.objects.filter(
        data_id__in=list(id_to_group.keys())
    ).values("data_id", "question_id", "value", "options", "index"):
        answers_by_data.setdefault(answer["data_id"], []).append(answer)

    by_parent = {}
    for data_id, group in id_to_group.items():
        per_question = pick_latest_repeat(answers_by_data.get(data_id, []))
        by_parent[group] = formula_evaluate(formula, per_question)

    return [
        dict(point, status=by_parent.get(point["id"]))
        for point in points
    ]


def resolve_widget_data(dashboard, widget, filters=None):
    """This widget's data, in the shape its renderer already reads.

    Args:
        dashboard: The Dashboard the widget belongs to. Supplies the
            registration form and, through it, the tenant.
        widget: A widget dict from `published_config` or from live rows.
        filters: The dashboard-level filters only — `from_date`,
            `to_date`, `administration_id`, plus `page` for a table.

    Returns:
        The renderer's input, or None for a widget that needs no request.
    """
    filters = filters or {}
    type_name = widget.get("type")
    # Snapshots store the string; live rows store the integer.
    if isinstance(type_name, int):
        type_name = WidgetTypes.FieldStr.get(type_name)

    if widget.get("is_broken") or type_name == "section_title":
        return None

    if type_name == "table":
        return _table_data(dashboard, widget, filters)
    if type_name == "map":
        return _map_status(
            widget, _map_points(dashboard, widget, filters)
        )
    if type_name in ("kpi", "bar", "line", "pie"):
        if not widget.get("form"):
            # form_id is required by the aggregation, and an unfinished
            # widget is not an error — it simply has nothing to show.
            return None
        return _values_data(dashboard, widget, filters)
    return None


__all__ = [
    "resolve_widget_data",
    "MONITORING_LATEST",
]
