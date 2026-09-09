# Quantity maps for the dashboard map widget

**Status:** implemented — [#382](https://github.com/akvo/akvo-mis/issues/382)
**Date:** 2026-09-09
**Upstream:** `akvo-charts@1.3.5` (published 2026-09-09), issue [akvo/akvo-charts#54](https://github.com/akvo/akvo-charts/issues/54), PR [#55](https://github.com/akvo/akvo-charts/pull/55)

## Why

The dashboard map widget can only say **where** things are and **which category** they
belong to. It cannot say **how much**. A form with a `number` question — population served,
households reached, litres per day, beneficiaries — has nowhere to put that number on a
map. Today every point is the same size, coloured by `status`.

`akvo-charts@1.3.5` adds a **quantity map** to `MapCluster`: point data carrying a numeric
value aggregates by **sum** across zoom levels, with circle size scaled to the aggregated
value. Zoomed out, nearby places merge into one circle labelled with their total; zoomed
in, clusters split and the numbers break down to individual places, which stay circles
sized by their own value.

This is the encoding a `number` question wants. It is not the same as a choropleth — that
fills polygon *areas*, which is wrong when the thing being measured is a **place** (a
school, a water point, a village) rather than a region.

## What the upstream library gives you

```jsx
import { MapCluster } from "akvo-charts";

<MapCluster
  type="quantity"
  valueKey="population"
  data={[
    { point: [-6.2087, 106.8456], label: "Jakarta", population: 10562088 },
    { point: [-7.2574, 112.7520], label: "Surabaya", population: 2874314 },
  ]}
/>;
```

| Prop | Type | Default | Meaning |
| --- | --- | --- | --- |
| `type` | `string` | `'default'` | `'quantity'` selects this mode |
| `valueKey` | `string` | `'value'` | Which field on each row holds the number |
| `radius` | `[number, number]` | `[16, 56]` | Min/max circle radius in px |
| `color` | `string \| (sum) => string` | `'#4c78a8'` | Fill colour, or a function of the aggregated value |
| `formatValue` | `(n) => string` | compact (`12.4M`) | Renders the number inside the circle |

Behaviours worth knowing before you design around it:

- **Sizing is a square-root scale, not strict area-proportionality.** The domain runs from
  the smallest single value to the **sum of all values**, and it is fixed for the lifetime
  of the data so circle sizes stay comparable as you zoom. Because the domain top is the
  total rather than the largest single value, individual places sit in the lower part of
  the range and only a fully collapsed cluster approaches the maximum. Do not promise users
  "twice the value is twice the width" — it is not.
- **Rows with a `point` but a missing or non-numeric value render as zero, not dropped.**
  Bad data shows up as a small circle instead of vanishing. Useful for the MIS case where a
  submission may simply not have answered the number question.
- **Clicking a circle opens a popup with the label and the exact value**
  (`Number(v).toLocaleString()`), not the compact form shown inside the circle. A
  `renderPopup` prop still overrides this completely — which matters, because `VizMap`
  already passes one.
- **Passing an explicit `markerIcon` suppresses the quantity circle entirely.** `VizMap`
  does not currently pass one, so this is fine today — just don't add one.

## Current state in this repo (verified)

| Fact | Where |
| --- | --- |
| `akvo-charts` is already a dependency at `^1.3.4`, so `1.3.5` arrives on a plain install | `frontend/package.json:10` |
| The map widget already renders `MapCluster` with `type="circle"` and `groupKey="status"` | `frontend/src/components/dashboard/widgets/VizMap.jsx` |
| Points are built as `{ id, point, label, status, color }` from `row.geo` / `row.name` / `row.status`, filtered by `geo.hasValidPoint` | `VizMap.jsx` |
| `VizMap` passes `renderPopup={(point) => point?.label}` — this **overrides** the new value popup | `VizMap.jsx` |
| Widget renderers are registered by string key | `frontend/src/components/dashboard/widgets/WidgetRenderer.jsx` |
| The map widget's default config is `{ color_scheme, chart_colors }` — no measure/value fields | `frontend/src/pages/dashboards/builderConstants.js:105` |
| `map` is in `NEEDS_FORM`, `NEEDS_QUESTION`, `NEEDS_COLOR`, `NEEDS_MEASURE` — but **not** in `NEEDS_VALUE_TYPE` or `NEEDS_GROUP_BY` | `builderConstants.js:690-730` |
| `SUPPORTED_GROUP_QUESTION_TYPES` **already includes `number`** | `builderConstants.js:168` |
| `STACK_QUESTION_TYPES` is only `option` / `multiple_option` | `builderConstants.js:165` |
| `number` is a first-class question type | `frontend/src/lib/constants.js:14` |
| Backend widget type `map = 6` | `backend/api/v1/v1_visualization/constants.py:117-136` |

So the gap is narrower than "the dashboard doesn't support number questions". Number is
already an accepted grouping type; what is missing is a **map widget that binds to a number
question and renders it as magnitude**.

## What to change

### 1. `VizMap.jsx` — render the quantity mode

The component currently hard-codes `type="circle"`. It needs to branch on the widget config.
Sketch, adapting the existing `points` builder:

```jsx
const isQuantity = widgetConfig.map_mode === "quantity";
const valueKey = "value"; // the normalised field name we write below

const points = useMemo(() => {
  const rows = Array.isArray(data) ? data : [];
  return rows.filter(geo.hasValidPoint).map((row) => ({
    id: row.id,
    point: row.geo,
    label: row.name,
    status: row.status,
    // Only meaningful in quantity mode; harmless otherwise.
    value: Number(row.value) || 0,
    color: row.status ? colorForStatus[row.status] || fallback : fallback,
  }));
}, [data, colorForStatus, fallback]);
```

and then:

```jsx
<MapCluster
  key={`${colorKey}-${isQuantity ? "quantity" : "circle"}`}
  data={points}
  type={isQuantity ? "quantity" : "circle"}
  {...(isQuantity
    ? { valueKey, color: fallback }
    : { groupKey: "status" })}
  config={{ center, zoom: 5, height: "100%", width: "100%" }}
  tile={geo.tile}
  renderPopup={
    isQuantity
      ? undefined // let the library show label + exact value
      : (point) => point?.label
  }
/>
```

Three things to get right here:

- **Drop `renderPopup` in quantity mode**, or you lose the value popup — the library's
  default only applies when `renderPopup` is absent. If you want a custom popup, render the
  value yourself.
- **Keep the `key`.** The component already remounts on colour change; include the mode too.
  `MapCluster` internally remounts its cluster group when `type` changes (fixed in 1.3.5),
  but `VizMap`'s own memoised `points` still need to be rebuilt.
- **The status legend is meaningless in quantity mode** — size carries the information, not
  colour. Either hide it (`showLegend && !isQuantity`) or replace it with a size legend.
  A colour legend next to uniformly-coloured circles will confuse people.

### 2. `builderConstants.js` — let the builder configure it

- Add a mode to the map widget's default config:
  ```js
  map: {
    col_span: 24,
    color: null,
    config: {
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
      map_mode: "category", // "category" | "quantity"
    },
  },
  ```
- **No second question control, and no user-facing mode switch.** The map's
  question dropdown has always listed number questions — picking one just did
  nothing — so the fix is to make that existing choice mean something. The mode
  follows the question's *type*: the inspector writes `map_mode` when the author
  picks, and the two can never disagree because there is nothing to disagree
  with. `widget.question` stays the one binding, which is also what keeps
  validation and public-dashboard scope unchanged (see §3).
- The inspector derives its own controls from `selectedQuestion.type` rather than
  from the stored flag; the flag exists for the *viewer*, which has no question
  types to derive it from.

### 3. Backend — supply the number per point

**Answered, 2026-09-09 (#382).** The original questions and what the code
actually says:

**Which view produces the rows, and do they carry arbitrary answers?**
`GeolocationListView.get` (`views.py:263`), ending at `views.py:424` with
`queryset.values("id", "name", "geo", "administration_id")` through
`GeoLocationListSerializer` (`serializers.py:87-90`). Fixed shape, no answers.

But that is not the whole picture: `status` is not from that endpoint either.
It is joined in the browser from a **second** request — `buildStatusRequest`
(`useWidgetData.js`) asks `/visualization/values/formula` with
`group_by=parent_id` and `normalize` merges it by `point.id`. So a per-point
attribute join was already the established pattern, and the number follows it.

**Can it be added without a new endpoint?** Yes, with one gap to fill.
`/visualization/values` with a number question and `group_by=parent_id` already
returns `{value, label, group}` where `group` is the registration datapoint id
— exactly the join key. Verified against a dev database, monitoring form 6002:

```
monitoring=latest -> [{'value': 49.0, 'label': 'DUMMY-Boyd Group…', 'group': '87'}, …]
```

The gap is the **registration** form — the one that actually carries `geo`, and
the natural home for "population served". `_number_group_by_parent` groups on
`data__parent_id`, which is NULL on every registration row, so it collapses the
whole form into one unjoinable `group: "None"`:

```
group_by=parent_id -> [{'value': 33.0, 'label': None, 'group': 'None'}]
group_by=id        -> [{'value': 33.0, 'label': 'Total'}]   # no 'group' at all
```

`group_by=id` was implemented for count mode only (`_count_group_by_id`); a
number question fell through to the ungrouped "Total" aggregate. Filling that in
— `_number_group_by_id`, one row per datapoint keyed by its own id — is the
entire backend change. `"id"` was already in `VALID_GROUP_BY`.

**Does validation need to accept a number question for a map?** No, and this is
the part that shrank the task most. `_validate_widget` checks only
`question.type not in SUPPORTED_QUESTION_TYPES` (`dashboard_functions.py:408`),
that set already contains `number`, and the validator has no widget-type branch
except `table`. A map bound to a number question already saved.

That holds **only because the magnitude question is `widget.question`**. Routing
it through `config.value_question` instead would have been refused —
`dashboard_functions.py:552-559` requires an option question there — and would
have needed a validation change. `widget.question` is also already in the
public-dashboard allowlist (`public_scope.py:87-89`), so published dashboards
needed nothing.

**One inherited gap, not fixed here:** `annotate_broken`
(`dashboard_snapshot.py:92-117`) watches `widget.question` for post-publish
deletion, so a deleted magnitude question *is* flagged. It does not watch
`config.value_question` — a pre-existing hole for VIZ-015.b bars.

## Testing

- `VizMap` has an existing test at
  `frontend/src/components/dashboard/__test__/VizMap.test.js` — extend it rather than
  starting fresh.
- **Markers do not render in jsdom.** Leaflet needs real layout, so
  `.leaflet-marker-icon` is never present in tests and a snapshot of the map captures the
  container chrome only. Do not write a test that asserts on marker DOM — it will pass
  whether or not the feature works. Assert on the props handed to `MapCluster`, or on the
  Leaflet map object via a ref, instead.
- Per `CLAUDE.md`, run everything through the wrapper: `./dc.sh exec frontend npm test`.

## Two traps from building this upstream

Both cost real debugging time in `akvo-charts`; both could bite here.

1. **A component can silently render a stale build.** In `akvo-charts` the example app
   resolves the library via `"link:.."` to `dist/`, so source changes were invisible until
   `yarn build` ran — the playground rendered the *previous* version of the component with
   no error at all. If you ever link `akvo-charts` locally rather than installing from npm,
   remember it serves `dist/index.js`, not `src/`.
2. **`MarkerClusterGroup` used to capture its props at mount.** Before 1.3.5, switching
   cluster type on a mounted map left the old icons on screen, because the Leaflet group was
   created once and its `iconCreateFunction` never re-read. Fixed upstream, but it is the
   reason the `key` prop above matters — and a good reminder that Leaflet objects created in
   an effect do not follow React's prop updates for free.

## Sequence as built

1. `akvo-charts` 1.3.4 → 1.3.5. The range in `package.json` covered it but the
   lockfile pinned 1.3.4, so nothing arrived without an explicit bump.
2. Backend: `_number_group_by_id`. No validation change was needed.
3. `useWidgetData`: a third request for the map, joined by id like the status one.
4. `builderConstants` + `BuilderInspector`: `map_mode` written from the picked
   question's type; status-colour controls hidden when it is a number.
5. `VizMap`: branch on mode, `renderPopup={null}`, legend hidden.
6. Tests at the props level, not the DOM level.

Step 2 turned out smaller than feared — one aggregation branch, not an endpoint —
and step 3 slightly larger, because the registration and monitoring cases need
different groupings.
