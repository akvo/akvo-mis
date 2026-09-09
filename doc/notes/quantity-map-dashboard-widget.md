# Quantity maps for the dashboard map widget

**Status:** proposal / implementation guide
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
- Add `map` to `NEEDS_VALUE_TYPE` (or introduce a map-specific control) so the builder can
  ask *which* number question supplies the magnitude.
- Constrain the question picker in quantity mode to `type === "number"`. There is an
  existing pattern for this — `STACK_QUESTION_TYPES` and the filters around
  `builderConstants.js:217-260` — follow it rather than inventing a new one.

### 3. Backend — supply the number per point

**This is the part I could not verify, and the part most likely to hold you up.**

I searched `backend/api/v1/v1_visualization/` for a map-specific compute path
(`dashboard_functions.py`, `dashboard_read_views.py`, `dashboard_serializers.py`,
`dashboard_snapshot.py`) and found no branch on `WidgetTypes.map`. So the map widget appears
to be fed by a shared row-shaped payload rather than a per-type aggregation — but I did not
trace the endpoint end to end, and I am not going to guess at it.

**Before writing frontend code, confirm:**

1. Which serializer/view produces the rows `VizMap` receives, and whether they already carry
   arbitrary question answers or only `{ id, geo, name, status }`.
2. Whether the numeric answer can be added to that payload without a new endpoint.
3. How the widget's bound question id reaches the backend, and whether validation needs to
   accept a `number` question for `map` the way it currently does for grouping.

If the payload is fixed-shape, this becomes a backend change of similar size to the frontend
one, and the guide above understates the work.

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

## Suggested sequence

1. Answer the three backend questions above. They determine the shape of everything else.
2. Backend: make the numeric answer available per point, plus validation for a `number`
   question bound to a `map` widget.
3. `builderConstants.js`: mode flag, value-question picker, question-type filter.
4. `VizMap.jsx`: branch on mode, drop `renderPopup`, handle the legend.
5. Tests at the props level, not the DOM level.

Steps 3-5 are small. Step 2 is the unknown.
