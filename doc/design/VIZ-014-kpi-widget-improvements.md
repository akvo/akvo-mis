# KPI widget improvements: design

**Status:** partly delivered. Asana marks "[VIZ-014] KPI Widget
Improvements" Done (2026-09-01), but there is no GitHub issue, no PR and
no commit. What works today came with VIZ-006 (`031c8050`); two of the
five acceptance criteria are unimplemented.

## Problem

A KPI card was the widget most likely to be the *first* thing an author
adds, and the two things they most often want from it were awkward or
impossible.

"How many sites are registered?" needs no question at all — it is a count
of datapoints — but the inspector asked for one. And "how many sites are
Functional **or** Partially functional?" needs several option values,
while "Count records where" accepts one.

## What works today

- **Count-only KPIs are supported by the data path.** `useWidgetData`
  omits `question_id` deliberately: it is optional, and a count-only KPI
  has none ([`useWidgetData.js:185`](../../frontend/src/util/hooks/useWidgetData.js#L185)).
  `DashboardWidget.question` is nullable for the same reason
  ([`models.py`](../../backend/api/v1/v1_visualization/models.py)).
  The value respects dashboard date and administration filters, because
  those merge into the same request as every other widget's.
- **"Count records where"** appears for a KPI bound to an option or
  multiple-option question, writes `config.option_value`, and clearing it
  means "all values"
  ([`BuilderInspector.jsx:640`](../../frontend/src/pages/dashboards/BuilderInspector.jsx#L640)).

## What is missing

- **Multi-select.** The control is a single-value `Select`. The backend
  grammar it would need already exists — `option_in` is in
  `VALID_VALUES_CRITERIA_TYPES` and is implemented in
  `values_functions.py` with OR semantics within a question — so this is
  a frontend change plus a `config.option_value` → list migration path,
  not new query work.
- **A KPI without a question cannot be built in the UI.** `NEEDS_QUESTION`
  in `builderConstants.js` includes `kpi`, so the picker is shown and
  nothing communicates that leaving it empty is a legitimate choice. The
  scatter widget already models the fix: an empty axis shows the hint
  "Default: each datapoint counts as 1".

## Recommended shape

Follow scatter. Make the KPI question select `allowClear` with a
placeholder naming the count-only behaviour, and change `option_value` to
accept an array, serialising to `option_in:{qid}:{v1}|{v2}` when it holds
more than one. Keep reading a bare string for dashboards saved before the
change.

## Out of scope

Comparison KPIs (period-over-period deltas, sparklines). Not requested.
