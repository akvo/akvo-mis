from collections import defaultdict

from django.db import transaction, connection
from django.db.models import (
    Q, Subquery, OuterRef,
)
from datetime import datetime as dt_datetime, timedelta, date
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import OpenApiExample, OpenApiParameter

from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_visualization.constants import (
    GLOBAL_CRITERIA_TYPES,
    GLOBAL_MATCH_VALUES,
    MAX_GLOBAL_CRITERIA,
)


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


def resolve_request_tenant(request):
    """The workspace a visualization request belongs to.

    Host first: these endpoints answer without a token, so a public
    dashboard served at a workspace address has to resolve the same
    workspace a logged-in reader does. The authenticated account is the
    fallback for single-host deployments, where no host names a
    workspace but the account still does — and TenantMiddleware has
    already refused any request where the two disagree, so consulting
    the host first can only narrow, never contradict.

    None means there is no workspace to be had: the base domain, or an
    install with BASE_DOMAIN unset and tenant-less accounts, which is
    how the test suite and every single-tenant deployment run.
    """
    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        return tenant
    return getattr(getattr(request, "user", None), "tenant", None)


def tenant_scoped_forms(tenant):
    """The forms a visualization request is allowed to name.

    form_id reaches these endpoints as a bare integer off the query
    string, so without this any workspace's aggregates are one guessed
    id away. Scoping the form scopes the question with it:
    ValuesFilterSerializer already rejects a question_id that does not
    belong to form_id.
    """
    forms = Forms.objects.all()
    if tenant is not None:
        forms = forms.filter(tenant=tenant)
    return forms


def resolve_default_administration_id(administration_id, tenant=None):
    """Fall back to the root administration (parent IS NULL) when no
    administration_id is provided. These visualization endpoints are
    public, so we scope to the top-level country by default instead of
    leaking data across unrelated administrations.

    The fallback is per workspace, because every tenant has its own
    root. An unscoped lookup here does not leak anyone's rows — it does
    something quieter and worse: it scopes the caller to somebody
    else's country, so every widget on a freshly opened dashboard
    reports 0 with nothing on screen to say why. Passing tenant=None
    keeps the install-wide lookup, which is right only where there is a
    single hierarchy to find.
    """
    if administration_id:
        return administration_id
    roots = Administration.objects.filter(parent__isnull=True)
    if tenant is not None:
        roots = roots.filter(tenant=tenant)
    # Ordered: .first() on an unordered queryset returns whatever the
    # planner hands back, which is how one deployment's answer came to
    # depend on which root happened to be read first.
    root = roots.order_by("id").values_list("id", flat=True).first()
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


# -- Dashboard-wide question filter (VIZ-027) --

OPTION_TYPES = [QuestionTypes.option, QuestionTypes.multiple_option]


def global_filter_scope(root_id, form_id, family_ids):
    """Forms a `(form_id, name)` filter reads (D-20): the whole family
    when `form_id` is the registration form, that form alone otherwise."""
    return family_ids if form_id == root_id else {form_id}


