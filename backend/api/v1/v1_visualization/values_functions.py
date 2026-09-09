from collections import defaultdict

from django.db.models import Count, Avg, F, OuterRef, Subquery
from django.db.models.functions import TruncMonth, Substr

from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import QuestionOptions
from api.v1.v1_visualization.constants import AGG_FUNCS
from api.v1.v1_visualization.functions import (
    get_base_monitoring_qs,
    get_monitoring_data_ids,
    format_month_label,
    format_month_group,
    format_date_group,
    fill_month_gaps,
    fill_date_gaps,
    apply_administration_filter,
    apply_parent_criteria_to_qs,
)


# Stacked rows are keyed by option LABEL, so a label that collides with a
# structural key would overwrite it and two options sharing a label would
# silently merge into one column. Both are author-controlled strings.
RESERVED_ROW_KEYS = {"label", "group", "color", "value"}


def value_by_data(value_question, data_ids):
    """`{data_id: [numbers]}` for the value question, or None.

    None means "no value question", which every caller reads as "count
    rows" — the behaviour every stored dashboard has today.

    A list per submission rather than a single number, because a
    repeatable group answers the same question several times. Collapsing
    those is `repeat_agg`'s job and it happens once, at the cell.
    """
    if value_question is None:
        return None
    values = defaultdict(list)
    rows = Answers.objects.filter(
        data_id__in=data_ids,
        question_id=value_question.id,
        value__isnull=False,
    ).values_list("data_id", "value")
    for data_id, value in rows:
        values[data_id].append(value)
    return values


def aggregate_values(values, agg):
    """One number from many, in AGG_FUNCS' vocabulary.

    Empty is 0, not None: a bar with no answers is a bar of zero height,
    and a hole in the middle of a stacked chart reads as a rendering
    fault rather than as an absence of data.
    """
    if not values:
        return 0
    if agg == "sum":
        total = sum(values)
    elif agg == "max":
        total = max(values)
    elif agg == "min":
        total = min(values)
    elif agg == "last":
        total = values[-1]
    else:
        total = sum(values) / len(values)
    return round(total, 2)


def cell_value(data_ids, values_by_data, agg):
    """The number one bar or segment carries.

    `values_by_data` is None for a plain count, which is why the count
    path stays a `len()` rather than growing a special case: the two
    readings of "how big is this cell" meet here and nowhere else.
    """
    if values_by_data is None:
        return len(data_ids)
    numbers = []
    for data_id in data_ids:
        numbers.extend(values_by_data.get(data_id, []))
    return aggregate_values(numbers, agg)


def build_stack_labels(options):
    """Row keys for the stack columns: unique, and never structural.

    The returned list is positional with `options`, and is the same list
    returned as `stack_labels`, so the legend and the row keys cannot
    disagree.
    """
    labels = []
    seen = {}
    for option in options:
        base = option.label or option.value or ""
        if base in RESERVED_ROW_KEYS:
            base = "{0} (option)".format(base)
        count = seen.get(base, 0) + 1
        seen[base] = count
        labels.append(
            base if count == 1 else "{0} ({1})".format(base, count)
        )
    return labels


def _should_fill_gaps(params):
    """Only gap-fill when both from_date and to_date are provided."""
    return bool(
        params.get("from_date") and params.get("to_date")
    )


def _total_parents_in_scope(form, params):
    """Count all parent registrations in scope, respecting filters."""
    scope_form = form.parent if form.parent else form
    qs = FormData.objects.filter(
        form=scope_form,
        parent__isnull=True,
        is_pending=False,
        is_draft=False,
    )
    administration_id = params.get("administration_id")
    if administration_id:
        qs = apply_administration_filter(qs, administration_id)
    qs = apply_parent_criteria_to_qs(
        qs, True, params.get("parent_criteria"),
    )
    return qs.count()


def _count_no_info_parents(form, params, qualifying_ids):
    """Count datapoints in scope with no qualifying answer.

    For monitoring forms: counts parent registrations without any
    qualifying monitoring submission (gap in monitoring coverage).
    For registration forms: counts registrations that exist but have no
    answer for the question (field left blank / skipped).

    Respects administration_id and parent_criteria so the count
    reconciles with option counts under filtering (FR-3).
    """
    total = _total_parents_in_scope(form, params)
    return max(0, total - len(qualifying_ids))


# -- Count mode handler --

def handle_count_mode(form, params):
    """Handle count mode (no question_id)."""
    form_id = form.id
    monitoring = params.get("monitoring", "latest")
    group_by = params.get("group_by")
    value_type = params.get("value_type", "number")
    sum_by = params.get("sum_by")
    is_monitoring = form.parent is not None

    if is_monitoring and monitoring == "latest" \
            and sum_by == "parent_id":
        qs, is_latest, _ = get_base_monitoring_qs(
            form, form_id, params
        )
        count = qs.count()
        if value_type == "percentage":
            total = FormData.objects.filter(
                form=form.parent,
                parent__isnull=True,
                is_pending=False,
                is_draft=False,
            ).count()
            value = round(
                (count / total * 100), 2
            ) if total > 0 else 0
        else:
            value = count
        return (
            [{"value": value, "label": "Total"}],
            ["Total"],
        )

    qs, is_latest, _ = get_base_monitoring_qs(
        form, form_id, params
    )

    if not group_by:
        count = qs.count()
        if value_type == "percentage" and is_monitoring:
            total = FormData.objects.filter(
                form=form.parent,
                parent__isnull=True,
                is_pending=False,
                is_draft=False,
            ).count()
            value = round(
                (count / total * 100), 2
            ) if total > 0 else 0
        else:
            value = count
        return (
            [{"value": value, "label": "Total"}],
            ["Total"],
        )

    if group_by == "month":
        return _count_group_by_month(qs, is_latest, params)

    if group_by == "parent_id":
        return _count_group_by_parent(qs, is_latest)

    if group_by == "id":
        return _count_group_by_id(qs, is_latest)

    if group_by == "date":
        return _count_group_by_date(qs, is_latest, params)

    return [{"value": 0, "label": "Total"}], ["Total"]


