# Dashboard workflow completion: design

**Status:** shipped — Asana "[VIZ-010] Complete the Dashboard Workflow",
PR [#335], merged with the epic in [#337] (`1b1001d5`, `422dcfba`).
Two items in the original scope did *not* land; see "Not delivered".

## Problem

VIZ-002..VIZ-009 built every piece of the dashboard builder, but the
authoring loop was broken in the middle. The builder canvas was written a
week before the data-fetching layer existed and was never re-pointed at
it, so it drew *placeholder* numbers: changing a widget's question
produced no API call and no visible change, while the chart on screen
showed invented values that looked like a genuine result.

Preview and the published view already fetched real data. The canvas did
not. So the three surfaces an author moves between disagreed.

## Decisions

- **One data path for all three surfaces.** `useWidgetData` is the single
  hook; `BuilderCanvas` and `DashboardGrid` both call it
  ([`BuilderCanvas.jsx:40`](../../frontend/src/pages/dashboards/BuilderCanvas.jsx#L40),
  [`DashboardGrid.jsx:44`](../../frontend/src/components/dashboard/DashboardGrid.jsx#L44)).
  Canvas, preview and published dashboard cannot drift again because
  there is nothing left to drift.
- **An unconfigured widget prompts, it does not draw.** A widget with no
  form renders "Choose a data source in the panel on the right"
  ([`BuilderCanvas.jsx:50`](../../frontend/src/pages/dashboards/BuilderCanvas.jsx#L50))
  rather than a chart of fake numbers. `form_id` is required by
  `ValuesFilterSerializer`, so fetching would be a guaranteed 400 anyway
  — but the real reason is that a plausible-looking chart is worse than
  no chart.
- **`question_id` is deliberately not part of that check.** It is
  optional, and a count-only KPI has none.

## Components

Table widgets took most of the work, because a table is the one widget
whose data comes from `/escalation` — a "registration parent plus its
latest monitoring child" join — rather than `/values`:

- A table bound to the registration form matches nothing
  (`latest_id__isnull=False` excludes every row), so `monitoringForms()`
  restricts the picker to monitoring forms.
- Columns come from *both* sides of the join: a registration question is
  read off the parent (`parent_answer`), a monitoring question off the
  latest submission (`answer`). `tableColumnOptions()` offers both and
  writes the right source.
- Criteria became optional, so a table with no conditions lists every
  datapoint instead of returning nothing.
- `pruneConfigForForm()` drops columns and criteria whose question
  belongs to the previous form when the author switches forms — left
  behind, they made the backend reject the whole table with no
  explanation.
- Rows are paged on the server, with an author-set cap.

`defaultMeasure()` fixed a related self-inflicted wound: `WIDGET_DEFAULTS`
seeded `measure: current_state` unconditionally while a new widget binds
to `/sources.forms[0]`, always the root registration form. Every newly
added chart widget was born unsavable.

## Not delivered

Two items from the task description are still open:

- **Unpublish and Duplicate have no UI.** `dashboardApi.unpublish` and
  `dashboardApi.duplicate` exist and are tested
  ([`dashboardApi.js:47`](../../frontend/src/util/dashboardApi.js#L47)),
  and the endpoints exist and are tested, but nothing in the app calls
  them. A published dashboard still cannot be taken down from the UI.
- **`backend/db.dbml` was never regenerated.** It predates the dashboard
  tables; `dashboard` and `dashboard_widget` are missing from the schema
  documentation.

The endpoint-hardening half of the task was superseded rather than
dropped — see [VIZ-018](VIZ-018-public-dashboard-visibility.md).

## Testing

397 backend and 230 frontend tests at merge. The canvas change is covered
by `BuilderCanvas.test.js` and by `viewerPreviewParity.test.js`, which
asserts the three surfaces render the same widget the same way.
