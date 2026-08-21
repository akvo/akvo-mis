from urllib.parse import urlencode

from django.db.models import Q

from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_visualization.functions import (
    apply_administration_filter,
    apply_criteria_to_monitoring_qs,
    apply_parent_criteria_to_qs,
    build_date_filters,
    latest_monitoring_subquery,
    format_date_group,
    split_criteria_by_form,
)


def build_escalation_criteria_filter(criteria, latest_ids, user):
    """Build OR query from parsed escalation criteria.

    Args:
        criteria: List of parsed criteria dicts with
            'type' and 'parts' keys.
        latest_ids: List of latest monitoring data IDs.
        user: Acting user, used to tenant-scope the answer
            lookups independently of the caller's own checks.

    Returns:
        Q object combining all criteria with OR logic.
    """
    or_condition = Q()
    for criterion in criteria:
        ctype = criterion["type"]
        parts = criterion["parts"]

        if ctype == "option_equals":
            qid = int(parts[0])
            value = parts[1]
            matching = Answers.objects.for_user(user).filter(
                data_id__in=latest_ids,
                question_id=qid,
                options__contains=[value],
            ).values_list("data_id", flat=True)
            or_condition |= Q(latest_id__in=matching)

        elif ctype == "threshold_gt":
            qid = int(parts[0])
            threshold = float(parts[1])
            matching = Answers.objects.for_user(user).filter(
                data_id__in=latest_ids,
                question_id=qid,
                value__gt=threshold,
            ).values_list("data_id", flat=True)
            or_condition |= Q(latest_id__in=matching)

        elif ctype == "threshold_lt":
            qid = int(parts[0])
            threshold = float(parts[1])
            matching = Answers.objects.for_user(user).filter(
                data_id__in=latest_ids,
                question_id=qid,
                value__lt=threshold,
            ).values_list("data_id", flat=True)
            or_condition |= Q(latest_id__in=matching)

        elif ctype == "overdue":
            from datetime import date
            completion_qid = int(parts[0])
            deadline_qid = int(parts[1])
            incomplete = set(Answers.objects.for_user(user).filter(
                data_id__in=latest_ids,
                question_id=completion_qid,
                options__contains=["no"],
            ).values_list("data_id", flat=True))
            overdue = set(Answers.objects.for_user(user).filter(
                data_id__in=latest_ids,
                question_id=deadline_qid,
                name__lt=date.today().isoformat(),
            ).values_list("data_id", flat=True))
            or_condition |= Q(
                latest_id__in=incomplete & overdue
            )

    return or_condition


def _answer_cell_value(answer):
    """Collapse an Answers row into the cell value used by escalation."""
    if not answer:
        return None
    if answer.get("options"):
        return answer["options"][0]
    if answer.get("value") is not None:
        return answer["value"]
    return answer.get("name")


def build_column_caches(paginated, columns, user):
    """Pre-fetch answers and FormData needed for rendering one page.

    Reduces the per-row work in extract_column_value from O(columns)
    queries per row to a handful of bulk queries per page.
    """
    latest_ids = [p.latest_id for p in paginated]
    parent_ids = [p.id for p in paginated]

    answer_qids = set()
    parent_answer_qids = set()
    latest_date_qids = set()
    need_created_fallback = False

    for c in columns:
        src = c["source"]
        qid = c.get("question_id")
        if src == "answer" and qid:
            answer_qids.add(qid)
        elif src == "parent_answer" and qid:
            parent_answer_qids.add(qid)
        elif src == "latest_date":
            if qid:
                latest_date_qids.add(qid)
            else:
                need_created_fallback = True

    answer_map = {}
    if answer_qids or latest_date_qids:
        rows = Answers.objects.for_user(user).filter(
            data_id__in=latest_ids,
            question_id__in=answer_qids | latest_date_qids,
        ).values(
            "data_id", "question_id",
            "name", "value", "options",
        )
        for r in rows:
            answer_map[(r["data_id"], r["question_id"])] = r

    parent_answer_map = {}
    if parent_answer_qids:
        rows = Answers.objects.for_user(user).filter(
            data_id__in=parent_ids,
            question_id__in=parent_answer_qids,
        ).values(
            "data_id", "question_id",
            "name", "value", "options",
        )
        for r in rows:
            parent_answer_map[(r["data_id"], r["question_id"])] = r

    created_map = {}
    if need_created_fallback:
        fd_rows = FormData.objects.for_user(user).filter(
            id__in=latest_ids,
        ).values("id", "created")
        created_map = {r["id"]: r["created"] for r in fd_rows}

    return {
        "answer": answer_map,
        "parent_answer": parent_answer_map,
        "created": created_map,
    }