def _count_group_by_month(qs, is_latest, params):
    """Count grouped by month."""
    date_qid = params.get("date_question_id")

    if is_latest:
        data_ids = get_monitoring_data_ids(qs, is_latest)
        if date_qid:
            answer_qs = Answers.objects.filter(
                data_id__in=data_ids,
                question_id=date_qid,
                name__isnull=False,
            )
            results = answer_qs.annotate(
                year_month=Substr("name", 1, 7),
            ).values("year_month").annotate(
                count=Count("data_id", distinct=True),
            ).order_by("year_month")
            data = [
                {
                    "value": r["count"],
                    "label": format_month_label(
                        r["year_month"]
                    ),
                    "group": r["year_month"],
                }
                for r in results
            ]
        else:
            results = FormData.objects.filter(
                id__in=data_ids,
            ).annotate(
                month=TruncMonth("created"),
            ).values("month").annotate(
                count=Count("id"),
            ).order_by("month")
            data = [
                {
                    "value": r["count"],
                    "label": format_month_label(r["month"]),
                    "group": format_month_group(r["month"]),
                }
                for r in results
            ]
    else:
        if date_qid:
            answer_qs = Answers.objects.filter(
                data__in=qs,
                question_id=date_qid,
                name__isnull=False,
            )
            results = answer_qs.annotate(
                year_month=Substr("name", 1, 7),
            ).values("year_month").annotate(
                count=Count("data_id", distinct=True),
            ).order_by("year_month")
            data = [
                {
                    "value": r["count"],
                    "label": format_month_label(
                        r["year_month"]
                    ),
                    "group": r["year_month"],
                }
                for r in results
            ]
        else:
            results = qs.annotate(
                month=TruncMonth("created"),
            ).values("month").annotate(
                count=Count("id"),
            ).order_by("month")
            data = [
                {
                    "value": r["count"],
                    "label": format_month_label(r["month"]),
                    "group": format_month_group(r["month"]),
                }
                for r in results
            ]

    if _should_fill_gaps(params):
        data = fill_month_gaps(
            data, params["from_date"], params["to_date"]
        )
    labels = [d["label"] for d in data]
    return data, labels


def _count_group_by_parent(qs, is_latest):
    """Count grouped by parent_id."""
    if is_latest:
        data = [
            {
                "value": 1,
                "label": p.name,
                "group": str(p.id),
            }
            for p in qs.only("id", "name")
        ]
    else:
        results = qs.filter(
            parent__isnull=False,
        ).values(
            "parent_id",
            parent_name=F("parent__name"),
        ).annotate(
            count=Count("id"),
        ).order_by("parent_name")
        data = [
            {
                "value": r["count"],
                "label": r["parent_name"],
                "group": str(r["parent_id"]),
            }
            for r in results
        ]
    labels = [d["label"] for d in data]
    return data, labels


def _count_group_by_id(qs, is_latest):
    """Count grouped by individual record id (value=1 per row)."""
    if is_latest:
        data = [
            {
                "value": 1,
                "label": p.name,
                "group": str(p.latest_id),
            }
            for p in qs.only("id", "name")
        ]
    else:
        data = [
            {
                "value": 1,
                "label": r.name,
                "group": str(r.id),
            }
            for r in qs.only("id", "name").order_by("id")
        ]
    labels = [d["label"] for d in data]
    return data, labels


def _count_group_by_date(qs, is_latest, params):
    """Count grouped by individual date (not month bucket)."""
    date_qid = params.get("date_question_id")
    data_ids = get_monitoring_data_ids(qs, is_latest)

    if date_qid:
        results = Answers.objects.filter(
            data_id__in=data_ids,
            question_id=date_qid,
            name__isnull=False,
        ).annotate(
            day=Substr("name", 1, 10),
        ).values("day").annotate(
            count=Count("data_id", distinct=True),
        ).order_by("day")
        data = [
            {
                "value": r["count"],
                "label": r["day"],
                "group": r["day"],
            }
            for r in results
        ]
    else:
        results = FormData.objects.filter(
            id__in=data_ids,
        ).values(
            day=F("created__date"),
        ).annotate(
            count=Count("id"),
        ).order_by("day")
        data = [
            {
                "value": r["count"],
                "label": format_date_group(r["day"]),
                "group": format_date_group(r["day"]),
            }
            for r in results
        ]
    if _should_fill_gaps(params):
        data = fill_date_gaps(
            data, params["from_date"], params["to_date"]
        )
    labels = [d["label"] for d in data]
    return data, labels


