# =========================================================
# Dashboard builder: save-time rules (VIZ-005)
# =========================================================
# Under file-based configs a human reviewed every dashboard before it
# shipped. Under tenant-authored ones nobody will, so every rule in
# VIZ-001 §4.5 is enforced here, before a row is written: a dashboard
# that saves is a dashboard that renders.
#
# Everything in this module is plain functions over dicts. The viewset
# turns what they return into HTTP; nothing here imports DRF.

import re

from django.utils.text import slugify

from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_visualization.constants import (
    SUPPORTED_QUESTION_TYPES,
    VALID_COLUMN_SOURCES,
    VALID_CRITERIA_TYPES,
    VALID_GROUP_BY,
    VALID_REPEAT_AGG,
    VALID_STACK_BY,
    VALID_VALUE_TYPE,
    WidgetTypes,
)
from api.v1.v1_visualization.models import DashboardWidget

# VIZ-001 §4.2. The server never interprets `measure` — VIZ-008 expands
# it — but it does insist the word is one of the two that exist.
VALID_MEASURES = {"current_state", "all_submissions"}

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

WIDGET_TYPE_IDS = {
    name: value for value, name in WidgetTypes.FieldStr.items()
}


def _error(message, widget_index=None, field=None):
    """Shape the builder already parses.

    DashboardBuilder.handleSave highlights widgets[widget_index] when
    the key is a number and falls back to a global message when it is
    absent, so a dashboard-level failure must omit the key rather than
    send null.
    """
    error = {"message": message}
    if widget_index is not None:
        error["widget_index"] = widget_index
    if field is not None:
        error["field"] = field
    return error


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# =========================================================
# Slugs
# =========================================================
# Derived from the name at create and never changed afterwards: a slug
# is the dashboard's URL, and re-slugging on rename would break every
# link for a cosmetic edit.


def derive_slug(name, requested=None):
    return (requested or "").strip() or slugify(name or "")


def suggest_slug(slug, queryset):
    """First free "<slug>-N" among the caller's live dashboards."""
    suffix = 2
    while queryset.filter(slug="{0}-{1}".format(slug, suffix)).exists():
        suffix += 1
    return "{0}-{1}".format(slug, suffix)


# =========================================================
# Validation
# =========================================================


def validate_dashboard_payload(data, user, dashboard=None):
    """Return None when the payload is safe to store, else an error.

    `dashboard` is None on create and the instance on update. The two
    paths differ in exactly two ways: create resolves and checks
    `root_form`, update refuses to change it.
    """
    forms = Forms.objects.for_user(user)

    if dashboard is None:
        if not (data.get("name") or "").strip():
            return _error("name is required", field="name")
        root_form = forms.filter(pk=_as_int(data.get("root_form"))).first()
        if root_form is None:
            return _error("root_form not found", field="root_form")
        if (
            root_form.type != FormTypes.registration
            or root_form.parent_id is not None
        ):
            return _error(
                "root_form must be a registration form with no parent",
                field="root_form",
            )
        live_widget_ids = set()
    else:
        requested_root = _as_int(data.get("root_form"))
        if (
            requested_root is not None
            and requested_root != dashboard.root_form_id
        ):
            # D-3: changing the data source orphans every widget, so
            # this is a refusal, not a cascading rewrite.
            return _error(
                "root_form cannot be changed after creation",
                field="root_form",
            )
        root_form = dashboard.root_form
        live_widget_ids = set(
            dashboard.widgets.values_list("id", flat=True)
        )

    questions = Questions.objects.for_user(user)
    for index, widget in enumerate(data.get("widgets") or []):
        error = _validate_widget(
            widget, index, root_form, forms, questions, live_widget_ids
        )
        if error:
            return error
    return None


