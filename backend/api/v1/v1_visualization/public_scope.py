# =========================================================
# The anonymous boundary for public dashboards
# =========================================================
# CLEANUP-001 removed the previous public dashboard because an
# anonymous caller could name any form id it liked and walk other
# tenants' aggregates. The rule that replaces it: an anonymous caller
# names one dashboard, and may ask only about the ids that dashboard's
# own published snapshot already names.
#
# Everything that decides what an anonymous request may see lives in
# this module. Nothing else in the codebase should be reading
# `request.user.is_anonymous` to make a scoping decision.

import json
from typing import NamedTuple, Optional, Set

from django.http import Http404

from api.v1.v1_visualization.constants import DashboardStatus
from api.v1.v1_visualization.functions import resolve_request_tenant
from api.v1.v1_visualization.models import Dashboard
from utils.tenant_host import public_tenant


class Allowlist(NamedTuple):
    """Ids a request may name. `None` means no restriction."""

    forms: Optional[Set[int]]
    questions: Optional[Set[int]]

    def permits_form(self, form_id):
        return self.forms is None or int(form_id) in self.forms

    def permits_question(self, question_id):
        return self.questions is None or int(question_id) in self.questions


# What an authenticated caller gets. Their scoping is the tenant, exactly
# as it was before this feature existed.
ALLOW_ANY = Allowlist(forms=None, questions=None)


def allowlist_from(dashboard):
    """The ids a public dashboard's own snapshot names.

    Read from `published_config`, never from the live widget rows: the
    snapshot is what viewers are served, so it is also what bounds what
    they may ask about. An author who deletes a widget and has not
    republished has not yet narrowed what the public dashboard shows,
    and must not have narrowed what it may query either.
    """
    config = dashboard.published_config or {}
    widgets = config.get("widgets") or []

    forms = {dashboard.root_form_id}
    questions = set()

    for widget in widgets:
        if widget.get("form"):
            forms.add(int(widget["form"]))
        if widget.get("question"):
            questions.add(int(widget["question"]))

        widget_config = widget.get("config") or {}

        # Criteria narrow a widget's datapoints and carry their own
        # question ids, in both the chart and the table grammars.
        for criterion in widget_config.get("criteria") or []:
            if isinstance(criterion, dict) and criterion.get("question"):
                questions.add(int(criterion["question"]))

        # Table columns of source `answer`, `parent_answer` and
        # `latest_date` name a question; `parent_name` and
        # `administration` do not.
        for column in widget_config.get("columns") or []:
            if isinstance(column, dict) and column.get("question"):
                questions.add(int(column["question"]))

    # The date filter's question reaches the endpoints as
    # `date_question_id`, and it lives on the dashboard rather than on
    # any widget.
    date_filter = (config.get("default_filters") or {}).get("date") or {}
    if date_filter.get("date_question"):
        questions.add(int(date_filter["date_question"]))

    return Allowlist(forms=forms, questions=questions)


def _ints(values):
    """Every value that is an integer id, quietly dropping the rest.

    Malformed input is the serializer's 400 to give. Yielding nothing
    from it here is not leniency: an id that cannot be parsed is an id
    that was not extracted, and an unextracted id is one the caller
    never gets checked for — so anything unparseable must also be
    unusable downstream, which the serializers guarantee.
    """
    for value in values:
        try:
            yield int(value)
        except (TypeError, ValueError):
            continue


def question_ids_in_criteria(value):
    """`option_equals:{qid}:{value},overdue:{qid}:{qid}` -> ids.

    Only `overdue` names two questions, a completion and a deadline
    (see `functions.py:parse_criteria_string`); every other criterion
    type carries a value in segment two, not a second id, and that
    value can itself look like an integer (`threshold_gt:600107:3`).
    So this reads segment two as an id for every type, and reads
    segment three as one only for `overdue` — never scans every
    integer-looking segment, or a numeric threshold would be
    mistaken for a question id.

    Strips each clause before splitting, matching every downstream
    reader of this exact grammar (`functions.py:parse_criteria_string`,
    `dashboard_serializers.py:validate_criteria`). Without the strip, a
    leading space after a comma — trivial to inject in a query string
    as `%20` or `+` — desyncs the two: `" overdue"` fails the `==
    "overdue"` check here while the stripped downstream parser still
    reads it as `overdue` and uses its second id unchecked. That is an
    anonymous caller reading a question this dashboard never allowed.
    """
    ids = []
    for clause in (value or "").split(","):
        parts = clause.strip().split(":")
        if len(parts) < 2:
            continue
        span = parts[1:3] if parts[0] == "overdue" else parts[1:2]
        ids.extend(_ints(span))
    return ids


def question_ids_in_columns(value):
    """`{key}:{source}` or `{key}:{source}:{qid}` -> ids.

    A source of `answer`, `parent_answer` or `latest_date` carries a
    third segment that parses as a question id; `parent_name` and
    `administration` do not have one. There is no branch on the
    source name here — a clause is treated as carrying a question
    purely because it has a third segment that parses as an int, the
    same way `question_ids_in_criteria` works. Stripped before
    splitting for the same reason as that function: to stay
    byte-for-byte aligned with the downstream grammar this mirrors.
    """
    ids = []
    for clause in (value or "").split(","):
        parts = clause.strip().split(":")
        if len(parts) < 3:
            continue
        ids.extend(_ints(parts[2:]))
    return ids


def question_ids_in_formula(value):
    """Every `question_id` inside a formula's buckets."""
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    ids = []
    for bucket in parsed.get("buckets") or []:
        if not isinstance(bucket, dict):
            continue
        for key in ("all_of", "any_of", "none_of"):
            for clause in bucket.get(key) or []:
                if isinstance(clause, dict):
                    ids.extend(_ints([clause.get("question_id")]))
    return ids


def check_ids(allowed, form_ids=(), question_ids=()):
    """Refuse the first id the dashboard's snapshot does not name.

    404 rather than an empty result, deliberately. An out-of-allowlist
    id answered with `[]` would let a regression in this module read as
    "that widget has no data" — the one failure mode nobody
    investigates.
    """
    for form_id in form_ids:
        if form_id is None:
            continue
        if not allowed.permits_form(form_id):
            raise Http404("form is not on this dashboard")
    for question_id in question_ids:
        if question_id is None:
            continue
        if not allowed.permits_question(question_id):
            raise Http404("question is not on this dashboard")


def resolve_view_scope(request):
    """`(tenant, allowlist)` for a visualization request.

    Authenticated callers keep exactly the path they had before this
    feature: the tenant from `resolve_request_tenant`, and no id
    restriction whatsoever.

    Anonymous callers must name a dashboard. It has to be published,
    public, and in the workspace this host serves — so the tenant a
    public request is scoped to is the dashboard's own, never anything
    the caller supplied.
    """
    if request.user and request.user.is_authenticated:
        return resolve_request_tenant(request), ALLOW_ANY

    slug = request.query_params.get("dashboard_slug")
    tenant = public_tenant(request)
    if not slug or tenant is None:
        raise Http404("no public dashboard named")

    dashboard = Dashboard.objects.filter(
        slug=slug,
        tenant=tenant,
        status=DashboardStatus.published,
        is_public=True,
    ).first()
    if dashboard is None:
        raise Http404("no such public dashboard")

    return dashboard.tenant, allowlist_from(dashboard)