# -- Option question handler --

def handle_option_question(form, question, params):
    """Handle option/multiple_option questions."""
    form_id = form.id
    group_by = params.get("group_by")
    option_value = params.get("option_value")
    sum_by = params.get("sum_by")
    value_type = params.get("value_type", "number")
    stack_by = params.get("stack_by")

    qs, is_latest, _ = get_base_monitoring_qs(
        form, form_id, params
    )
    data_ids = get_monitoring_data_ids(qs, is_latest)

    options = QuestionOptions.objects.filter(
        question=question,
    ).order_by("order")

    if option_value and group_by == "month":
        return _option_value_group_by_month(
            question, data_ids, option_value, sum_by, params
        )

    if option_value:
        return _option_value_filter(
            question, data_ids, qs, is_latest,
            option_value, sum_by, value_type,
            include_unanswered=params.get(
                "include_unanswered", False
            ),
            form=form,
            params=params,
            include_empty=params.get("include_empty", False),
        )

    # Absent stack_question means "this question's own options", which
    # is what stack_by=option has always meant.
    stack_question = params.get("stack_question") or question
    # ...but a question cross-tabbed against ITSELF is a diagonal: every
    # bar is one option, so its only non-zero segment is that same
    # option. That is the plain option breakdown wearing a legend, so
    # fall through and draw the plain one.
    self_crosstab = (
        group_by == "option" and stack_question.id == question.id
    )
    # Resolved once for every path below: None means "count rows", which
    # is what every stored dashboard does (VIZ-015.b).
    values_by_data = value_by_data(
        params.get("value_question"), data_ids
    )

    if stack_by == "option" and group_by and not self_crosstab:
        stack_options = (
            options
            if stack_question.id == question.id
            else QuestionOptions.objects.filter(
                question=stack_question,
            ).order_by("order")
        )
        return handle_stack_by_option(
            question, options, stack_question, stack_options,
            data_ids, qs, is_latest, params,
            values_by_data=values_by_data
        )

    if group_by == "option":
        restricted = _extract_criteria_option_values(
            params, question.id
        )
        return _option_group_by_option(
            question, options, data_ids, qs,
            is_latest, value_type, restricted,
            include_unanswered=params.get(
                "include_unanswered", False
            ),
            form=form,
            params=params,
            values_by_data=values_by_data,
            agg=params.get("repeat_agg", "average"),
        )

    return [], []


def _option_value_filter(
    question, data_ids, qs, is_latest,
    option_value, sum_by, value_type,
    include_unanswered=False, form=None, params=None,
    include_empty=False,
):
    """Filter by specific option value and count.

    include_unanswered=True: parents with no answer for the question
    (monitored but null options) are added to the count.

    include_empty=True: parents with zero monitoring submissions
    (never visited) are added to the count. Takes precedence over
    include_unanswered when both are set, as the coverage-gap count
    already subsumes the answer-gap count.
    """
    count = Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
        options__contains=[option_value],
    )
    if sum_by == "parent_id":
        count = count.values(
            "data__parent_id"
        ).distinct().count()
    else:
        count = count.count()

    is_monitoring = form is not None and form.parent is not None
    extra = 0

    if include_empty and is_monitoring:
        monitored_parent_ids = set(
            FormData.objects.filter(id__in=data_ids)
            .values_list("parent_id", flat=True)
            .distinct()
        )
        extra = _count_no_info_parents(
            form, params or {}, monitored_parent_ids
        )
    elif include_unanswered and is_monitoring:
        all_answered_ids = set(
            Answers.objects.filter(
                data_id__in=data_ids,
                question_id=question.id,
                options__isnull=False,
            ).values_list("data__parent_id", flat=True).distinct()
        )
        extra = _count_no_info_parents(
            form, params or {}, all_answered_ids
        )

    if value_type == "percentage":
        if (include_empty or include_unanswered) and is_monitoring:
            total = _total_parents_in_scope(form, params or {})
            numerator = count + extra
        else:
            total = qs.count() if is_latest else len(data_ids)
            numerator = count
        value = round(
            (numerator / total * 100), 2
        ) if total > 0 else 0
    else:
        value = count + extra

    return (
        [{"value": value, "label": option_value}],
        [option_value],
    )


