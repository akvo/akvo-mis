"""`config.measure` → aggregation parameters.

The one place the string `monitoring` is written on the server, ported from
`frontend/src/util/dashboardMeasure.js` for VIZ-010. The public path cannot
use the JS version — an anonymous caller authors no query, so the expansion
has to happen where the widget is read — and VIZ-008 was explicit that two
copies of this rule is the hazard, not the duplication itself:

    "If that expansion is written in two places, one of them will
    eventually be wrong, and the number it produces will look perfectly
    reasonable."

So the JS copy goes away and every surface asks the server.

A widget asks one of two questions, and they are easy to confuse because
both produce a plausible number:

    current_state    "How many water points are currently operational?"
                     The universe is registration datapoints, each reduced
                     to its most recent monitoring submission. Counting
                     distinct parents therefore counts *sites*.

    all_submissions  "How many monitoring visits reported operational?"
                     Every submission, no reduction, each counted once.

Ask the first with the second's parameters and you get "42" where the truth
is "17", on a widget titled "Operational sites", with nothing on screen to
suggest anything is wrong.

See VIZ-001 §4.2 and D-4, VIZ-008 "measure expansion", VIZ-010 D-4.
"""

# The only `monitoring` value the formula endpoint accepts. A map pin shows
# one current status, so "latest" is right there regardless of the widget's
# own measure.
MONITORING_LATEST = "latest"

CURRENT_STATE = "current_state"
ALL_SUBMISSIONS = "all_submissions"


def expand_measure(widget, root_form_id):
    """Parameters to merge into this widget's aggregation.

    Args:
        widget: A widget dict from `published_config` or a payload.
        root_form_id: The dashboard's registration form id.

    Returns:
        dict: `monitoring`, `sum_by` and `include_unanswered` as they
        apply. Keys are absent rather than false, so a default never
        forks a cache key or lengthens a query string.
    """
    config = (widget or {}).get("config") or {}
    params = {}

    # Guarded on the form rather than on `config.measure`: a stale measure
    # left behind by an earlier edit — the widget was on a monitoring form,
    # then moved — must not reach the request. A registration widget has no
    # monitoring submissions to reduce over, and §4.5 rejects a measure on
    # one at save time.
    widget_form = (widget or {}).get("form")
    is_monitoring_widget = bool(
        widget_form and root_form_id and widget_form != root_form_id
    )

    if is_monitoring_widget:
        measure = config.get("measure")
        if measure == ALL_SUBMISSIONS:
            params["monitoring"] = "all"
        elif measure == CURRENT_STATE:
            params["monitoring"] = MONITORING_LATEST
            # Inseparable from monitoring=latest: without it the aggregate
            # counts submissions inside the latest-per-site universe, a
            # number that means nothing to anyone (VIZ-001 D-4).
            params["sum_by"] = "parent_id"

    if config.get("include_unmonitored"):
        params["include_unanswered"] = True

    return params
