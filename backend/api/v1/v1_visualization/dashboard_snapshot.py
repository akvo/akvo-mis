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

from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_visualization.constants import DashboardKind
from api.v1.v1_visualization.dashboard_builder_serializers import (
    DashboardWidgetSerializer,
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
        "default_filters": dashboard.default_filters or {},
        "widgets": DashboardWidgetSerializer(widgets, many=True).data,
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