def _option_value_group_by_month(
    question, data_ids, option_value, sum_by, params
):
    """Filter by option_value, then bucket by month.

    Used by charts like "Proposed completion date": filter to
    incomplete projects (option_value='no') and bucket the count
    by a date question (e.g. project deadline). When `sum_by` is
    `parent_id`, counts distinct parents per month.
    """
    date_qid = params.get("date_question_id")

    matching_ids = list(Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
        options__contains=[option_value],
    ).values_list("data_id", flat=True))

    if not matching_ids:
        data = []
    elif date_qid:
        answer_qs = Answers.objects.filter(
            data_id__in=matching_ids,
            question_id=date_qid,
            name__isnull=False,
        )
        if sum_by == "parent_id":
            answer_qs = answer_qs.annotate(
                year_month=Substr("name", 1, 7),
            ).values("year_month").annotate(
                count=Count(
                    "data__parent_id", distinct=True
                ),
            ).order_by("year_month")
        else:
            answer_qs = answer_qs.annotate(
                year_month=Substr("name", 1, 7),
            ).values("year_month").annotate(
                count=Count("data_id", distinct=True),
            ).order_by("year_month")
        data = [
            {
                "value": r["count"],
                "label": format_month_label(
                    r["year_month"]
                ),
                "group": r["year_month"],
            }
            for r in answer_qs
        ]
    else:
        fd_qs = FormData.objects.filter(
            id__in=matching_ids,
        ).annotate(
            month=TruncMonth("created"),
        ).values("month")
        if sum_by == "parent_id":
            fd_qs = fd_qs.annotate(
                count=Count("parent_id", distinct=True),
            ).order_by("month")
        else:
            fd_qs = fd_qs.annotate(
                count=Count("id"),
            ).order_by("month")
        data = [
            {
                "value": r["count"],
                "label": format_month_label(r["month"]),
                "group": format_month_group(r["month"]),
            }
            for r in fd_qs
        ]

    if _should_fill_gaps(params):
        data = fill_month_gaps(
            data, params["from_date"], params["to_date"]
        )
    labels = [d["label"] for d in data]
    return data, labels


def _extract_criteria_option_values(params, question_id):
    """Extract option values that criteria restricts for a given qid.

    When criteria includes option_equals/option_contains/option_in
    targeting the same question_id as the donut chart, the tally
    should only count those specific values — not every value in
    a multiple_option answer array. Returns None if no restriction.
    """
    all_criteria = list(params.get("criteria") or [])
    all_criteria.extend(params.get("parent_criteria") or [])
    values = set()
    for c in all_criteria:
        ctype = c["type"]
        parts = c["parts"]
        if parts[0] != question_id:
            continue
        if ctype in ("option_equals", "option_contains"):
            values.add(parts[1])
        elif ctype == "option_in":
            values.update(parts[1])
    return values or None


def _option_group_by_option(
    question, options, data_ids, qs,
    is_latest, value_type, restricted_values=None,
    include_unanswered=False, form=None, params=None,
    values_by_data=None, agg="average",
):
    """Group by option values (donut chart).

    Returns a row for every defined option — including zero-count
    options — so pie/doughnut charts have stable legends and colors
    across refreshes and filter changes.

    When `restricted_values` is set (from a criteria filter on the
    same question), only those values are tallied — so a
    multiple_option record ["a", "b"] filtered by "a" counts only
    for "a", not "b".

    When `include_unanswered=True`, appends one synthetic row
    (group="_no_info") for parents with no qualifying answer,
    and adjusts the percentage denominator to include the bucket
    so single-choice rows sum to 100%.
    """
    option_values = {o.value for o in options}
    tally_values = (
        option_values & restricted_values
        if restricted_values else option_values
    )
    # Submission ids per option, not a running count: a count is len()
    # of the list, and a value question needs the ids to look its
    # numbers up (VIZ-015.b).
    members = defaultdict(list)
    qualifying_parents = set()
    # Registration forms have no parent; track data_id directly.
    # Monitoring forms track data__parent_id (the registration ID).
    is_registration = form is not None and form.parent is None
    tracking_field = (
        "data_id" if is_registration else "data__parent_id"
    )
    # `data_id` alongside the tracking field: the tracking field may be
    # the PARENT's id (used for the percentage denominator), while a
    # value lookup is always keyed on the submission itself.
    for tracking_id, data_id, opts in Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
        options__isnull=False,
    ).values_list(tracking_field, "data_id", "options"):
        matched = False
        for v in (opts or []):
            if v in tally_values:
                members[v].append(data_id)
                matched = True
        if matched:
            qualifying_parents.add(tracking_id)

    counts = [
        cell_value(members.get(opt.value, []), values_by_data, agg)
        for opt in options
    ]

    bucket_count = (
        _count_no_info_parents(form, params, qualifying_parents)
        if include_unanswered else 0
    )

    if value_type == "percentage":
        if include_unanswered:
            denom = len(qualifying_parents) + bucket_count
        else:
            denom = sum(counts)
    else:
        denom = None

    data = []
    for opt, count in zip(options, counts):
        val = (
            round((count / denom * 100), 2)
            if value_type == "percentage" and denom else count
        )
        data.append({
            "value": val,
            "label": opt.label,
            "group": opt.value,
            "color": opt.color,
        })

    if include_unanswered and bucket_count > 0:
        bucket_val = (
            round((bucket_count / denom * 100), 2)
            if value_type == "percentage" and denom else bucket_count
        )
        data.append({
            "value": bucket_val,
            "label": "No information available",
            "group": "_no_info",
            "color": "#bfbfbf",
        })

    labels = [d["label"] for d in data]
    return data, labels


# -- Number question handler --

def handle_number_question(form, question, params):
    """Handle number questions."""
    form_id = form.id
    group_by = params.get("group_by")
    repeat_agg = params.get("repeat_agg", "average")
    value_type = params.get("value_type", "number")
    stack_by = params.get("stack_by")

    qs, is_latest, _ = get_base_monitoring_qs(
        form, form_id, params
    )
    data_ids = get_monitoring_data_ids(qs, is_latest)
    agg_func = AGG_FUNCS.get(repeat_agg, Avg)

    if stack_by == "parent_id":
        return handle_stack_by_parent(
            question, qs, is_latest,
            data_ids, params
        )

    if group_by == "parent_id":
        return _number_group_by_parent(
            question, data_ids, agg_func, value_type
        )

    if group_by == "date":
        return _number_group_by_date(
            question, data_ids, params
        )

    if group_by == "month":
        return _number_group_by_month(
            question, data_ids, agg_func, value_type, params
        )

    result = Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
        value__isnull=False,
    ).aggregate(agg_value=agg_func("value"))

    value = (
        round(result["agg_value"], 2)
        if result["agg_value"] else 0
    )
    return [{"value": value, "label": "Total"}], ["Total"]


