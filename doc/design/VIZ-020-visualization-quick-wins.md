# Visualization layer quick wins: design

## Problem

We looked at GeoLibre (an open-source GIS platform) for ideas on where the
dashboard/map stack could improve, and four things fell out that are cheap
to fix without touching the data model or adding new API surface.

Three separate map components exist today, and they don't agree with each
other:

- [`VizMap`](../../frontend/src/components/dashboard/widgets/VizMap.jsx):
  the dashboard builder's `map` widget (`WidgetTypes.map`, [constants.py:94](../../backend/api/v1/v1_visualization/constants.py#L94)).
  Renders through akvo-charts' `MapCluster`, clusters spatially, colours by
  a `status` field from `config.config.status_colors`.
- [`DashboardMap`](../../frontend/src/components/dashboard/DashboardMap/index.jsx):
  the newer filterable dashboard map, with chip filters, popups, and bucket
  colour via `activeFilter.color_map`. Renders every point as its own
  `react-leaflet` `CircleMarker`, no clustering at all.
- [`MapView`](../../frontend/src/components/map-view/MapView.jsx): the
  "Manage Data" map. Uses akvo-charts' plain `Map.Container`, one
  `L.marker` per row, and papers over overlapping points with manual
  jitter ([`overlapUtils.js`](../../frontend/src/components/map-view/overlapUtils.js))
  rather than clustering.

