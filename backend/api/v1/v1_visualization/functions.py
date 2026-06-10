from django.db import transaction, connection
from django.db.models import (
    Q, Subquery, OuterRef,
)
from datetime import datetime as dt_datetime, timedelta, date
from rest_framework.exceptions import ValidationError

from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_forms.models import Questions
from api.v1.v1_profile.models import Administration


@transaction.atomic
def refresh_materialized_data():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_matviews WHERE matviewname = 'view_data_options'"
        )
        if not cursor.fetchone():
            return
        cursor.execute(
            "REFRESH MATERIALIZED VIEW view_data_options;"
        )


# -- Shared helpers --

def apply_administration_filter(queryset, administration_id):
    """Filter queryset by administration hierarchy."""
    try:
        adm = Administration.objects.get(
            pk=administration_id
        )
    except Administration.DoesNotExist:
        return queryset.none()
    adm_path = (
        f"{adm.path}{adm.id}." if adm.path
        else f"{adm.id}."
    )
    return queryset.filter(
        Q(administration_id=administration_id)
        | Q(administration__path__startswith=adm_path)
    )


def resolve_default_administration_id(administration_id):
    """Fall back to the root administration (parent IS NULL) when no
    administration_id is provided. These visualization endpoints are
    public, so we scope to the top-level country by default instead of
    leaking data across unrelated administrations."""
    if administration_id:
        return administration_id
    root = Administration.objects.filter(
        parent__isnull=True
    ).values_list("id", flat=True).first()
    if root is None:
        raise ValidationError(
            "No root administration configured; "
            "administration_id is required."
        )
    return root


def build_date_filters(params):
    """Collect from_date/to_date/date_question_id into a dict.

    Returns an empty dict when no date filter is set, so callers can
    pass `date_filters or None` to subqueries that treat falsy as
    'no filter'.
    """
    date_filters = {}
    if params.get("from_date"):
        date_filters["from_date"] = params["from_date"]
    if params.get("to_date"):
        date_filters["to_date"] = params["to_date"]
    if params.get("date_question_id"):
        date_filters["date_question_id"] = params["date_question_id"]
    return date_filters


def _to_date_upper_bound(value):
    """Produce an inclusive upper bound for an ISO date-time string.

    `Answers.name` stores dates as ISO-8601 with time (e.g.
    '2025-01-20T00:00:00.000Z'), so a plain `name__lte='2025-01-20'`
    excludes same-day records lexically. Appending the latest time
    makes `<=` work as an inclusive day boundary.
    """
    return f"{value}T23:59:59.999Z"


def latest_monitoring_subquery(form_id, date_filters=None):
    """Subquery: latest monitoring FormData ID per parent."""
    qs = FormData.objects.filter(
        parent=OuterRef("pk"),
        form_id=form_id,
        is_pending=False,
        is_draft=False,
    )
    if date_filters:
        date_qid = date_filters.get("date_question_id")
        if date_qid:
            sub = Answers.objects.filter(
                data=OuterRef("pk"),
                question_id=date_qid,
            )
            if date_filters.get("from_date"):
                sub = sub.filter(
                    name__gte=date_filters["from_date"],
                )
            if date_filters.get("to_date"):
                sub = sub.filter(
                    name__lte=_to_date_upper_bound(
                        date_filters["to_date"]
                    ),
                )
            qs = qs.filter(
                pk__in=Subquery(sub.values("data_id"))
            )
        else:
            if date_filters.get("from_date"):
                qs = qs.filter(
                    created__date__gte=(
                        date_filters["from_date"]
                    )
                )
            if date_filters.get("to_date"):
                qs = qs.filter(
                    created__date__lte=(
                        date_filters["to_date"]
                    )
                )
    return Subquery(
        qs.order_by("-created").values("id")[:1]
    )


def parse_criteria_string(value, allowed_types):
    """Parse a `criteria=type:qid:value,...` query string.

    Returns a list of {"type", "parts"} dicts. For option_in the
    value is split on `|` into a list; for other option operators
    the value is passed through as a string; thresholds are coerced
    to float. Raises ValueError with a user-visible message on any
    malformed fragment so callers can surface a 400.
    """
    parsed = []
    for item in value.split(","):
        parts = item.strip().split(":")
        if len(parts) < 3:
            raise ValueError(
                f"Invalid criteria format: '{item}'."
                " Expected type:qid:value"
            )
        ctype = parts[0]
        if ctype not in allowed_types:
            raise ValueError(
                f"Invalid criteria type: '{ctype}'."
                f" Options: {sorted(allowed_types)}"
            )
        try:
            if ctype in ("option_equals", "option_contains"):
                qid = int(parts[1])
                normalized = [qid, parts[2]]
            elif ctype == "option_in":
                qid = int(parts[1])
                values = [
                    v for v in parts[2].split("|") if v
                ]
                if not values:
                    raise ValueError(
                        "option_in requires at least one value:"
                        f" '{item}'"
                    )
                normalized = [qid, values]
            elif ctype in ("threshold_gt", "threshold_lt"):
                qid = int(parts[1])
                threshold = float(parts[2])
                normalized = [qid, threshold]
            elif ctype == "overdue":
                completion_qid = int(parts[1])
                deadline_qid = int(parts[2])
                normalized = [completion_qid, deadline_qid]
            else:
                normalized = parts[1:]
        except ValueError as e:
            # Re-raise our own messages; wrap numeric parse failures
            if "criteria" in str(e) or "option_in" in str(e):
                raise
            raise ValueError(
                f"Invalid numeric value in criteria: '{item}'."
            )
        parsed.append({"type": ctype, "parts": normalized})
    return parsed