def _number_group_by_parent(
    question, data_ids, agg_func, value_type
):
    """Number question grouped by parent_id."""
    results = Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
        value__isnull=False,
    ).values(
        parent_name=F("data__parent__name"),
        parent_id=F("data__parent_id"),
    ).annotate(
        agg_value=agg_func("value"),
    ).order_by("parent_name")

    data = [
        {
            "value": round(r["agg_value"], 2),
            "label": r["parent_name"],
            "group": str(r["parent_id"]),
        }
        for r in results
    ]

    if value_type == "percentage":
        total = sum(d["value"] for d in data)
        if total > 0:
            for d in data:
                d["value"] = round(
                    d["value"] / total * 100, 2
                )

    labels = [d["label"] for d in data]
    return data, labels


def _number_group_by_date(question, data_ids, params):
    """Number question grouped by date."""
    repeat_agg = params.get("repeat_agg", "average")
    agg_func = AGG_FUNCS.get(repeat_agg, Avg)
    date_qid = params.get("date_question_id")

    if date_qid:
        data = []
        for data_id in data_ids:
            date_answer = Answers.objects.filter(
                data_id=data_id,
                question_id=date_qid,
            ).first()
            if not date_answer or not date_answer.name:
                continue
            val_result = Answers.objects.filter(
                data_id=data_id,
                question_id=question.id,
                value__isnull=False,
            ).aggregate(agg_value=agg_func("value"))
            if val_result["agg_value"] is not None:
                date_str = format_date_group(
                    date_answer.name
                )
                data.append({
                    "value": round(
                        val_result["agg_value"], 2
                    ),
                    "label": date_str,
                    "group": date_str,
                })
    else:
        results = Answers.objects.filter(
            data_id__in=data_ids,
            question_id=question.id,
            value__isnull=False,
        ).values(
            date=F("data__created__date"),
        ).annotate(
            agg_value=agg_func("value"),
        ).order_by("date")
        data = [
            {
                "value": round(r["agg_value"], 2),
                "label": format_date_group(r["date"]),
                "group": format_date_group(r["date"]),
            }
            for r in results
        ]

    data.sort(key=lambda x: x["group"])
    if _should_fill_gaps(params):
        data = fill_date_gaps(
            data, params["from_date"], params["to_date"]
        )
    labels = [d["label"] for d in data]
    return data, labels


def _number_group_by_month(
    question, data_ids, agg_func, value_type, params
):
    """Number question grouped by month.

    When date_question_id is provided, bucket by the month of that
    date answer (via a Subquery) instead of FormData.created so the
    x-axis aligns with the filter's date dimension.
    """
    date_qid = params.get("date_question_id")

    base = Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
        value__isnull=False,
    )

    if date_qid:
        date_sq = Answers.objects.filter(
            data_id=OuterRef("data_id"),
            question_id=date_qid,
            name__isnull=False,
        ).values("name")[:1]
        results = base.annotate(
            date_name=Subquery(date_sq),
        ).filter(
            date_name__isnull=False,
        ).annotate(
            month_key=Substr("date_name", 1, 7),
        ).values("month_key").annotate(
            agg_value=agg_func("value"),
        ).order_by("month_key")
        data = [
            {
                "value": round(r["agg_value"], 2),
                "label": format_month_label(r["month_key"]),
                "group": r["month_key"],
            }
            for r in results if r["agg_value"] is not None
        ]
    else:
        results = base.annotate(
            month=TruncMonth("data__created"),
        ).values("month").annotate(
            agg_value=agg_func("value"),
        ).order_by("month")
        data = [
            {
                "value": round(r["agg_value"], 2),
                "label": format_month_label(r["month"]),
                "group": format_month_group(r["month"]),
            }
            for r in results
        ]

    if value_type == "percentage":
        total = sum(d["value"] for d in data)
        if total > 0:
            for d in data:
                d["value"] = round(
                    d["value"] / total * 100, 2
                )

    if _should_fill_gaps(params):
        data = fill_month_gaps(
            data, params["from_date"], params["to_date"]
        )

    labels = [d["label"] for d in data]
    return data, labels


# -- Stack handlers --