def parse_global_criteria(items, form):
    """Parse and family-check `global_criteria` (D-6, D-10, D-15, D-20,
    D-21).

    `items` holds one `<type>:<form_id>:<name>:<value>` per value, `<type>`
    being `option_in` or `option_not_in`,
    split at most three times so the value may contain `:`, `,` or `|`.
    Occurrences for the same `(form_id, name)` become one criterion whose
    values are ORed. Its `group` holds the live option questions of that
    name in the scope: every form of the family for the registration
    form, that monitoring form otherwise. Raises ValueError with a
    user-facing message.
    """
    if len(items) > MAX_GLOBAL_CRITERIA:
        raise ValueError(
            f"at most {MAX_GLOBAL_CRITERIA} values are allowed"
        )
    values_by_key = defaultdict(list)
    types = {}
    for item in items:
        parts = item.split(":", 3)
        if (
            len(parts) < 4 or parts[0] not in GLOBAL_CRITERIA_TYPES
            or not parts[2]
        ):
            raise ValueError(f"invalid entry: '{item}'")
        # ASCII digits only: "²".isdigit() is true but int("²") fails.
        if not (parts[1].isascii() and parts[1].isdigit()):
            raise ValueError(f"invalid form id: '{item}'")
        if not parts[3]:
            raise ValueError(f"{parts[0]} requires a value: '{item}'")
        key = (int(parts[1]), parts[2])
        if types.setdefault(key, parts[0]) != parts[0]:
            raise ValueError(
                "a filter cannot both show only and filter out: "
                f"'{parts[1]}:{parts[2]}'"
            )
        values_by_key[key].append(parts[3])

    root_id = form.parent_id or form.id
    family_ids = set(
        Forms.objects.filter(Q(pk=root_id) | Q(parent_id=root_id))
        .values_list("pk", flat=True)
    )
    questions = defaultdict(list)
    for pk, name, form_id in Questions.objects.filter(
        form_id__in=family_ids,
        name__in={name for _, name in values_by_key},
        type__in=OPTION_TYPES,
    ).values_list("pk", "name", "form_id"):
        questions[name].append((pk, form_id))

    criteria = []
    for (form_id, name), values in values_by_key.items():
        if form_id not in family_ids:
            raise ValueError(f"form {form_id} is not in this form family")
        scope = global_filter_scope(root_id, form_id, family_ids)
        group = [(pk, fid) for pk, fid in questions[name] if fid in scope]
        if not group:
            where = (
                f"form {form_id} or its monitoring forms"
                if form_id == root_id else f"form {form_id}"
            )
            raise ValueError(f"no option question '{name}' in {where}")
        criteria.append({
            "type": types[(form_id, name)],
            "form_id": form_id,
            "name": name,
            "values": values,
            "group": group,
        })
    return criteria


# VIZ-027: the OpenAPI shape of `global_criteria`, shared by the four
# endpoints. An array in the query, exploded: one repeated key per value.
GLOBAL_CRITERIA_PARAMETER = OpenApiParameter(
    name="global_criteria",
    required=False,
    # drf-spectacular 0.21 has no `many=`: spell the array out.
    type={"type": "array", "items": {"type": "string"}},
    style="form",
    explode=True,
    location=OpenApiParameter.QUERY,
    description=(
        "Dashboard filter. **One item = one option value, written "
        "whole:** `option_in:<form id>:<question name>:<option value>` "
        "(for example `option_in:12:weather_condition:cloudy`). Do not "
        "split an item over several boxes: every item is read on its own. "
        "For a second value, add a second whole item.\n\n"
        "`option_in` shows only the registration datapoints whose latest "
        "answer to that question is one of the values (the dashboard's "
        "filter bar). `option_not_in` instead hides them; one question "
        "uses one of the two. `<form id>` sets the scope: the "
        "registration form reads the whole form family, a monitoring form "
        "that form only (VIZ-027 D-15, D-20, D-21)."
    ),
    # Fills Swagger's boxes with the shape to edit, one whole item.
    examples=[
        OpenApiExample(
            "Show only one value",
            value=["option_in:<form id>:<question name>:<option value>"],
        ),
        OpenApiExample(
            "Show only two values of one question",
            value=[
                "option_in:<form id>:<question name>:<value 1>",
                "option_in:<form id>:<question name>:<value 2>",
            ],
        ),
        OpenApiExample(
            "Hide one value",
            value=["option_not_in:<form id>:<question name>:<option value>"],
        ),
    ],
)

# VIZ-027 D-21: how different `global_criteria` filters combine.
GLOBAL_MATCH_PARAMETER = OpenApiParameter(
    name="global_match",
    required=False,
    type=str,
    enum=sorted(GLOBAL_MATCH_VALUES),
    default="all",
    location=OpenApiParameter.QUERY,
    description=(
        "How different filters (question names) combine: `all` keeps a "
        "datapoint that passes every filter (AND), `any` one that passes "
        "at least one (OR). Values of one question are always ORed."
    ),
)


