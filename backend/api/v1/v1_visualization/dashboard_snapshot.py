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
    return _annotate(widgets, lambda model: model.objects.for_user(user))


def annotate_broken_for_tenant(widgets, tenant):
    """The same annotation for a caller with no user (VIZ-010).

    A public dashboard is read anonymously, so there is nobody to scope
    by. `for_user(AnonymousUser)` is not a stand-in: it resolves to
    `tenant IS NULL`, which matches nothing on a real deployment and
    every row on a tenant-less one. The tenant comes from the host
    instead, and is named explicitly.
    """
    return _annotate(
        widgets, lambda model: model.objects.for_tenant(tenant)
    )


def _annotate(widgets, scoped):
    def live(model, key):
        ids = {w.get(key) for w in widgets if w.get(key)}
        return set(
            scoped(model)
            .filter(id__in=ids)
            .values_list("id", flat=True)
        )

    live_forms = live(Forms, "form")
    live_questions = live(Questions, "question")

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