Each one hardcodes its own tile source, legend, and geo-point filter: the
same `Array.isArray(row.geo) && row.geo.length === 2` check is copy-pasted
into all three. And `VizMap`/`DashboardMap` both point at
`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`, OSM's raw tile
server. That's a real operational risk, not just a style nit. OSM's usage
policy doesn't allow sustained application traffic against that endpoint,
and they will rate-limit or ban an IP range without warning. `MapView`
already does this correctly (`geo.tile`, CartoDB Voyager,
[`geo.js:11`](../../frontend/src/lib/geo.js#L11)), so the fix is just to
point the other two at the same source.

One thing from the original comparison isn't in this package: an
embeddable, unauthenticated dashboard view, à la GeoLibre's `layout=viewer`
+ `postMessage`. Worth flagging why it's out rather than just missing:
CLEANUP-001 deleted the old public dashboard because an anonymous caller
could enumerate `/visualization/progress/<id>` across tenants
([CLEANUP-001 §Problem](CLEANUP-001-remove-public-dashboard.md)). Bringing
embedding back would mean a signed, tenant-scoped, expiring link, which is
a security decision that needs its own sign-off, not something to fold into
a quick-wins pass.

## Scope

Four slices, roughly independent of each other. Do QW-1 first anyway. It's
the shared plumbing the other two lean on, and skipping it just means a
fourth divergent implementation instead of one shared one.

### QW-1: Consolidate the shared map plumbing

Tile config, the geo-point filter, and the "compute a Leaflet center from
`geo.defaultPos()`" boilerplate are duplicated across `VizMap`,
`DashboardMap`, and `MapView`, and two of the three are pointed at the
OSM tile URL flagged above instead of `geo.tile`.

What to do:
- Point `VizMap` and `DashboardMap` at `geo.tile`
  ([`geo.js:11`](../../frontend/src/lib/geo.js#L11)) instead of their local
  `OSM_TILE` const / inline URL string. One tile source, one attribution
  string, everywhere.
- Pull the geo-point filter into `geo.js`, something like
  `geo.hasValidPoint = (row) => Array.isArray(row?.geo) && row.geo.length === 2`,
  and use it in all three places instead of the repeated inline check.
- `geo.defaultPos()` is already shared, so nothing to change there. Just
  confirm all three actually call it instead of falling back to a
  hardcoded `[0, 0]`.

Done when:
- `grep -rn "tile.openstreetmap.org" frontend/src` comes back empty.
- `grep -rn "row.geo) && row.geo.length === 2\|row?.geo) && row.geo.length === 2" frontend/src` finds nothing outside `geo.js`.
- All three maps still render markers at the same positions and zoom as
  before. This is plumbing, not a behavior change, so a visual diff
  should show nothing.

### QW-2: Cluster `DashboardMap`

`DashboardMap` is the widget most likely to carry a lot of points. It's
the general-purpose dashboard map, not scoped to one question the way
`VizMap` is, and right now it draws one `CircleMarker` per row with no
clustering. `VizMap` already solved this: akvo-charts' `MapCluster` with
`type="circle"` draws a self-contained inline-SVG donut per cluster, keyed
by a `groupKey` field, and sidesteps the leaflet.markercluster
stylesheet-resolution problem documented right in
[`VizMap.jsx:16-31`](../../frontend/src/components/dashboard/widgets/VizMap.jsx#L16-L31).
No reason to solve that twice.

Swap `DashboardMap`'s `MapContainer`/`CircleMarker` rendering for
`MapCluster`, following that same pattern:
- Reshape `visiblePoints` into `{ id, point: p.geo, label, groupKey, color }`,
  the way `VizMap`'s `points` memo does it, using
  `colorForParent(String(p.id))` and `bucketForPoint(String(p.id))` for
  `color`/`groupKey`.
- The one real unknown here: `MapCluster`'s `renderPopup` prop gets the
  point object and returns content, but it's not clear yet whether it
  accepts a React node or just a string/HTML. `DashboardMap`'s popup
  (`MapPopupCard`) is a stateful component with its own datapoint-detail
  fetch (`datapointCache`), so if `renderPopup` turns out to be
  string-only, don't force rich content through a callback that wasn't
  built for it. Keep the existing `react-leaflet` `Popup`/`CircleMarker`
  rendering inside each cluster leaf instead. Check this against the
  installed `akvo-charts` version before writing the rest of the slice.
- Leave `DashboardMapHeader`'s chip filters and `useMapFilters`/
  `useMapByParent` alone. They operate on `points`/`byParent` upstream of
  rendering and don't care how the markers get drawn.

Done when:
- A dashboard map widget backed by a form with 50+ geolocated datapoints
  visibly clusters at low zoom and un-clusters on zoom-in, matching what
  `VizMap` already does.
- Chip filtering, popups, and the "click through to datapoint" link
  (`urlTemplate`) still work, whether that ends up being per-marker or
  per-cluster-leaf depending on how the `renderPopup` question above shakes
  out.

`MapView` (the Manage Data map) is deliberately not part of this slice. It
already has a working (if different) overlap mitigation, and its
per-point value rendering (`getMarkerDisplayText`, abbreviated numeric
labels like "12k") doesn't map cleanly onto `MapCluster`'s status-donut
model. Worth a separate look if Manage Data's dataset sizes ever become a
real problem, but not now.

### QW-3: Port auto-binned legends to the dashboard map widgets

This one turned out to already be half-built. [`ManageDataMap.jsx`](../../frontend/src/pages/manage-data/components/ManageDataMap.jsx#L516-L529)
already does the "auto-suggest a renderer from the data" idea borrowed from
GeoLibre: an `isNumeric` flag switches between
[`MarkerLegend`](../../frontend/src/components/map-view/MarkerLegend.jsx)
(categorical, one colour per option) and
[`GradationLegend`](../../frontend/src/components/map-view/GradationLegend.jsx)
(graduated, with thresholds computed by d3's `scaleQuantize` via
`geo.getColorScale`, [`geo.js:26-51`](../../frontend/src/lib/geo.js#L26-L51)).
It just never made it into the dashboard widgets. `VizMap` and
`DashboardMap` only support categorical colouring, hand-configured per
dashboard as `status_colors` / `color_map` in the widget's JSON config. Ask
someone to put "liters of water delivered" on a map widget today and
there's no graduated-colour option at all.

What to do:
- Check the map widget's config schema on the dashboard builder side (see
  VIZ-006/VIZ-008) for somewhere a `value_type: "category" | "number"` flag
  could live, or add one if it's not there.
- When the bound question is numeric, compute thresholds with the existing
  `geo.getColorScale`/`GradationLegend` pair instead of requiring the
  dashboard author to hand-enter a `status_colors` map, the same branch
  `ManageDataMap` already takes.
- Purely additive: existing dashboards using `status_colors`/`color_map`
  keep working exactly as they do now.

Done when:
- A map widget bound to a numeric question shows a graduated legend with
  auto-computed bins, no manual colour config needed.
- Existing dashboards using `status_colors`/`color_map` render exactly as
  they did before (this is a regression check, not really a new test).

### QW-4: Export a dashboard/map view to PNG/PDF

There's currently no way to get a dashboard or map view out of the app for
an offline report, a real, recurring ask for an M&E tool and the direct
analogue of GeoLibre's Print Layout composer (map + legend + scale bar →
PNG/PDF).

- Add an "Export" action to the dashboard viewer toolbar
  ([`DashboardViewer.jsx`](../../frontend/src/pages/dashboards/DashboardViewer.jsx))
  that rasterizes the current view with `html2canvas` and offers a PNG
  download. Check `frontend/package.json` first for an existing dependency
  before adding one. Note that `report_generator.py` on the backend
  already does Excel/DOCX export, but that's server-side tabular export
  and doesn't help here. Add `jspdf` for PDF output if it's not already
  pulled in.
- Scope this to the dashboard viewer as a whole first. It's a single,
  well-defined container to snapshot. A per-widget export button is a
  reasonable follow-up, but not required for this slice.

Done when:
- The exported PNG/PDF visually matches the on-screen dashboard, map and
  legend included, for both a chart-only dashboard and one with a map
  widget.
- Map tiles actually show up in the export, not blank space.
  `html2canvas` and cross-origin tile images are a known bad combination.
  Confirm the tile source's CORS headers allow this; if they don't, fall
  back to Leaflet's own canvas-renderer approach (e.g. `leaflet-image`)
  instead of fighting `html2canvas`.

## Testing

- `./dc.sh exec -T frontend npx eslint <changed files>` clean for every
  slice: curly braces, no `console.log`, prettier formatting, per
  CLAUDE.md's frontend rules.
- Eyeball all three map surfaces after QW-1, since it touches tile config
  shared by all of them.
- QW-2: a dashboard with a form that has enough geolocated datapoints to
  actually trigger clustering at default zoom. Confirm the cluster→leaf
  transition and that filtering/popups still resolve to the right
  datapoint.
- QW-3: one dashboard with a numeric-question map widget, one with an
  existing categorical config. Both should render correctly.
- QW-4: export a map-containing dashboard and a chart-only one; open the
  resulting file and confirm tiles and legend are actually there, not
  blank.
- No backend changes in this package, so the `v1_visualization` suite
  shouldn't need touching. If anything in it starts failing, that's a
  sign a frontend change reached further than it should have.