def _criterion_matching_ids(data_ids, criterion):
    """Return iterable of data_ids matching a single criterion."""
    ctype = criterion["type"]
    parts = criterion["parts"]
    if ctype in ("option_equals", "option_contains"):
        qid, value = parts
        return Answers.objects.filter(
            data_id__in=data_ids,
            question_id=qid,
            options__contains=[value],
        ).values_list("data_id", flat=True)
    if ctype == "option_in":
        qid, values = parts
        or_q = Q()
        for v in values:
            or_q |= Q(options__contains=[v])
        return Answers.objects.filter(
            or_q,
            data_id__in=data_ids,
            question_id=qid,
        ).values_list("data_id", flat=True)
    if ctype == "threshold_gt":
        qid, threshold = parts
        return Answers.objects.filter(
            data_id__in=data_ids,
            question_id=qid,
            value__gt=threshold,
        ).values_list("data_id", flat=True)
    if ctype == "threshold_lt":
        qid, threshold = parts
        return Answers.objects.filter(
            data_id__in=data_ids,
            question_id=qid,
            value__lt=threshold,
        ).values_list("data_id", flat=True)
    return []


def narrow_data_ids_by_criteria(data_ids, criteria):
    """Return subset of data_ids where ALL criteria match (AND).

    Each criterion is evaluated as a separate Answers query over the
    current candidate set; the intersection shrinks monotonically so
    criteria that narrow heavily short-circuit the remaining work.
    """
    if not criteria:
        return list(data_ids)
    matching = set(data_ids)
    for criterion in criteria:
        if not matching:
            break
        ids = set(
            _criterion_matching_ids(list(matching), criterion)
        )
        matching &= ids
    return [i for i in data_ids if i in matching]


def apply_parent_criteria_to_qs(qs, is_latest, parent_criteria):
    """Narrow by criteria on the PARENT (registration) form's answers.

    In latest mode `qs` rows are parent FormData (with `latest_id`),
    so we match directly against `qs.id`. In non-latest mode `qs`
    rows are monitoring FormData, so we match against `qs.parent_id`.
    """
    if not parent_criteria:
        return qs
    if is_latest:
        parent_ids = list(qs.values_list("id", flat=True))
        narrowed = narrow_data_ids_by_criteria(
            parent_ids, parent_criteria,
        )
        return qs.filter(id__in=narrowed)
    parent_ids = list(
        qs.values_list("parent_id", flat=True).distinct()
    )
    narrowed = narrow_data_ids_by_criteria(
        parent_ids, parent_criteria,
    )
    return qs.filter(parent_id__in=narrowed)


def apply_criteria_to_monitoring_qs(qs, is_latest, criteria):
    """Narrow a base monitoring queryset by multi-criteria filter.

    Fetches the current data_ids from `qs` (either `latest_id` or
    `id` depending on the mode), intersects them against each
    criterion's matching set, then re-filters `qs` so downstream
    callers see a consistent narrowed view.
    """
    if not criteria:
        return qs
    if is_latest:
        ids = list(qs.values_list("latest_id", flat=True))
        narrowed = narrow_data_ids_by_criteria(ids, criteria)
        return qs.filter(latest_id__in=narrowed)
    ids = list(qs.values_list("id", flat=True))
    narrowed = narrow_data_ids_by_criteria(ids, criteria)
    return qs.filter(id__in=narrowed)


def split_criteria_by_form(criteria, form_id, parent_form_id):
    """Split parsed criteria list into same-form and parent-form."""
    if not criteria:
        return None, None
    qids = {c["parts"][0] for c in criteria}
    on_form = set(
        Questions.objects.filter(
            pk__in=qids, form_id=form_id,
        ).values_list("pk", flat=True)
    )
    on_parent = set()
    if parent_form_id:
        remaining = qids - on_form
        if remaining:
            on_parent = set(
                Questions.objects.filter(
                    pk__in=remaining,
                    form_id=parent_form_id,
                ).values_list("pk", flat=True)
            )
    same = [c for c in criteria if c["parts"][0] in on_form]
    parent = [c for c in criteria if c["parts"][0] in on_parent]
    return same or None, parent or None


