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
from api.v1.v1_visualization.dashboard_builder_serializers import (
    DashboardWidgetSerializer,
)


def build_snapshot(dashboard):
    """Live widget rows -> the dict stored in `published_config`.

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
    widgets = dashboard.widgets.order_by("order", "id")
    return {
        "default_filters": dashboard.default_filters or {},
        "widgets": DashboardWidgetSerializer(widgets, many=True).data,
    }


def annotate_broken(widgets, user):
    """Copy each widget with `is_broken` / `broken_reason` set.

    Spec D-5. The obvious query here is
    `filter(deleted_at__isnull=False)`. This does the inverse: it asks
    which referenced ids are *live and visible to this caller*, and
    treats everything else as broken. That catches three failure modes
    where the obvious one catches a single case — soft-deleted (the
    common case), hard-deleted (no row left to read `deleted_at` from),
    and an id belonging to another tenant. The last should be
    unreachable, since the family was validated at save time, but a
    snapshot is a copy taken at a point in time and this is the one
    place where such a copy meets live rows.

    Two queries, both flat in widget count. The result is a new list;
    the caller's snapshot is never mutated, because it is a row from
    the database that nobody meant to write back.
    """
    form_ids = {w.get("form") for w in widgets if w.get("form")}
    question_ids = {
        w.get("question") for w in widgets if w.get("question")
    }
    live_forms = set(
        Forms.objects.for_user(user)
        .filter(id__in=form_ids)
        .values_list("id", flat=True)
    )
    live_questions = set(
        Questions.objects.for_user(user)
        .filter(id__in=question_ids)
        .values_list("id", flat=True)
    )

    annotated = []
    for widget in widgets:
        row = dict(widget)
        form_id = row.get("form")
        question_id = row.get("question")
        # Form first: a widget on a deleted form must not blame the
        # question that went down with it.
        if form_id and form_id not in live_forms:
            reason = "form_deleted"
        elif question_id and question_id not in live_questions:
            reason = "question_deleted"
        else:
            reason = None
        row["is_broken"] = reason is not None
        row["broken_reason"] = reason
        annotated.append(row)
    return annotated
