# =========================================================
# Dashboard publish: the snapshot, both directions (VIZ-007)
# =========================================================
# Publish freezes what a dashboard renders; the read namespace serves
# that frozen copy, checked against live rows as it goes out. Both
# directions live in one module so the shape written and the shape read
# cannot drift apart.
#
# Plain functions over dicts, like dashboard_functions.py. Nothing here
# touches a request or a response.

from collections import defaultdict

from django.db.models import Prefetch, Q

from api.v1.v1_forms.models import Forms, QuestionOptions, Questions
from api.v1.v1_visualization.constants import DashboardKind
from api.v1.v1_visualization.dashboard_builder_serializers import (
    DashboardWidgetSerializer,
    serialize_question,
)
from api.v1.v1_visualization.functions import (
    OPTION_TYPES,
    global_filter_scope,
)


def build_snapshot(dashboard):
    """Live content -> the dict stored in `published_config`.

    `default_filters` travels with the widgets (spec D-1). The rule is
    "does editing this change the picture?": retuning the filter bar
    changes the numbers on screen exactly as moving a widget does, so
    both wait for Publish. Identity — name, slug, root_form — is
    deliberately absent, because a corrected typo in a title should not
    require re-publishing work that is not finished.

    The ordering is stated here rather than inherited from
    `DashboardWidget.Meta.ordering`: this is the artefact viewers read,
    and its order must not depend on a Meta attribute a later change
    could quietly reorder.
    """
    if dashboard.kind == DashboardKind.embed:
        # No widgets and no filters: the snippet is the whole of an
        # embed's content, and there is nothing of ours to filter.
        return {"embed_snippet": dashboard.embed_snippet}

    widgets = dashboard.widgets.order_by("order", "id")
    return {
        "default_filters": _snapshot_default_filters(
            dashboard.default_filters or {}, dashboard.root_form_id,
        ),
        "widgets": DashboardWidgetSerializer(widgets, many=True).data,
    }


def _options_prefetch():
    return Prefetch(
        "options", queryset=QuestionOptions.objects.order_by("order", "id"),
    )


def _merge_options(option_lists):
    """One entry per value; differing labels joined with " / " (D-14).

    The first list's order and labels lead; values found only in later
    lists follow, in their order.
    """
    labels = {}
    for options in option_lists:
        for option in options:
            seen = labels.setdefault(option["value"], [])
            if option["label"] not in seen:
                seen.append(option["label"])
    return [
        {"value": value, "label": " / ".join(names)}
        for value, names in labels.items()
    ]