def get_base_monitoring_qs(form, monitoring_form_id, params):
    """Build base queryset for monitoring data.

    Returns:
        Tuple of (queryset, is_monitoring_form, date_filters)
    """
    monitoring = params.get("monitoring", "latest")
    from_date = params.get("from_date")
    to_date = params.get("to_date")
    date_question_id = params.get("date_question_id")
    administration_id = params.get("administration_id")

    date_filters = build_date_filters(params)

    is_monitoring = form.parent is not None
    parent_form = (
        form.parent if is_monitoring else form
    )

    if is_monitoring and monitoring == "latest":
        qs = FormData.objects.filter(
            form=parent_form,
            parent__isnull=True,
            is_pending=False,
            is_draft=False,
        ).annotate(
            latest_id=latest_monitoring_subquery(
                monitoring_form_id,
                date_filters or None,
            ),
        ).filter(latest_id__isnull=False)

        if administration_id:
            qs = apply_administration_filter(
                qs, administration_id
            )
        qs = apply_criteria_to_monitoring_qs(
            qs, True, params.get("criteria"),
        )
        qs = apply_parent_criteria_to_qs(
            qs, True, params.get("parent_criteria"),
        )
        return qs, True, date_filters

    qs = FormData.objects.filter(
        form_id=monitoring_form_id,
        is_pending=False,
        is_draft=False,
    )
    if administration_id:
        qs = apply_administration_filter(
            qs, administration_id
        )

    if date_filters:
        if date_question_id:
            matching_ids = Answers.objects.filter(
                data__form_id=monitoring_form_id,
                question_id=date_question_id,
                name__isnull=False,
            )
            if from_date:
                matching_ids = matching_ids.filter(
                    name__gte=from_date
                )
            if to_date:
                matching_ids = matching_ids.filter(
                    name__lte=_to_date_upper_bound(to_date)
                )
            qs = qs.filter(
                id__in=matching_ids.values("data_id")
            )
        else:
            if from_date:
                qs = qs.filter(
                    created__date__gte=from_date
                )
            if to_date:
                qs = qs.filter(
                    created__date__lte=to_date
                )

    qs = apply_criteria_to_monitoring_qs(
        qs, False, params.get("criteria"),
    )
    qs = apply_parent_criteria_to_qs(
        qs, False, params.get("parent_criteria"),
    )
    return qs, False, date_filters


def get_monitoring_data_ids(qs, is_latest_mode):
    """Extract monitoring data IDs from queryset."""
    if is_latest_mode:
        return list(
            qs.values_list("latest_id", flat=True)
        )
    return list(qs.values_list("id", flat=True))


def format_month_label(dt):
    """Format a date/datetime to 'Mon YYYY' label."""
    if hasattr(dt, 'strftime'):
        return dt.strftime("%b %Y")
    try:
        d = dt_datetime.strptime(str(dt)[:7], "%Y-%m")
        return d.strftime("%b %Y")
    except (ValueError, TypeError):
        return str(dt)


def format_month_group(dt):
    """Format to YYYY-MM group key."""
    if hasattr(dt, 'strftime'):
        return dt.strftime("%Y-%m")
    return str(dt)[:7]


def format_date_group(dt):
    """Format to YYYY-MM-DD group key."""
    if hasattr(dt, 'strftime'):
        return dt.strftime("%Y-%m-%d")
    return str(dt)[:10]


def _parse_iso_date(value):
    """Parse YYYY-MM-DD string or pass through date/datetime."""
    if isinstance(value, (dt_datetime, date)):
        return value if isinstance(value, date) else value.date()
    return dt_datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def fill_month_gaps(data, from_date, to_date):
    """Return a new list with zero-filled month rows between bounds.

    Preserves existing rows (by `group` key) and inserts zero rows
    for every month in [from_date, to_date] that is missing. Output
    is sorted chronologically by `group`.
    """
    start = _parse_iso_date(from_date).replace(day=1)
    end = _parse_iso_date(to_date).replace(day=1)
    existing = {row["group"]: row for row in data}

    filled = []
    cursor = start
    while cursor <= end:
        key = cursor.strftime("%Y-%m")
        if key in existing:
            filled.append(existing[key])
        else:
            filled.append({
                "value": 0,
                "label": cursor.strftime("%b %Y"),
                "group": key,
            })
        # advance to first day of next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return filled


def fill_date_gaps(data, from_date, to_date):
    """Return a new list with zero-filled day rows between bounds.

    Preserves existing rows (by `group` key) and inserts zero rows
    for every day in [from_date, to_date] that is missing. Output
    is sorted chronologically by `group`.
    """
    start = _parse_iso_date(from_date)
    end = _parse_iso_date(to_date)
    existing = {row["group"]: row for row in data}

    filled = []
    cursor = start
    while cursor <= end:
        key = cursor.strftime("%Y-%m-%d")
        if key in existing:
            filled.append(existing[key])
        else:
            filled.append({
                "value": 0,
                "label": key,
                "group": key,
            })
        cursor = cursor + timedelta(days=1)
    return filled
