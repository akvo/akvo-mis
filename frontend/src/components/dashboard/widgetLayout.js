// =========================================================
// How tall a widget's body is, per type
// =========================================================
//
// Read by both surfaces that draw a widget: the published viewer and the
// builder's preview through `DashboardGrid`, and the editing canvas
// through `BuilderCanvas`. VIZ-006 §3 asks the canvas to show what the
// viewer will show, and a height defined twice is a height that drifts —
// which is exactly what happened. `App.scss:355` pins every akvo-charts
// chart in the app to `height: 500px` via `div[role="figure"]`. The viewer
// overrode it and bounded each cell; the canvas never did, so its
// auto-height cards grew around a 500px chart while the same widget was
// squeezed into 300px in preview. The author reviewed one chart and
// published another.
//
// The numbers started as the mockup's `_bodyStyle` (bar/line 300, pie 320,
// map 380). They are larger now because 300px is not enough for a
// half-width bar chart with date labels — the taller rendering the canvas
// was accidentally showing is the one that reads correctly.
//
// Types absent from this map are auto-height on purpose: a KPI is a line
// of text, a section title is a heading, and a table sizes to its own rows
// and pagination.
export const WIDGET_BODY_HEIGHT = {
  bar: 380,
  line: 380,
  pie: 380,
  scatter: 380,
  map: 380,
};

export default WIDGET_BODY_HEIGHT;