def parse_request_global_criteria(request, form):
    """VIZ-027: the request's `global_criteria`, parsed against `form`.

    Call it AFTER check_ids and the tenant-scoped form lookup, never from
    a serializer. It reads `getlist("global_criteria")`, the same list
    check_ids saw. A DRF ListField would also accept
    `global_criteria[0]=...`, which check_ids never sees: that would let an
    anonymous caller filter on a question the dashboard does not offer.

    Returns ({"match", "criteria"}, None), (None, None) when absent, or
    (None, "<parameter>: <reason>") for a 400. `match` is `global_match`,
    "all" unless the caller asks for "any" (D-21).
    """
    items = request.query_params.getlist("global_criteria")
    match = request.query_params.get("global_match") or "all"
    if match not in GLOBAL_MATCH_VALUES:
        return None, "global_match: must be 'all' or 'any'"
    if not items:
        return None, None
    try:
        return {
            "match": match,
            "criteria": parse_global_criteria(items, form),
        }, None
    except ValueError as error:
        return None, f"global_criteria: {error}"


def _any_option(values):
    """OR of options__contains=[v]. Answers.options is a JSONField, so
    ArrayField lookups such as __overlap do not exist."""
    q = Q()
    for value in values:
        q |= Q(options__contains=[value])
    return q


def in_date_range(date_filters, form_ids, date_name):
    """Q over FormData: inside the dashboard's date range (D-14).

    The date question is matched by NAME (`date_name`) on each form of the
    group. A form without a same-named question uses `created`. Lazy: no
    query runs until the widget's own query does.
    """
    # A date question without a range bounds nothing: it must not drop
    # the submissions that skipped the date question.
    if not date_filters or not (
        date_filters.get("from_date") or date_filters.get("to_date")
    ):
        return Q()
    by_created = Q()
    if date_filters.get("from_date"):
        by_created &= Q(created__date__gte=date_filters["from_date"])
    if date_filters.get("to_date"):
        by_created &= Q(created__date__lte=date_filters["to_date"])
    if not date_name:
        return by_created
    date_questions = Questions.objects.filter(
        name=date_name, form_id__in=form_ids, type=QuestionTypes.date,
    )
    answers = Answers.objects.filter(question__in=date_questions)
    if date_filters.get("from_date"):
        answers = answers.filter(name__gte=date_filters["from_date"])
    if date_filters.get("to_date"):
        answers = answers.filter(
            name__lte=_to_date_upper_bound(date_filters["to_date"]),
        )
    forms_with_date = date_questions.values("form_id")
    return (
        Q(form_id__in=forms_with_date, pk__in=answers.values("data_id"))
        | (~Q(form_id__in=forms_with_date) & by_created)
    )


def matching_registrations_subqueries(
    criterion, root_form_id, date_filters, date_name=None,
):
    """Lazy querysets of registration ids that match, one per part (D-20).

    A registration matches when its latest answer in the criterion's
    scope contains one of its values: `option_in` keeps those rows,
    `option_not_in` removes them (D-21).

    Monitoring forms in the scope: per registration, the latest
    submission that answered one of the group's questions inside the
    range; it matches when its answer does. The registration form, when
    in the scope (family scope): its own answer, but only for
    registrations no such monitoring submission speaks for, since the
    registration answer is the oldest (D-8: no date range on it).

    Returned apart on purpose: an OR of sublinks inside one subquery
    cannot become a join, and Postgres then scans the whole `data` table
    per criterion. The caller tests the row's own column against each.

    Never NULL (D-5: one NULL would empty every chart): each part selects
    Answers.data_id, or the parent_id of submissions filtered with
    parent__isnull=False. Ignores Answers.index, so any matching repeat
    makes the registration match (D-9).
    """
    group = criterion["group"]
    registration_qids = [
        qid for qid, form_id in group if form_id == root_form_id
    ]
    monitoring_qids = [
        qid for qid, form_id in group if form_id != root_form_id
    ]

    def matching(qids):
        return Answers.objects.filter(
            _any_option(criterion["values"]), question_id__in=qids,
        )

    parts = []
    answered = None
    if monitoring_qids:
        form_ids = {
            form_id for _, form_id in group if form_id != root_form_id
        }
        answered = FormData.objects.filter(
            in_date_range(date_filters, form_ids, date_name),
            form_id__in=form_ids,
            parent__isnull=False,
            is_pending=False,
            is_draft=False,
            pk__in=Answers.objects.filter(
                question_id__in=monitoring_qids,
            ).values("data_id"),
        )
        # One DISTINCT ON pass, not a correlated subquery per
        # registration: BE-6 measured the correlated form at one loop per
        # registration (+145% on a 10,000-site family).
        latest_answered = (
            answered.order_by("parent_id", "-created", "-id")
            .distinct("parent_id")
            .values("id")
        )
        parts.append(FormData.objects.filter(
            pk__in=latest_answered,
            parent__isnull=False,
            id__in=matching(monitoring_qids).values("data_id"),
        ).values("parent_id"))
    if registration_qids:
        own = matching(registration_qids).filter(
            data__is_pending=False, data__is_draft=False,
        )
        if answered is not None:
            own = own.exclude(data_id__in=answered.values("parent_id"))
        parts.append(own.values("data_id"))
    return parts


