from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_visualization.functions import (
    apply_administration_filter,
    apply_criteria_to_monitoring_qs,
    apply_parent_criteria_to_qs,
    build_date_filters,
    latest_monitoring_subquery,
)


def compute_any_yes(latest_data_id, question_ids, answers_map, **kwargs):
    """100% if ANY listed question answered 'Yes'."""
    for qid in question_ids:
        a = answers_map.get((latest_data_id, qid))
        if a and a.get("options") and "yes" in a["options"]:
            return 100.0
    return 0.0


def compute_completed_binary(
    latest_data_id, question_ids, answers_map, **kwargs
):
    """100% if answered 'Completed'."""
    for qid in question_ids:
        a = answers_map.get((latest_data_id, qid))
        if a and a.get("options") and "completed" in a["options"]:
            return 100.0
    return 0.0


def compute_ratio(
    latest_data_id, question_ids, answers_map, **kwargs
):
    """(Implemented / Planned) * 100, clamped to [0, 100].

    Expects question_ids = [implemented_qid, planned_qid].
    Returns 0.0 if either value is missing or planned <= 0.
    """
    if len(question_ids) < 2:
        return 0.0
    implemented_qid, planned_qid = question_ids[0], question_ids[1]
    impl_row = answers_map.get((latest_data_id, implemented_qid))
    plan_row = answers_map.get((latest_data_id, planned_qid))
    implemented = impl_row.get("value") if impl_row else None
    planned = plan_row.get("value") if plan_row else None
    if implemented is None or planned is None:
        return 0.0
    try:
        planned = float(planned)
        implemented = float(implemented)
    except (TypeError, ValueError):
        return 0.0
    if planned <= 0:
        return 0.0
    return round(min((implemented / planned) * 100, 100.0), 2)


def compute_multi_select_proportion(
    latest_data_id, question_ids, answers_map,
    total_items=1, **kwargs
):
    """Percentage based on number of selected options."""
    selected = None
    for qid in question_ids:
        a = answers_map.get((latest_data_id, qid))
        if a and a.get("options"):
            selected = a["options"]
            break
    if not selected:
        return 0.0
    if not total_items or total_items <= 0:
        return 0.0
    pct = (len(selected) / total_items) * 100
    return round(min(pct, 100.0), 2)


FORMULA_HANDLERS = {
    "any_yes": compute_any_yes,
    "completed_binary": compute_completed_binary,
    "ratio": compute_ratio,
    "multi_select_proportion": (
        compute_multi_select_proportion
    ),
}


def filter_components_by_scope(components, scope_value):
    """Filter components to those applicable for a scope value.

    If scope_value is None or a component has no applicable_types,
    the component is always included.
    """
    if not scope_value:
        return components
    return [
        c for c in components
        if not c.get("applicable_types")
        or scope_value in c["applicable_types"]
    ]


def compute_component_scores(
    latest_id, components, answers_map, scope_value=None,
):
    """Compute progress scores for applicable components."""
    active = filter_components_by_scope(components, scope_value)
    scores = {}
    for comp in active:
        handler = FORMULA_HANDLERS[comp["formula"]]
        kwargs = {}
        if comp.get("total_items"):
            kwargs["total_items"] = comp["total_items"]
        scores[comp["key"]] = handler(
            latest_id,
            comp["question_ids"],
            answers_map,
            **kwargs,
        )
    return scores


def build_progress_answers_map(latest_ids, components, user):
    """Bulk-fetch answers needed to score all components for all parents.

    Returns dict keyed by (data_id, question_id) carrying the fields
    formula handlers read (options, value).
    """
    qids = {
        q for c in components for q in c.get("question_ids", [])
    }
    if not qids or not latest_ids:
        return {}
    rows = Answers.objects.for_user(user).filter(
        data_id__in=latest_ids,
        question_id__in=qids,
    ).values("data_id", "question_id", "options", "value")
    return {
        (r["data_id"], r["question_id"]): r for r in rows
    }


def build_histogram(eps_results):
    """Bucket overall progress into 10% ranges.

    Returns list of 10 buckets, each with progress label
    and count.
    """
    buckets = [
        "0-10%", "11-20%", "21-30%", "31-40%", "41-50%",
        "51-60%", "61-70%", "71-80%", "81-90%", "91-100%",
    ]
    counts = [0] * 10
    for eps in eps_results:
        overall = eps["overall"]
        if overall <= 0:
            idx = 0
        else:
            idx = min(max(0, int(overall - 1) // 10), 9)
        counts[idx] += 1
    return [
        {"progress": buckets[i], "count": counts[i]}
        for i in range(10)
    ]


def handle_progress(
    parent_form, monitoring_form_id,
    components, params, user,
):
    """Handle progress query.

    Args:
        parent_form: Registration form instance.
        monitoring_form_id: Monitoring form ID.
        components: Parsed component list with
            key/formula/question_ids/total_items.
        params: Dict with filter_question_id,
            filter_option_value, administration_id,
            from_date, to_date, date_question_id.
        user: Acting user. Kept out of `params` on purpose:
            `params` is the attacker-controlled query grammar,
            so the security principal travels separately.

    Returns:
        Dict with histogram and details.
    """
    administration_id = params.get("administration_id")
    filter_qid = params.get("filter_question_id")
    filter_value = params.get("filter_option_value")

    date_filters = build_date_filters(params)

    parents = FormData.objects.for_user(user).filter(
        form=parent_form,
        parent__isnull=True,
        is_pending=False,
        is_draft=False,
    ).annotate(
        latest_id=latest_monitoring_subquery(
            monitoring_form_id, date_filters or None
        ),
    ).filter(latest_id__isnull=False)

    if administration_id:
        parents = apply_administration_filter(
            parents, administration_id
        )

    # Multi-criteria AND filter (shared grammar with /values).
    parents = apply_criteria_to_monitoring_qs(
        parents, True, params.get("criteria"),
    )
    parents = apply_parent_criteria_to_qs(
        parents, True, params.get("parent_criteria"),
    )

    # Optional filter by latest monitoring option value
    if filter_qid and filter_value:
        latest_ids = parents.values_list(
            "latest_id", flat=True
        )
        matching_ids = Answers.objects.for_user(user).filter(
            data_id__in=latest_ids,
            question_id=filter_qid,
            options__contains=[filter_value],
        ).values_list("data_id", flat=True)
        parents = parents.filter(
            latest_id__in=matching_ids
        )

    # Compute scores per parent
    scope_qid = params.get("scope_question_id")
    parents = list(parents.only("id", "name"))
    latest_ids = [p.latest_id for p in parents]
    answers_map = build_progress_answers_map(
        latest_ids, components, user
    )

    # Build scope lookup: latest_id -> scope option value
    scope_map = {}
    if scope_qid:
        scope_rows = Answers.objects.for_user(user).filter(
            data_id__in=latest_ids,
            question_id=scope_qid,
        ).values("data_id", "options")
        for row in scope_rows:
            opts = row.get("options") or []
            if opts:
                scope_map[row["data_id"]] = opts[0]

    eps_results = []
    for parent in parents:
        scope_value = scope_map.get(parent.latest_id)
        scores = compute_component_scores(
            parent.latest_id, components, answers_map,
            scope_value=scope_value,
        )
        overall = (
            round(sum(scores.values()) / len(scores), 2)
            if scores else 0.0
        )
        eps_results.append({
            "label": parent.name,
            "group": str(parent.id),
            "components": scores,
            "overall": overall,
        })

    histogram = build_histogram(eps_results)

    return {
        "histogram": histogram,
        "details": eps_results,
    }
