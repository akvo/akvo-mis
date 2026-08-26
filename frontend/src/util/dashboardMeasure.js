// =========================================================
// `config.measure` → /visualization query parameters
// =========================================================
//
// This module exists so that the string `monitoring` appears as a request
// parameter in exactly one file in the frontend. That is enforced by a test
// in `__test__/dashboardMeasure.test.js`, and it is worth the ceremony.
//
// A dashboard widget asks one of two questions, and they are easy to
// confuse because both produce a plausible number:
//
//   current_state    "How many water points are currently operational?"
//                    The universe is registration datapoints, each reduced
//                    to its most recent monitoring submission. Counting
//                    distinct parents (`sum_by=parent_id`) therefore counts
//                    *sites*.
//
//   all_submissions  "How many monitoring visits reported operational?"
//                    The universe is every submission. No reduction, no
//                    `sum_by` — each submission counts once.
//
// Ask the first question with the second question's parameters and you get
// "42" where the truth is "17", on a widget titled "Operational sites",
// with nothing on screen to suggest anything is wrong. That failure is
// silent, plausible, and would be discovered by a field officer rather than
// by us — which is why the expansion is centralised rather than inlined at
// the two or three call sites that need it.
//
// See VIZ-001 §4.2 and D-4, and VIZ-008 "measure expansion".

// The only `monitoring` value the formula endpoint accepts, exported so
// the map's status request (useWidgetData) can name it without writing
// the parameter a second time. A pin shows one current status, so "latest"
// is the right answer there regardless of the widget's own measure.
export const MONITORING_LATEST = "latest";

/**
 * Expand a widget's `measure` into query parameters.
 *
 * @param {object} widget      A widget from `published_config` or builder state.
 * @param {number} rootFormId  The dashboard's registration form id.
 * @returns {object}           Parameters to merge into the widget's request.
 */
export const expandMeasure = (widget, rootFormId) => {
  const config = widget?.config || {};
  const params = {};

  // A widget on the registration form has no monitoring submissions to
  // reduce over, so it carries no `measure` (VIZ-001 §4.5 rejects one at
  // save time) and gets neither parameter. Guarding on the form rather
  // than on `config.measure` means a stale measure left behind by an
  // earlier edit cannot leak into the request.
  const isMonitoringWidget = Boolean(
    widget?.form && rootFormId && widget.form !== rootFormId
  );

  if (isMonitoringWidget) {
    if (config.measure === "all_submissions") {
      params.monitoring = "all";
    } else if (config.measure === "current_state") {
      params.monitoring = MONITORING_LATEST;
      // Inseparable from `monitoring=latest`: without it the aggregate
      // counts submissions inside the latest-per-site universe, which is
      // a number that means nothing to anyone (VIZ-001 D-4).
      params.sum_by = "parent_id";
    }
  }

  // Independent of the measure, and emitted as an absent key rather than
  // `false` so the query string stays minimal and the request cache key
  // does not fork on a default.
  if (config.include_unmonitored) {
    params.include_unanswered = true;
  }

  return params;
};

export default expandMeasure;
