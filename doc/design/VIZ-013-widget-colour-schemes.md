# Widget colour schemes: design

**Status:** shipped — GitHub [#353], PR [#354], commit `dc968c2f`.
The Asana card still reads "PR Review"; the code is on `main`.

## Problem

Every widget carried a single "Accent colour" swatch. That is the right
model for a KPI card, which has one number, and the wrong model for
everything else: a bar chart with six categories, a pie with four slices
or a map with five statuses all need a *set* of colours, and one swatch
cannot supply it. Charts fell back to a hardcoded default array, so the
accent picker was a control that visibly did nothing on most widgets.

Map status colours were worse: every option defaulted to the same green,
so a freshly configured map drew a uniform blob and the author had to
hand-enter a colour per option before it meant anything.

## Decisions

- **Replace the swatch with a scheme.** Five ColorBrewer-derived palettes
  of five colours each — Categorical, Blue shades, Green shades, Pastel,
  Warm (`COLOR_SCHEMES`,
  [`builderConstants.js`](../../frontend/src/pages/dashboards/builderConstants.js)).
  Reference: <https://colorbrewer2.org/>.
- **Store the resolved colours, not the scheme name.** Picking a scheme
  writes `config.chart_colors` as a concrete array *and* `color_scheme`
  as the name. Widgets read `chart_colors`, so a published dashboard
  cannot change appearance because someone edited a palette definition
  later, and a per-category override is just an edit to that array.
- **Old dashboards keep working.** A widget with no `color_scheme` falls
  back to `DEFAULT_CHART_COLORS`, which is the Categorical palette — the
  same five colours the charts were already hardcoding. Nothing needs a
  data migration.
- **Map statuses get a colour each, automatically.** Selecting the status
  question pre-fills `config.status_colors` by walking the question's
  options against the active scheme
  ([`BuilderInspector.jsx:475`](../../frontend/src/pages/dashboards/BuilderInspector.jsx#L475)).
  Per-option override stays available underneath.

## Components

Colour reaches a widget in one shape — `config.chart_colors`, an array —
consumed by `VizBar`, `VizLine`, `VizPie`, `VizKPI` (first entry only),
`VizScatter` and `VizMap`. `VizMap` additionally reads `status_colors`
for its per-option mapping.

The map is the only widget that draws a legend
([`VizMap.jsx:54`](../../frontend/src/components/dashboard/widgets/VizMap.jsx#L54)),
shown only when more than one distinct colour is in play. Charts set
`legend: { show: false }` and rely on axis labels instead; a legend that
repeats the x-axis is noise. The task's "generate a colour legend?"
question is therefore answered for maps and deliberately declined for
bar/line/scatter.

## Out of scope

Graduated (numeric) colour scales for map widgets. `geo.getColorScale`
and `GradationLegend` already exist for Manage Data's map and have not
been ported to the dashboard widgets — tracked in
[VIZ-020 QW-3](VIZ-020-visualization-quick-wins.md).
