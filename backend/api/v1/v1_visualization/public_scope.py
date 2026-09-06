# =========================================================
# The anonymous boundary for public dashboards
# =========================================================
# CLEANUP-001 removed the previous public dashboard because an
# anonymous caller could name any form id it liked and walk other
# tenants' aggregates. The rule that replaces it: an anonymous caller
# names one dashboard, and may ask only about the ids that dashboard's
# own published snapshot already names.
#
# What an anonymous request may see, once it has a tenant, lives in
# this module: which dashboard, and which of that dashboard's ids. The
# anonymous TENANT decision does not live here -- that is
# `utils/tenant_host.py:public_tenant`, which this module calls rather
# than reimplements. And this module is not anonymous-only: its
# `has_any_dashboard_access` decides what an AUTHENTICATED caller may
# see in the private dashboard dropdown.

import json
from typing import NamedTuple, Optional, Set

from django.http import Http404

from api.v1.v1_profile.constants import FeatureTypes
from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
)
from api.v1.v1_visualization.functions import resolve_request_tenant
from api.v1.v1_visualization.models import Dashboard
from utils.tenant_host import public_tenant


class Allowlist(NamedTuple):
    """Ids a request may name. `None` means no restriction."""

    forms: Optional[Set[int]]
    questions: Optional[Set[int]]

    def permits_form(self, form_id):
        if self.forms is None:
            return True
        return _as_id(form_id) in self.forms

    def permits_question(self, question_id):
        if self.questions is None:
            return True
        return _as_id(question_id) in self.questions


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
    if dashboard.kind == DashboardKind.embed:
        # An embedded dashboard queries none of our data endpoints, so
        # the correct set of ids it may name is empty and every data
        # endpoint 404s for a caller holding this slug (spec D-6).
        return Allowlist(forms=set(), questions=set())

    config = dashboard.published_config or {}
    widgets = config.get("widgets") or []

    # `- {None}` is load-bearing, not tidiness. `root_form` is nullable
    # since VIZ-019, and `permits_form` resolves an unparseable id to
    # None through `_as_id` -- so a set containing None would make
    # `None in self.forms` true and let a garbage `form_id` through.
    # The guard lives here, in the function that builds the set, so
    # both kinds are safe by construction rather than by the embed
    # branch above never falling through.
    forms = {dashboard.root_form_id} - {None}
    questions = set()

    for widget in widgets:
        form_id = _as_id(widget.get("form"))
        if form_id is not None:
            forms.add(form_id)
        question_id = _as_id(widget.get("question"))
        if question_id is not None:
            questions.add(question_id)

        widget_config = widget.get("config") or {}

        # Scatter Y axis lives in config; X axis uses widget.question
        # (already collected above).
        axis_qid = _as_id(widget_config.get("question_y"))
        if axis_qid is not None:
            questions.add(axis_qid)

        # Both carry author-entered question ids under the same key:
        # criteria narrow a widget's datapoints, and table columns of
        # source `answer`, `parent_answer` or `latest_date` name one
        # (`parent_name` and `administration` do not, and simply have
        # nothing to collect). Neither is validated as numeric —
        # validate_dashboard_payload does not check it — so a malformed
        # entry must narrow the allowlist rather than crash every public
        # view of the dashboard.
        for key in ("criteria", "columns"):
            for entry in widget_config.get(key) or []:
                if not isinstance(entry, dict):
                    continue
                qid = _as_id(entry.get("question"))
                if qid is not None:
                    questions.add(qid)

    # The date filter's question reaches the endpoints as
    # `date_question_id`, and it lives on the dashboard rather than on
    # any widget.
    date_filter = (config.get("default_filters") or {}).get("date") or {}
    date_qid = _as_id(date_filter.get("date_question"))
    if date_qid is not None:
        questions.add(date_qid)

    return Allowlist(forms=forms, questions=questions)


def _as_id(value):
    """An id as an int, or None when it is not one at all.

    Callers hand these methods values straight off a query string,
    where an id can be anything a client typed. An unparseable id
    cannot be on any dashboard, so it must be refused -- `None` is
    never in an allowlist set, which is exactly the answer we want.
    Raising here would turn a hand-crafted request into a 500 on a
    public page.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ints(values):
    """Every value that parses as an id, dropping the rest.

    Malformed input is the serializer's 400 to give. Dropping it here is
    not leniency: an id that cannot be parsed is one that cannot be used
    downstream either, which the serializers guarantee.
    """
    return [i for i in map(_as_id, values) if i is not None]


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
        for clause in bucket.get("all_of") or []:
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


def has_any_dashboard_access(user):
    """Does this account hold any dashboard feature access at all?

    The gate for private published dashboards. `dashboard_view` is the
    one you would grant a pure consumer, but Create, Edit, Publish and
    Delete each imply being able to look at what you are working on, so
    the question is about the feature and not about one access type.
    """
    if user.is_superuser:
        return True
    return user.user_user_role.filter(
        role__role_role_feature_access__type=(
            FeatureTypes.dashboard_builder
        ),
    ).exists()


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