def handle_stack_by_option(
    question, options, stack_question, stack_options,
    data_ids, qs, is_latest, params, values_by_data=None
):
    """Handle stack_by=option: stacked bar charts.

    `question`/`options` are what the bars are measured on;
    `stack_question`/`stack_options` are what the columns come from.
    They are the same object unless the caller passed a stack question
    (VIZ-015), in which case only the cross-tab branch reads both.
    """
    group_by = params.get("group_by")
    value_type = params.get("value_type", "number")
    agg = params.get("repeat_agg", "average")

    labels = build_stack_labels(stack_options)
    colors = [o.color for o in stack_options]
    # A multi-select answer belongs to several columns at once, so its
    # columns do not sum to the number of submissions. That only matters
    # for the percentage denominator -- see D-1.
    is_multi = stack_question.type == QuestionTypes.multiple_option

    if group_by in ("month", "date"):
        return _stack_option_by_period(
            stack_question, stack_options, labels, colors,
            data_ids, value_type, is_multi, params, period=group_by,
            values_by_data=values_by_data, agg=agg
        )

    if group_by == "parent_id":
        return _stack_option_by_parent(
            stack_question, stack_options, labels, colors,
            data_ids, qs, is_latest,
            values_by_data=values_by_data, agg=agg
        )

    if group_by == "option":
        return _stack_option_crosstab(
            question, options, stack_question, stack_options,
            labels, colors, data_ids, value_type, is_multi,
            values_by_data=values_by_data, agg=agg
        )

    return {
        "data": [], "labels": [],
        "stack_labels": [], "colors": [],
    }


def _percentage_denominator(cells, submission_ids, is_multi):
    """What a stacked bar's percentages divide by (D-1).

    Summing the row's own columns is the number of *selections*, which
    equals the number of submissions only for a single-select question.
    For a multi-select it does not, and dividing by it answers "what
    share of all selections is this option" -- a sentence nobody asked
    for that reads exactly like the one they did. Multi-select divides
    by distinct submissions instead, so a column reads "this share of
    submissions chose it" and the row may legitimately exceed 100.
    """
    if is_multi:
        return len(submission_ids)
    return sum(cells)


def _apply_percentage(row, labels, cells, submission_ids, is_multi):
    """Rewrite a row's cells as percentages of its own bar, in place."""
    denominator = _percentage_denominator(
        cells, submission_ids, is_multi
    )
    if denominator <= 0:
        return
    for label in labels:
        row[label] = round(row[label] / denominator * 100, 2)


def _stack_option_by_period(
    question, options, labels, colors,
    data_ids, value_type, is_multi, params, period="month",
    values_by_data=None, agg="average"
):
    """Stack by option, grouped by month or by day.

    Fetches answers once and buckets in Python -- O(N) instead of
    O(periods x options) queries. Honors date_question_id when
    provided so the bucket aligns with the filter dimension.
    """
    date_qid = params.get("date_question_id")
    option_values = {o.value for o in options}

    base = Answers.objects.filter(
        data_id__in=data_ids,
        question_id=question.id,
    )

    # The two periods differ only in how wide the bucket is: 7 leading
    # characters of an ISO date is its month, 10 is its day. Everything
    # after this block is identical, which is why group_by=date is a
    # parameter here rather than a second copy of the function.
    by_day = period == "date"
    width = 10 if by_day else 7
    format_label = format_date_group if by_day else format_month_label

    if date_qid:
        date_sq = Answers.objects.filter(
            data_id=OuterRef("data_id"),
            question_id=date_qid,
            name__isnull=False,
        ).values("name")[:1]
        rows = base.annotate(
            date_name=Subquery(date_sq),
        ).filter(
            date_name__isnull=False,
        ).annotate(
            period_key=Substr("date_name", 1, width),
        ).values("period_key", "options", "data_id")
        get_key = lambda r: r["period_key"]  # noqa: E731
    elif by_day:
        rows = base.values(
            "options", "data_id", day=F("data__created__date"),
        )
        get_key = lambda r: format_date_group(r["day"])  # noqa: E731
    else:
        rows = base.annotate(
            month=TruncMonth("data__created"),
        ).values("month", "options", "data_id")
        get_key = lambda r: format_month_group(r["month"])  # noqa: E731

    # Submission ids per (period, option), not a running count — see
    # `cell_value`. A count is len() of the list.
    buckets = defaultdict(lambda: defaultdict(list))
    submissions = defaultdict(set)
    for r in rows:
        key = get_key(r)
        if not key:
            continue
        submissions[key].add(r["data_id"])
        for v in (r["options"] or []):
            if v in option_values:
                buckets[key][v].append(r["data_id"])

    data = []
    for key in sorted(buckets.keys()):
        row = {"group": key, "label": format_label(key)}
        cells = [
            cell_value(buckets[key].get(o.value, []), values_by_data, agg)
            for o in options
        ]
        for label, cell in zip(labels, cells):
            row[label] = cell
        if value_type == "percentage":
            _apply_percentage(
                row, labels, cells, submissions[key], is_multi
            )
        data.append(row)

    # No gap filling: fill_month_gaps injects {value, label, group}
    # rows, which carry none of the stack columns and would render as
    # holes in the chart rather than as empty months.
    return {
        "data": data,
        "labels": [d["label"] for d in data],
        "stack_labels": labels,
        "colors": colors,
    }