def _validate_widget(
    widget, index, root_form, forms, questions, live_widget_ids
):
    widget_id = widget.get("id")
    if widget_id is not None and widget_id not in live_widget_ids:
        # A stale canvas must not be able to adopt another dashboard's
        # widget row by guessing its id.
        return _error(
            "widget id does not belong to this dashboard", index, "id"
        )

    type_name = widget.get("type")
    if type_name not in WIDGET_TYPE_IDS:
        return _error(
            "unknown widget type: {0!r}".format(type_name), index, "type"
        )

    col_span = widget.get("col_span", 24)
    if not isinstance(col_span, int) or not 1 <= col_span <= 24:
        return _error(
            "col_span must be between 1 and 24", index, "col_span"
        )

    config = widget.get("config") or {}

    form = None
    form_id = widget.get("form")
    if form_id is not None:
        # Tenant before family: a form belonging to someone else is
        # "not found", never "outside the family" — the second message
        # would confirm the id exists somewhere.
        form = forms.filter(pk=_as_int(form_id)).first()
        if form is None:
            return _error("form not found", index, "form")
        in_family = (
            form.id == root_form.id or form.parent_id == root_form.id
        )
        if not in_family:
            # sum_by=parent_id and monitoring=latest are defined
            # relative to a known registration form, so a widget
            # outside the family renders numbers that look fine and
            # are not.
            return _error(
                "form must be the dashboard's root form or one of its "
                "monitoring forms",
                index,
                "form",
            )

    question_id = widget.get("question")
    if question_id is not None:
        question = questions.filter(pk=_as_int(question_id)).first()
        if question is None:
            return _error("question not found", index, "question")
        if form is None or question.form_id != form.id:
            return _error(
                "question must belong to the widget's form",
                index,
                "question",
            )
        if question.type not in SUPPORTED_QUESTION_TYPES:
            # Answers stores numerics in `value`, choices in `options`
            # and everything else in `name`, so only these four types
            # are aggregatable at all.
            return _error(
                "question type is not aggregatable", index, "question"
            )

    measure = config.get("measure")
    if measure is not None:
        if measure not in VALID_MEASURES:
            return _error(
                "unknown measure: {0!r}".format(measure),
                index,
                "config.measure",
            )
        if measure == "current_state" and (
            form is None or form.type != FormTypes.monitoring
        ):
            return _error(
                "measure current_state requires a monitoring form",
                index,
                "config.measure",
            )

    if config.get("stack_by") and not (
        config.get("group_by") and question_id
    ):
        return _error(
            "stack_by requires group_by and a question",
            index,
            "config.stack_by",
        )

    # Vocabularies the values endpoint already enforces at render time.
    # Checking them here turns a broken dashboard into a refused save.
    for key, allowed in (
        ("group_by", VALID_GROUP_BY),
        ("stack_by", VALID_STACK_BY),
        ("value_type", VALID_VALUE_TYPE),
        ("repeat_agg", VALID_REPEAT_AGG),
    ):
        value = config.get(key)
        if value and value not in allowed:
            return _error(
                "{0} must be one of: {1}".format(
                    key, ", ".join(sorted(allowed))
                ),
                index,
                "config.{0}".format(key),
            )

    if type_name == "table":
        for column in config.get("columns") or []:
            if column.get("source") not in VALID_COLUMN_SOURCES:
                return _error(
                    "column source must be one of: {0}".format(
                        ", ".join(sorted(VALID_COLUMN_SOURCES))
                    ),
                    index,
                    "config.columns",
                )
        for criterion in config.get("criteria") or []:
            if criterion.get("type") not in VALID_CRITERIA_TYPES:
                return _error(
                    "criteria type must be one of: {0}".format(
                        ", ".join(sorted(VALID_CRITERIA_TYPES))
                    ),
                    index,
                    "config.criteria",
                )
    return None


# =========================================================
# Writes
# =========================================================


def apply_widgets(dashboard, widgets):
    """Replace the widget array wholesale.

    The builder's canvas treats add, remove and reorder as local edits
    until save, so the payload is the whole array: rows carrying an id
    update in place, rows without are created, stored rows the payload
    omits are deleted.

    Assumes validate_dashboard_payload() has already passed and that
    the caller holds the transaction — a half-applied array is a
    dashboard that renders wrong.
    """
    existing = {w.id: w for w in dashboard.widgets.all()}
    kept = set()
    for index, payload in enumerate(widgets):
        fields = {
            "order": payload.get("order", index + 1),
            "type": WIDGET_TYPE_IDS[payload["type"]],
            "col_span": payload.get("col_span", 24),
            "title": payload.get("title"),
            "color": payload.get("color"),
            "form_id": payload.get("form"),
            "question_id": payload.get("question"),
            "config": payload.get("config") or {},
        }
        widget = existing.get(payload.get("id"))
        if widget is None:
            DashboardWidget.objects.create(dashboard=dashboard, **fields)
            continue
        for key, value in fields.items():
            setattr(widget, key, value)
        widget.save()
        kept.add(widget.id)

    for widget_id, widget in existing.items():
        if widget_id not in kept:
            widget.delete()
