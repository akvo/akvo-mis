# Dashboard viewer and preview: design

## Problem

A published dashboard is a row in a table. Nothing renders it, and nothing
turns a widget's stored `config` into the `/visualization/*` request that
fills it with data.

That translation is the whole slice, and one line of it carries most of the
risk: `config.measure`. `current_state` expands to `monitoring=latest` plus
`sum_by=parent_id`, which counts *sites by their most recent monitoring
submission*. `all_submissions` expands to `monitoring=all`, which counts
*submissions*. The difference is "42 water points are currently operational"
versus "42 monitoring visits reported operational". If that expansion is
written in two places, one of them will eventually be wrong, and the number
it produces will look perfectly reasonable.

Mockup: `doc/design/VIZ-Example/index.html` — view screen `363–412`.

## Decisions

- **The `measure` expansion lives in exactly one module** and is the only
  place `monitoring=` is written anywhere in the frontend. Everything else
  calls it.
- **The viewer and the builder's preview are the same renderer.** One
  component tree, two entry points, differing only in whether it reads
  `published_config` (viewer) or the builder's unsaved local state
  (preview). A preview that renders through a different path is not a
  preview.
- **Charts come from `akvo-charts` only** (D-10;
  `npm install --save akvo-charts`, demo at
  <https://akvo.github.io/akvo-charts>). The widget renderers are the ones
  built in VIZ-006 and are not reimplemented here.
- **A broken widget renders a placeholder in its own grid cell** (D-9). It
  does not disappear, and it does not take the page with it. Under
  tenant-authored dashboards a stale question reference is routine, not
  exceptional.
- Filters are dashboard-level, applied to every widget. That is coherent
  only because a dashboard is one form family (D-3) — every widget shares a
  registration form, so "this administration, this period" means the same
  thing everywhere on the page.

## Components

### 1. Viewer route

`/dashboards/:slug` reads `GET /api/v1/dashboards/{slug}` and renders
`published_config` on the same 24-column grid the builder authored on
(`index.html:363–412`). An Edit button, gated on `dashboard_edit`, goes to
the builder.

### 2. Preview mode

The builder's Preview switches the canvas for the same renderer, fed from
unsaved local state. Selection, drag handles and the inspector are hidden;
nothing else differs.

### 3. The filter bar

Monitoring period and administration, shown per `Dashboard.default_filters`
(VIZ-001 §4.4) and rendered as the mockup's chips (`363–390`). Active values
merge into every widget request as `from_date`, `to_date`,
`date_question_id` and `administration_id`.

`date_question_id` bounds the window on an answer date when
`default_filters.date.date_question` is set; otherwise the filter applies to
`FormData.created`. It never reorders anything — "latest" stays latest by
submission date (D-8).

### 4. `measure` expansion

`frontend/src/util/dashboardMeasure.js`, one exported function:

| `config.measure` | Query parameters |
|---|---|
| `current_state` *(default on monitoring forms)* | `monitoring=latest`, `sum_by=parent_id` |
| `all_submissions` | `monitoring=all` |

`config.include_unmonitored` maps to `include_unanswered`. A widget whose
`form` is the registration form carries no `measure` and gets neither
parameter.

The builder cannot express `monitoring=latest` without `sum_by=parent_id`;
that combination has no sensible dashboard meaning, and the loss is
intentional (D-4).

### 5. Widget data fetching

Per widget, by type:

| Widget | Request |
|---|---|
| `kpi`, `bar`, `line`, `pie` | `GET /visualization/values` |
| `table` | `GET /visualization/escalation` |
| `map` | `GET /maps/geolocation/{form_id}` |
| `section_title` | none |

Built on the existing hooks — `useDashboardValues`,
`useDashboardEscalation`, `useVisualizationRequest` — re-pointed at the new
config shape. The Fiji compute hooks (`useDashboardConfig`,
`useDashboardProgress`) are not carried over; the first read a file-based
registry that no longer exists, and the second backs `/progress`, which has
no widget type (D-6).

Each widget fetches independently, so one slow or failing request does not
hold the page.

### 6. Widget states

Four, per widget, never page-level:

- **Loading** — a skeleton in the widget's own cell.
- **Data** — the VIZ-006 renderer.
- **No data** — the existing empty placeholder, when the request succeeds
  with nothing in it. Common and expected under `current_state`, where sites
  never monitored are excluded unless `include_unmonitored` is set.
- **Broken** — when the serializer returned `is_broken`: *"This widget's
  question no longer exists."* The widget keeps its grid position and its
  title, so the layout does not reflow around it.

## Data flow

    GET /dashboards/:slug
      → published_config { widgets[], default_filters }
      → render grid
      → per widget:
          is_broken?        → placeholder, no request
          section_title?    → text, no request
          else              → expand measure + merge active filters
                            → GET /visualization/{values|escalation}
                              or /maps/geolocation/{form_id}
                            → akvo-charts component

## Error handling

- A widget request that fails renders an error state in that widget only.
  The rest of the page loads.
- A 404 on the slug means unpublished, deleted, or another tenant's — one
  "dashboard not found" screen for all three.
- A widget referencing a question that was deleted after publish is caught
  by the server annotation, not by the client guessing from an empty
  response.
- Filter values that produce an empty result are "No data", not an error.

## Testing

- The `measure` expansion has a unit test for both values, plus the
  registration-form case that emits neither parameter. Assert it is the only
  module in the frontend writing `monitoring=`.
- A dashboard with one broken widget renders every other widget and shows
  the placeholder in the broken one's position.
- Filter changes re-request every data widget with the merged parameters and
  leave `section_title` alone.
- Viewer and preview render byte-identical output from the same widget array.
- Table and map render from `/visualization/escalation` and
  `/maps/geolocation/{form_id}` with their existing response shapes.
- No `echarts` / `echarts-for-react` import anywhere in the viewer path.
- A widget request failure is contained to that widget.

## Out of scope

- `/visualization/progress` and any staged-progress widget (D-6). Retained
  and hardened in VIZ-003; no widget type exposes it.
- Deleting the legacy renderer and the Fiji compute layer — VIZ-009, after
  this ships.
- Export, print and embed (VIZ-001 §13).
- Per-widget filter overrides. Filters are dashboard-level, which is what
  makes them coherent (D-3).