def _stack_option_by_parent(
    question, options, labels, colors,
    data_ids, qs, is_latest, values_by_data=None, agg="average"
):
    """Stack by option, grouped by parent_id.

    Handles three data shapes:
      - is_latest=True: qs rows are parent FormData with a `latest_id`
        annotation pointing to each parent's most-recent monitoring
        submission. Answer counts are read from that single submission.
      - is_latest=False, monitoring-form query: data_ids reference
        monitoring submissions; parents are derived via their parent_id.
        Answer counts aggregate all matching submissions per parent.
      - is_latest=False, REGISTRATION-form query (akvo-mis-9d8): data_ids
        ARE registration submissions themselves (parent__isnull=True).
        Parents = qs directly; p_data_ids = [parent.id].
    """
    # Distinguish monitoring vs registration by probing for a parent_id.
    is_registration_form = False
    if is_latest:
        parents = qs
    else:
        parent_ids = list(FormData.objects.filter(
            id__in=data_ids,
            parent__isnull=False,
        ).values_list("parent_id", flat=True).distinct())
        if parent_ids:
            # is_pending / is_draft are re-checked on the parent here,
            # not inherited: data_ids bound the *children*, and a
            # pending or draft registration with an approved monitoring
            # submission would otherwise be drawn under
            # measure=all_submissions while current_state excludes it
            # -- the same site answering differently per measure (D-3).
            parents = FormData.objects.filter(
                id__in=parent_ids,
                is_pending=False,
                is_draft=False,
            )
        else:
            # Registration-form path: qs IS the list of registrations.
            parents = qs
            is_registration_form = True

    data = []
    for parent in parents:
        if is_latest:
            p_data_ids = [parent.latest_id]
            p_name = parent.name
        elif is_registration_form:
            p_data_ids = [parent.id]
            p_name = parent.name
        else:
            p_data_ids = list(FormData.objects.filter(
                id__in=data_ids,
                parent_id=parent.id,
            ).values_list("id", flat=True))
            p_name = parent.name

        # One query per site rather than one per (site, option): the
        # answers are fetched once and bucketed here, which the value
        # question needs anyway — it has to know WHICH submissions are
        # in a cell, not just how many.
        chosen = defaultdict(list)
        for data_id, opts in Answers.objects.filter(
            data_id__in=p_data_ids,
            question_id=question.id,
        ).values_list("data_id", "options"):
            for value in (opts or []):
                chosen[value].append(data_id)

        row = {"label": p_name, "group": parent.id}
        for option, label in zip(options, labels):
            row[label] = cell_value(
                chosen.get(option.value, []), values_by_data, agg
            )
        data.append(row)

    return {
        "data": data,
        "labels": [d["label"] for d in data],
        "stack_labels": labels,
        "colors": colors,
    }


def _stack_option_crosstab(
    question, options, stack_question, stack_options,
    labels, colors, data_ids, value_type, is_multi,
    values_by_data=None, agg="average"
):
    """Cross-tab: bars are one question's options, columns another's.

    Two flat queries and Python bucketing, deliberately. The obvious
    implementation is one COUNT per (bar, column) pair, which is
    O(options x stack options) round trips for a result that is small
    by construction -- both option sets come from QuestionOptions.
    """
    bar_values = [o.value for o in options]
    bar_value_set = set(bar_values)
    bar_labels = build_stack_labels(options)
    stack_values = [o.value for o in stack_options]
    stack_value_set = set(stack_values)

    def selections(question_id, allowed):
        chosen = defaultdict(set)
        rows = Answers.objects.filter(
            data_id__in=data_ids,
            question_id=question_id,
        ).values_list("data_id", "options")
        for data_id, opts in rows:
            for value in (opts or []):
                if value in allowed:
                    chosen[data_id].add(value)
        return chosen

    bars_by_data = selections(question.id, bar_value_set)
    stacks_by_data = selections(stack_question.id, stack_value_set)

    # The submissions in each (bar, column) cell, rather than a running
    # count: a count is len() of the set, and a value question needs the
    # ids themselves to look their numbers up (VIZ-015.b).
    members = defaultdict(lambda: defaultdict(list))
    submissions = defaultdict(set)
    for data_id, bars in bars_by_data.items():
        stacks = stacks_by_data.get(data_id)
        if not stacks:
            # No answer to the stacking question: this submission
            # belongs to no column, so it leaves the chart. Bars are
            # shorter than the same chart unstacked -- see the design
            # doc's "bars shrink when stacking is turned on".
            continue
        for bar in bars:
            submissions[bar].add(data_id)
            for stack in stacks:
                members[bar][stack].append(data_id)

    indexed = []
    for index, value in enumerate(bar_values):
        row = {"group": value, "label": bar_labels[index]}
        cells = [
            cell_value(members[value].get(s, []), values_by_data, agg)
            for s in stack_values
        ]
        for label, cell in zip(labels, cells):
            row[label] = cell
        total = sum(cells)
        if value_type == "percentage":
            _apply_percentage(
                row, labels, cells, submissions[value], is_multi
            )
        # D-2: bars read by magnitude, so they sort by total
        # descending. The index breaks ties on the question's own
        # option order, so two equal bars cannot swap between renders.
        # Sorting on `total` and not on the percentage keeps the bar
        # order identical in both value_types.
        indexed.append((-total, index, row))

    indexed.sort(key=lambda entry: (entry[0], entry[1]))
    data = [row for _, _, row in indexed]

    return {
        "data": data,
        "labels": [d["label"] for d in data],
        "stack_labels": labels,
        "colors": colors,
    }


