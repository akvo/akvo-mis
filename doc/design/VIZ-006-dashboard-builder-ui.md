# Dashboard builder UI: design

## Problem

The list screen can create an empty dashboard and the API can store one, but
there is nothing to author with. This slice builds the canvas: a palette of
widget types, a 24-column grid the author arranges them on, and an inspector
that turns a widget into a valid VIZ-001 §4.3 `config` object.

It is the largest slice in the milestone and the one where a wrong default
does the most damage. A builder that makes it easy to produce a chart
counting *monitoring visits* when the author meant *sites* will produce
confidently wrong dashboards at scale, and nobody will review them.

Mockup: `doc/design/VIZ-Example/index.html` — builder screen `117–362`,
palette `144–179`, canvas `180–233`, inspector `234–336`, dashboard settings
`337–360`, widget defaults `519–532`, reorder `655–673`.

## Decisions

- **`measure` is on the path, not in an advanced panel** (D-4). The mockup's
  inspector has no `measure` control at all. Every widget bound to a
  monitoring form passes through one required, plain-language choice —
  *"Current status of each site"* (default) or *"Every submission over
  time"* — before its shape controls. There is no route to a KPI that
  silently counts submissions. `include_unmonitored` sits directly beneath
  it as *"Include sites with no data yet"*, because sites never monitored
  drop out of `current_state` by default and Fiji had to bolt on a
  "No information available" bucket after discovering that the hard way.
- **Every chart is an `akvo-charts` component** (D-10;
  `npm install --save akvo-charts`, demo at
  <https://akvo.github.io/akvo-charts>). No `echarts-for-react`, no new chart
  component in this repo. Anything the wrapper cannot express is a
  `rawConfig` prop or an upstream change.
- **The form picker offers the family and nothing else.** It is populated
  from `/sources`, which returns `root_form` and its monitoring children.
  The mockup lets a widget name any form; D-3 does not. The client does not
  re-derive the rule — it just cannot offer what `/sources` did not return.
- **The builder publishes.** The mockup has Save and a static "Draft" badge
  and no publish anywhere (`index.html:117–144`). Save writes the draft;
  Publish snapshots it for viewers (VIZ-007); Unpublish returns it to draft.
  Without this the lifecycle in VIZ-001 §5.3 has no UI.
- Widget renderers are built once, here. The canvas preview and the
  published viewer (VIZ-008) are the same components with different props —
  presentational, taking `(config, data)` and nothing else. If VIZ-008 finds
  itself writing a second renderer, this split was wrong.
- The width control stays as the mockup's four preset buttons (`325–335`)
  writing `col_span` 6 / 8 / 12 / 24. Presets in the UI, `col_span` on the
  wire; a free 1–24 spinner is precision nobody wants at authoring time.

## Components

### 1. Builder shell

Three panes: palette left, canvas centre, inspector right
(`index.html:117–144`). The header carries the dashboard name as an inline
editable field, the draft/published badge, and Save / Preview / Publish.
`root_form` is shown as read-only text — it is fixed at creation (D-3).

### 2. Palette

The seven widget types with their one-line descriptions, exactly as the
mockup words them (`144–179`): KPI card *(single metric)*, Bar chart
*(compare categories)*, Line chart *(trend over time)*, Pie / doughnut
*(share of total)*, Table *(rows of records)*, Map *(geographic points)*,
Section title *(group your widgets)*.

### 3. Canvas

A 24-column grid. Click to select, drag to reorder (`655–673`), move
up/down, delete, and an empty state (`180–233`). Each widget renders a live
preview using the real renderer, so the canvas shows what the viewer will
show.

### 4. Inspector

Walks the VIZ-001 §5.2 decision tree, showing only the controls the selected
widget type uses:

| Control | Applies to | Writes |
|---|---|---|
| Widget title | all but section_title | `title` |
| Heading text | section_title | `config.text` |
| Data source (form) | kpi, bar, line, pie, table, map | `form` |
| Question | kpi, bar, line, pie, map | `question` |
| **Measure** | any widget on a monitoring form | `config.measure` |
| **Include sites with no data yet** | same | `config.include_unmonitored` |
| Group by | bar, line, pie | `config.group_by` |
| Stack by | bar, line | `config.stack_by` |
| Value type | kpi, bar, line, pie | `config.value_type` |
| Repeat aggregation | kpi, bar, line | `config.repeat_agg` |
| Count records where | kpi | `config.option_value` |
| Orientation | bar | `config.orientation` |
| Variant | pie | `config.variant` |
| **Criteria** | table | `config.criteria[]` |
| Columns | table | `config.columns[]` |
| Status question + colours | map | `config.status_question`, `status_colors` |
| Accent colour | chart widgets | `color` |
| Width | all | `col_span` |

Four of these are absent from the mockup and are required by §4.3: measure,
include-unmonitored, the table **criteria editor** (the mockup has column
checkboxes only, `297–311`), and the map's `status_colors` mapping (the
mockup has a single accent colour). The `Group by` options are
`option | month | date | parent_id` — the mockup's list includes `quarter`
(`483–488`), which `VALID_GROUP_BY` does not support; it is dropped rather
than faked client-side.