def date_question_name(date_qid):
    """The `name` of a date question id, or None (D-18).

    Includes soft-deleted rows: a form edit replaces "Date of visit" with
    a new live row of the same name, while a published dashboard keeps
    the old id. Matching by name then reaches the live successor instead
    of silently falling back to `created`.
    """
    if not date_qid:
        return None
    return (
        Questions.objects_with_deleted.filter(pk=date_qid)
        .values_list("name", flat=True).first()
    )


def resolve_date_question(date_qid, form_id):
    """VIZ-027 D-18: the dashboard's date question, as asked on `form_id`.

    Returns `(id, name)`: the live date question on `form_id` named like
    `date_qid` (None when the form does not ask it, so the handlers fall
    back to `created`), and that name, for the global filter. A widget
    on the visit form and one on the check form are then both dated by
    "Date of visit", whichever copy the dashboard stores.
    """
    name = date_question_name(date_qid)
    if name is None:
        return None, None
    resolved = (
        Questions.objects.filter(
            form_id=form_id, name=name, type=QuestionTypes.date,
        )
        .values_list("pk", flat=True).first()
    )
    return resolved, name


def resolve_request_date_question(params, form_id):
    """`params` with `date_question_id` resolved on `form_id` (D-18).

    `date_question_name` keeps the requested question's name, so the
    global filter stays on the dashboard's date when `form_id` does not
    ask it. Called by the views after check_ids, which saw the id the
    client sent.
    """
    resolved, name = resolve_date_question(
        params.get("date_question_id"), form_id,
    )
    return {
        **params,
        "date_question_id": resolved,
        "date_question_name": name,
    }


def apply_global_filters(qs, column, root_form_id, params):
    """qs narrowed by the dashboard's global filters (D-3, D-21).

    `column` holds the row's registration id: "id" for registration rows,
    "parent_id" for monitoring submissions. `params["global_criteria"]`
    is what parse_request_global_criteria returns. `option_in` keeps the
    rows whose registration matches, `option_not_in` drops them; with
    match "all" every filter applies, with "any" a row passing one is
    kept. A no-op without criteria.
    """
    filters = params.get("global_criteria") or {}
    criteria = filters.get("criteria") or []
    if not criteria:
        return qs
    date_filters = build_date_filters(params)
    # Resolved once: every criterion matches the date question by name.
    # The views pass the dashboard's name (D-18); it survives a widget
    # form that does not ask the question.
    if "date_question_name" in params:
        date_name = params["date_question_name"]
    else:
        date_name = date_question_name(date_filters.get("date_question_id"))
    match_any = filters.get("match") == "any"
    passes = []
    for criterion in criteria:
        parts = matching_registrations_subqueries(
            criterion, root_form_id, date_filters, date_name,
        )
        if criterion["type"] == "option_not_in" and not match_any:
            # One exclude per part: the plan BE-6 measured.
            for part in parts:
                qs = qs.exclude(**{f"{column}__in": part})
            continue
        matches = Q()
        for part in parts:
            matches |= Q(**{f"{column}__in": part})
        passes.append(
            matches if criterion["type"] == "option_in" else ~matches
        )
    if not passes:
        return qs
    if match_any:
        keep = Q()
        for condition in passes:
            keep |= condition
        return qs.filter(keep)
    for condition in passes:
        qs = qs.filter(condition)
    return qs


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
        # Rows are registrations annotated with latest_id (D-3).
        qs = apply_global_filters(qs, "id", parent_form.id, params)
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
    # Monitoring submissions point at their registration; registration
    # rows are their own (D-3).
    qs = apply_global_filters(
        qs, "parent_id" if is_monitoring else "id", parent_form.id, params,
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