def handle_stack_by_parent(
    question, qs, is_latest, data_ids, params
):
    """Handle stack_by=parent_id: multi-line charts."""
    group_by = params.get("group_by")
    repeat_agg = params.get("repeat_agg", "average")
    agg_func = AGG_FUNCS.get(repeat_agg, Avg)

    if is_latest:
        parents = list(
            qs.values("id", "name", "latest_id")
        )
    else:
        parent_ids = FormData.objects.filter(
            id__in=data_ids,
            parent__isnull=False,
        ).values_list(
            "parent_id", flat=True
        ).distinct()
        # Same re-check as _stack_option_by_parent: data_ids bound the
        # children, so a pending or draft parent would otherwise appear
        # here and nowhere else (D-3).
        parent_data = FormData.objects.filter(
            id__in=parent_ids,
            is_pending=False,
            is_draft=False,
        ).values("id", "name")
        parents = [
            {
                "id": p["id"],
                "name": p["name"],
                "data_ids": list(
                    FormData.objects.filter(
                        id__in=data_ids,
                        parent_id=p["id"],
                    ).values_list("id", flat=True)
                ),
            }
            for p in parent_data
        ]

    parent_names = [p["name"] for p in parents]

    if group_by == "date":
        return _stack_parent_by_date(
            question, parents, is_latest,
            parent_names, agg_func, params
        )

    if group_by == "month":
        return _stack_parent_by_month(
            question, parents, is_latest,
            parent_names, agg_func, params
        )

    return {"data": [], "labels": [], "stack_labels": []}


def _stack_parent_by_date(
    question, parents, is_latest,
    parent_names, agg_func, params
):
    """Stack by parent_id, grouped by date.

    Prefetches date keys and aggregated values per data_id in two
    bulk queries instead of N+1 per-point queries.
    """
    date_qid = params.get("date_question_id")

    all_data_ids = []
    for p in parents:
        if is_latest:
            all_data_ids.append(p["latest_id"])
        else:
            all_data_ids.extend(p["data_ids"])

    if date_qid:
        date_rows = Answers.objects.filter(
            data_id__in=all_data_ids,
            question_id=date_qid,
            name__isnull=False,
        ).values("data_id", "name")
        date_map = {
            r["data_id"]: format_date_group(r["name"])
            for r in date_rows
        }
    else:
        fd_rows = FormData.objects.filter(
            id__in=all_data_ids,
        ).values("id", "created")
        date_map = {
            r["id"]: format_date_group(r["created"])
            for r in fd_rows
        }

    val_rows = Answers.objects.filter(
        data_id__in=all_data_ids,
        question_id=question.id,
        value__isnull=False,
    ).values("data_id").annotate(
        agg_value=agg_func("value"),
    )
    val_map = {
        r["data_id"]: r["agg_value"]
        for r in val_rows
        if r["agg_value"] is not None
    }

    all_rows = {}
    for p in parents:
        p_ids = (
            [p["latest_id"]] if is_latest
            else p["data_ids"]
        )
        for data_id in p_ids:
            date_key = date_map.get(data_id)
            agg_val = val_map.get(data_id)
            if not date_key or agg_val is None:
                continue
            if date_key not in all_rows:
                all_rows[date_key] = {"date": date_key}
            all_rows[date_key][p["name"]] = round(agg_val, 2)

    data = [all_rows[k] for k in sorted(all_rows.keys())]
    labels = sorted(all_rows.keys())
    return {
        "data": data,
        "labels": labels,
        "stack_labels": parent_names,
    }


def _stack_parent_by_month(
    question, parents, is_latest,
    parent_names, agg_func, params
):
    """Stack by parent_id, grouped by month.

    When date_question_id is provided, buckets by the month of that
    date answer (via Subquery) instead of FormData.created.
    """
    date_qid = params.get("date_question_id")
    all_rows = {}

    for p in parents:
        p_ids = (
            [p["latest_id"]] if is_latest
            else p["data_ids"]
        )

        base = Answers.objects.filter(
            data_id__in=p_ids,
            question_id=question.id,
            value__isnull=False,
        )

        if date_qid:
            date_sq = Answers.objects.filter(
                data_id=OuterRef("data_id"),
                question_id=date_qid,
                name__isnull=False,
            ).values("name")[:1]
            results = base.annotate(
                date_name=Subquery(date_sq),
            ).filter(
                date_name__isnull=False,
            ).annotate(
                month_key=Substr("date_name", 1, 7),
            ).values("month_key").annotate(
                agg_value=agg_func("value"),
            ).order_by("month_key")
            for r in results:
                if r["agg_value"] is None:
                    continue
                month_key = r["month_key"]
                if month_key not in all_rows:
                    all_rows[month_key] = {
                        "month": format_month_label(month_key),
                    }
                all_rows[month_key][p["name"]] = round(
                    r["agg_value"], 2,
                )
        else:
            results = base.annotate(
                month=TruncMonth("data__created"),
            ).values("month").annotate(
                agg_value=agg_func("value"),
            ).order_by("month")
            for r in results:
                month_key = format_month_group(r["month"])
                if month_key not in all_rows:
                    all_rows[month_key] = {
                        "month": format_month_label(
                            r["month"]
                        ),
                    }
                all_rows[month_key][p["name"]] = round(
                    r["agg_value"], 2,
                )

    data = [all_rows[k] for k in sorted(all_rows.keys())]
    labels = [d["month"] for d in data]
    return {
        "data": data,
        "labels": labels,
        "stack_labels": parent_names,
    }
