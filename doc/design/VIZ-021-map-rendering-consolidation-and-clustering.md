# Map rendering consolidation and clustering: design

**Status:** in review — GitHub [#374], PR [#375] **open**, branch
`feature/374-map-rendering-consolidation-and-clustering` (1 commit). Not on
`main`. Ships [VIZ-020](VIZ-020-visualization-quick-wins.md) QW-1 plus a
centering fix that wasn't in that plan. QW-2 (clustering) needs no work —
VIZ-009 already removed its target; see below.

## Problem

Three tile definitions existed, and two of them were wrong.

- [`VizMap`](../../frontend/src/components/dashboard/widgets/VizMap.jsx)
  held a local `OSM_TILE` const pointing at `{s}.tile.openstreetmap.org`,
  OSM's raw tile server. OSM's usage policy doesn't permit sustained
  application traffic there; they rate-limit or ban an IP range without
  warning, so this is an operational risk rather than a style nit.
- [`util/tileLayer.js`](../../frontend/src/util/tileLayer.js) exported the
  same OSM URL again as a second source of truth.
- [`geo.tile`](../../frontend/src/lib/geo.js) — the one `MapView` used —
  was on CARTO, but on the `voyager_labels_under` variant and carrying an
  attribution string crediting "Esri — DeLorme, NAVTEQ, Esri". Those tiles
  are CARTO's, rendered from OpenStreetMap data. The credit named neither.

The point-validity check `Array.isArray(row?.geo) && row.geo.length === 2`
was copy-pasted into `VizMap` and `MapView`.

Separately, the Manage Data map opened in the wrong place. `ManageDataMap`
always seeded the viewport from `geo.defaultPos()`, the neutral world
viewport, no matter where the loaded datapoints actually were — so every
form opened zoomed out to the whole world and the user panned to find their
own data. `MapView.fitBounds` then had no `maxZoom`, so a form with one
datapoint (or a tight cluster) snapped to Leaflet's maximum zoom, where
there is no surrounding context to orient by. And `scrollWheelZoom` was
disabled in the same callback that removes the zoom control, which between
them left the map with no way to zoom at all.

## Decisions

- **`geo.tile` is the only tile definition.** `VizMap` uses it directly;
  `util/tileLayer.js` becomes a one-line re-export rather than being
  deleted, so existing importers don't have to churn in this PR.
- **CARTO Voyager, no `{s}` sharding.** The `{s}` subdomain placeholder is
  a legacy HTTP/1.1 connection-limit workaround; `basemaps.cartocdn.com`
  serves fine as a single host. Attribution now credits OpenStreetMap and
  CARTO, which is what the tiles actually are.
- **`REACT_APP_CARTO_API_KEY` is optional.** Unset, the URL is the public
  keyless basemap — fine for local development, rate-limited in aggregate.
  Set, the key is appended as `?key=`. Being a `REACT_APP_*` variable it is
  inlined into the JavaScript bundle at build time and is readable by
  anyone who loads the app, so **this must be a domain-restricted basemap
  key, never a CARTO account API key with data scopes.** It is plumbed
  through `docker-compose.yml` / `docker-compose.override.yml` for dev,
  `frontend/start.sh` (which writes `frontend/.env` at container start) and
  `ci/build.sh` for production builds. Consequence worth knowing: editing
  `.env` alone does nothing — the frontend container has to be restarted,
  or the production image rebuilt.
- **`geo.hasValidPoint(row)` replaces the copy-pasted filter** in both map
  components.
- **The Manage Data viewport is derived from the data.** `ManageDataMap`
  computes a bbox and center from the loaded points and falls back to
  `geo.defaultPos()` only when no row has usable coordinates. `fitBounds`
  gets `maxZoom: 14` and 20px padding, so a single-point form lands at
  neighbourhood zoom with context around it instead of at maximum zoom.
- **Scroll-wheel zoom is re-enabled** in `MapView`, since the zoom control
  is removed there.

## Components

| File | Change |
|---|---|
| [`lib/geo.js`](../../frontend/src/lib/geo.js) | `tile` moves to keyless/keyed CARTO Voyager with corrected attribution; adds `hasValidPoint` |
| [`util/tileLayer.js`](../../frontend/src/util/tileLayer.js) | Re-exports `geo.tile` |
| [`widgets/VizMap.jsx`](../../frontend/src/components/dashboard/widgets/VizMap.jsx) | Drops local `OSM_TILE`; uses `geo.tile` and `geo.hasValidPoint` |
| [`map-view/MapView.jsx`](../../frontend/src/components/map-view/MapView.jsx) | `disableScrollWheelZoom` → `initMapControls`; bounded `fitBounds`; `geo.hasValidPoint` |
| [`ManageDataMap.jsx`](../../frontend/src/pages/manage-data/components/ManageDataMap.jsx) | Computes center/bbox from loaded points, `geo.defaultPos()` as fallback |
| `docker-compose*.yml`, `frontend/start.sh`, `ci/build.sh`, `env.example` | Plumb `REACT_APP_CARTO_API_KEY` through dev and build |

## QW-2 is already done, by VIZ-009

VIZ-020 scopes QW-2 — the clustering half of this task — entirely to
`DashboardMap`, and describes it as a third map component sitting alongside
`VizMap` and `MapView`. It isn't one. VIZ-009 deleted
`components/dashboard/DashboardMap.jsx` and the whole `DashboardMap/`
directory in [#313] (`41cebba7`, on `main` since 2026-08-31), recording it
in that document's inventory as *"superseded by `widgets/VizMap.jsx`"*.
VIZ-020 was written afterwards against a stale reading of the tree.

That resolves the slice rather than blocking it. The replacement `VizMap`
already renders through akvo-charts `MapCluster`, which is exactly what
QW-2 asked for `DashboardMap` to be changed to, and VIZ-020 excludes
`MapView` from clustering deliberately. So:

- QW-1 is complete as written — with only `VizMap` to fix rather than
  `VizMap` + `DashboardMap`, both of its done-when greps come back empty.
- **QW-2 needs no work.** Its target is gone and its goal is met.
- VIZ-021 therefore reduces to QW-1, which is this PR. The Asana card
  (`1218226404614661`) can be closed on merge; the "and clustering" in the
  task and branch name is vestigial.

The open question VIZ-020 raised under QW-2 — whether `MapCluster`'s
`renderPopup` accepts a React node or only a string — dies with the slice.
It only mattered for porting `MapPopupCard`, which #313 also deleted.

## Testing

`util/__test__/tileLayer.test.js` now asserts that `tileLayer` is
identically `geo.tile` and that the URL is on `cartocdn.com`. Its snapshot
is deleted; it existed only to pin the OSM URL this PR removes.

Nothing covers `hasValidPoint` or the new centering logic, and neither has
an automated test worth writing cheaply — the centering is a viewport
calculation whose failure mode is visual. Manual pass before merge:

- Manage Data, a form with geolocated datapoints: opens framed on the data,
  not on the world.
- Same page, a form with no coordinates: falls back to the world view
  without erroring.
- A form with exactly one datapoint: stops around zoom 14, with visible
  surroundings.
- Scroll-wheel zoom responds on the Manage Data map.
- A dashboard `map` widget still renders and clusters as before — this PR
  changes only its tile source and point filter.

Docker was not running when this document was written, so no test or lint
command was executed against the branch.

## Out of scope

[QW-3](VIZ-020-visualization-quick-wins.md) (graduated
legends, VIZ-022) and QW-4 (PNG/PDF export, VIZ-023). Key rotation and
secret handling for the CARTO key — it is a public, domain-restricted
value by design. The mobile app's maps, which don't share this code.

[#374]: https://github.com/akvo/akvo-mis/issues/374
[#375]: https://github.com/akvo/akvo-mis/pull/375
[#313]: https://github.com/akvo/akvo-mis/pull/313