def _snapshot_default_filters(default_filters, root_form_id):
    """VIZ-027 D-7, D-20: the filter bar's filters, with label and options.

    A public viewer cannot read form definitions, so what the bar shows
    travels in the snapshot. Each `{form, name}` entry gets the options of
    every live option question of that name in its scope, merged by value
    (D-14): the whole family for the registration form, that form alone
    otherwise. The chosen form's own question names the filter; failing
    that, the first form by id. An entry with nothing left in its scope
    is left out; one emptied after Publish is dropped as the dashboard is
    read (live_filter_questions).
    """
    entries = default_filters.get("questions")
    if not isinstance(entries, list) or not entries:
        return default_filters
    family = set(
        Forms.objects.filter(Q(pk=root_form_id) | Q(parent_id=root_form_id))
        .values_list("pk", flat=True)
    )
    names = {
        entry.get("name") for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    by_name = defaultdict(list)
    for question in (
        Questions.objects.filter(
            form_id__in=family, name__in=names, type__in=OPTION_TYPES,
        )
        .order_by("form_id", "id")
        .prefetch_related(_options_prefetch())
    ):
        by_name[question.name].append(question)
    questions = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        form_id, name = entry.get("form"), entry.get("name")
        if form_id not in family:
            continue
        scope = global_filter_scope(root_form_id, form_id, family)
        # Stable sort: the chosen form's question first, then form order.
        group = sorted(
            (q for q in by_name.get(name, []) if q.form_id in scope),
            key=lambda question: question.form_id != form_id,
        )
        if not group:
            continue
        questions.append({
            "form": form_id,
            "name": name,
            "label": group[0].label,
            "options": _merge_options([
                serialize_question(question).get("options") or []
                for question in group
            ]),
        })
    return {**default_filters, "questions": questions}


def live_filter_questions(default_filters, tenant):
    """Copy of default_filters without filters that stopped being
    filterable since Publish: no live option question of that name left
    in the scope, or the form deleted (VIZ-027, decided 2026-10-06; D-20).

    Checked as the dashboard is served, like annotate_broken: a question
    can be deleted at any time after Publish. One query, scoped by tenant
    for the same reason annotate_broken is. The stored snapshot is not
    touched.
    """
    entries = (default_filters or {}).get("questions")
    if not isinstance(entries, list) or not entries:
        return default_filters
    # Still filterable means what parse_global_criteria accepts: a live
    # option question of that name on a live form of the scope. A question
    # on a monitoring form also counts for the family scope of its parent
    # (the registration form). Anything else would 400 every widget the
    # moment a viewer picked a value.
    forms = {
        entry.get("form") for entry in entries if isinstance(entry, dict)
    }
    query = Questions.objects.filter(
        Q(form_id__in=forms) | Q(form__parent_id__in=forms),
        name__in={
            entry.get("name") for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
        },
        type__in=OPTION_TYPES,
        form__deleted_at__isnull=True,
    )
    if tenant is not None:
        query = query.filter(**{Questions.TENANT_PATH: tenant})
    live = set()
    for form_id, parent_id, name in query.values_list(
        "form_id", "form__parent_id", "name",
    ):
        live.add((form_id, name))
        if parent_id is not None:
            live.add((parent_id, name))
    return {
        **default_filters,
        "questions": [
            entry for entry in entries
            if isinstance(entry, dict)
            and (entry.get("form"), entry.get("name")) in live
        ],
    }


def annotate_broken(widgets, tenant):
    """Copy each widget with `is_broken` / `broken_reason` set.

    Spec D-5. The obvious query here is
    `filter(deleted_at__isnull=False)`. This does the inverse: it asks
    which referenced ids are *live and belong to this tenant*, and
    treats everything else as broken. That catches three failure modes
    where the obvious one catches a single case — soft-deleted (the
    common case), hard-deleted (no row left to read `deleted_at` from),
    and an id belonging to another tenant. The last should be
    unreachable, since the family was validated at save time, but a
    snapshot is a copy taken at a point in time and this is the one
    place where such a copy meets live rows.

    Scoped by tenant rather than by user because this runs for
    anonymous readers too. `for_user` would hand an anonymous caller
    the tenant-less queryset, mark every widget on a public dashboard
    broken, and render the whole page as an error — a failure that
    looks like data loss rather than like a missing permission.

    Two queries, both flat in widget count. The result is a new list;
    the caller's snapshot is never mutated, because it is a row from
    the database that nobody meant to write back.
    """
    def live(model, ids):
        query = model.objects.filter(id__in={i for i in ids if i})
        if tenant is not None:
            query = query.filter(**{model.TENANT_PATH: tenant})
        return set(query.values_list("id", flat=True))

    def stack_question(widget):
        return (widget.get("config") or {}).get("stack_question")

    def stack_form(widget):
        return (widget.get("config") or {}).get("stack_form")

    live_forms = live(
        Forms,
        [w.get("form") for w in widgets]
        + [stack_form(w) for w in widgets],
    )
    # Both question references in one query: the widget's own, and the
    # stacking question a bar may name in its config (VIZ-015). A stack
    # question deleted after publish would otherwise 400 the viewer
    # with no explanation — the exact failure this function exists to
    # turn into a visible broken widget.
    live_questions = live(
        Questions,
        [w.get("question") for w in widgets]
        + [stack_question(w) for w in widgets],
    )

    annotated = []
    for widget in widgets:
        row = dict(widget)
        form_id = row.get("form")
        question_id = row.get("question")
        stack_question_id = stack_question(row)
        stack_form_id = stack_form(row)
        # Widest cause first, all the way down: a widget on a deleted
        # form must not blame the question that went down with it, and a
        # deleted stack form must not blame its own question either.
        if form_id and form_id not in live_forms:
            reason = "form_deleted"
        elif question_id and question_id not in live_questions:
            reason = "question_deleted"
        elif stack_form_id and stack_form_id not in live_forms:
            reason = "stack_form_deleted"
        elif stack_question_id and (
            stack_question_id not in live_questions
        ):
            reason = "stack_question_deleted"
        else:
            reason = None
        row["is_broken"] = reason is not None
        row["broken_reason"] = reason
        annotated.append(row)
    return annotated