### 5. Widget renderers

Presentational components under
`frontend/src/components/dashboard/widgets/`, each taking `(config, data)`:

| Widget | Component |
|---|---|
| `kpi` | local `KPICard` — a styled number, no chart |
| `bar` | `Bar` from `akvo-charts`, `StackBar` when `stack_by` is set |
| `line` | `Line`, `StackLine` when `stack_by` is set |
| `pie` | `Pie`, `Doughnut` when `variant: doughnut` |
| `map` | `MapCluster` |
| `table` | Ant Design `Table` — `akvo-charts` has no table primitive |
| `section_title` | local `SectionTitleWidget` |

`akvo-charts` takes `config` (title, `xAxisLabel`, `yAxisLabel`,
`horizontal`, `legend`, `textStyle`, `itemStyle`, `color`) and `data` in one
of the three ECharts dataset shapes; `StackBar` additionally takes
`stackMapping`. `config.horizontal` is what the inspector's `orientation`
writes. The existing `ChartRenderer` is rewritten to this mapping and loses
its `setOption` escape hatches along with the Fiji compute imports.

### 6. Dashboard settings

Shown when nothing is selected (`337–360`): name, description, and the
default monitoring-period and location filters, writing
`Dashboard.default_filters` per VIZ-001 §4.4. These are dashboard-level and
apply to every widget — coherent only because the dashboard is one family.

## Data flow

    open /dashboards/:slug/edit
      → GET /manage/dashboards/{id}          → widget rows
      → GET /manage/dashboards/{id}/sources  → family forms + questions
      → author on the canvas (all local)
      → Save    → PUT  /manage/dashboards/{id}  {..., widgets: [...]}
      → Preview → the VIZ-008 renderer, same components, unsaved state
      → Publish → POST /manage/dashboards/{id}/publish

## Error handling

- A 400 from `PUT` carries a widget index; the canvas selects and highlights
  that widget and shows the message in the inspector. A global error banner
  for a per-widget problem is useless in a 20-widget dashboard.
- Client-side validation mirrors §4.5 for immediate feedback but is never
  the gate. The server response is authoritative.
- A monitoring-form widget cannot be saved without an explicit `measure`;
  the control has no empty state, it has a default (`current_state`).
- Leaving with unsaved changes prompts.

## Testing

- Every §4.3 config field is reachable in the inspector, and no field outside
  §4.3 is.
- The inspector shows exactly the controls for the selected type — the
  decision tree in §5.2 walked per type.
- The measure control appears if and only if `widget.form` is a monitoring
  form, and defaults to `current_state`.
- The form picker offers only forms returned by `/sources`; a fixture
  containing an out-of-family form is not offered.
- The `PUT` payload produced matches VIZ-001 §6 against the fixture.
- Renderers: each widget type mounts its mapped `akvo-charts` component with
  the expected `config`/`data`; `stack_by` switches bar to `StackBar` and
  line to `StackLine`; `variant: doughnut` switches pie to `Doughnut`.
- No module under `components/dashboard/` imports `echarts` or
  `echarts-for-react` — assert it in the test suite, not just at review.
- Reorder, add, delete and width changes are local until Save.
- ESLint clean per `frontend/.eslintrc.json` (`curly`, `no-undefined`,
  `prefer-arrow-callback`, prettier), verified in the container.

## Out of scope

- Publishing mechanics. The button is here; the snapshot is VIZ-007.
- The read-only viewer route (VIZ-008). Preview reuses its renderer, which
  is built here.
- AI-suggested widget arrays. A separate epic (`VIZ-AI-001`); if built, they
  land on this canvas as unsaved state and are edited with these controls, so
  nothing here needs to anticipate them.
- Cross-form widgets, in any form. Not deferred — not allowed (D-3).