def extract_column_value(parent, latest_id, col, caches):
    """Extract a column value for a single parent row using caches."""
    source = col["source"]

    if source == "parent_name":
        return parent.name

    if source == "administration":
        adm = parent.administration
        if adm and adm.path:
            ancestors = adm.ancestors.values_list(
                "name", flat=True,
            )
            parts = list(ancestors) + [adm.name]
            return " > ".join(parts)
        return adm.name if adm else None

    if source == "answer":
        qid = col.get("question_id")
        if not qid:
            return None
        return _answer_cell_value(
            caches["answer"].get((latest_id, qid))
        )

    if source == "parent_answer":
        qid = col.get("question_id")
        if not qid:
            return None
        return _answer_cell_value(
            caches["parent_answer"].get((parent.id, qid))
        )

    if source == "latest_date":
        qid = col.get("question_id")
        if qid:
            answer = caches["answer"].get((latest_id, qid))
            if answer and answer.get("name"):
                return format_date_group(answer["name"])
        created = caches["created"].get(latest_id)
        if created:
            return format_date_group(created)
        return None

    return None


def handle_escalation(
    parent_form, monitoring_form_id,
    criteria, columns, params, user,
):
    """Handle escalation query.

    Args:
        parent_form: Registration form instance.
        monitoring_form_id: Monitoring form ID.
        criteria: Parsed criteria list.
        columns: Parsed columns list.
        params: Dict with page, page_size,
            administration_id, from_date, to_date.
        user: Acting user. Kept out of `params` on purpose:
            `params` is the attacker-controlled query grammar,
            so the security principal travels separately.

    Returns:
        Dict with count, next, previous, results.
    """
    page = params.get("page", 1)
    page_size = params.get("page_size", 20)
    administration_id = params.get("administration_id")

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

    # Optional AND-narrowing criteria (shared grammar with /values)
    # applied on top of the OR-escalation criteria. Split by form so
    # parent-form filters (e.g. implementing_agency) go through
    # apply_parent_criteria_to_qs while monitoring-form filters go
    # through apply_criteria_to_monitoring_qs.
    filter_criteria = params.get("filter_criteria")
    if filter_criteria:
        mon_criteria, parent_criteria = split_criteria_by_form(
            filter_criteria, monitoring_form_id, parent_form.id,
        )
        parents = apply_criteria_to_monitoring_qs(
            parents, True, mon_criteria,
        )
        parents = apply_parent_criteria_to_qs(
            parents, True, parent_criteria,
        )

    latest_ids = list(
        parents.values_list("latest_id", flat=True)
    )

    or_condition = build_escalation_criteria_filter(
        criteria, latest_ids, user
    )
    matching = parents.filter(or_condition).order_by("id")

    total = matching.count()
    start = (page - 1) * page_size
    end = start + page_size
    paginated = list(
        matching[start:end].select_related("administration")
    )

    caches = build_column_caches(paginated, columns, user)

    results = []
    for parent in paginated:
        row = {"id": parent.id}
        for col in columns:
            row[col["key"]] = extract_column_value(
                parent, parent.latest_id, col, caches,
            )
        results.append(row)

    query_string = params.get("query_string")
    if query_string:
        base_params = [
            (k, v) for k, v in query_string
            if k != "page"
        ]
    else:
        base_params = [
            ("monitoring_form_id", monitoring_form_id),
            ("page_size", page_size),
        ]
        if administration_id:
            base_params.append(
                ("administration_id", administration_id)
            )
        for key in ("from_date", "to_date", "date_question_id"):
            if params.get(key):
                base_params.append((key, params[key]))

    def build_link(target_page):
        link_params = base_params + [("page", target_page)]
        return f"?{urlencode(link_params, doseq=True)}"

    return {
        "count": total,
        "next": build_link(page + 1) if end < total else None,
        "previous": build_link(page - 1) if page > 1 else None,
        "results": results,
    }
