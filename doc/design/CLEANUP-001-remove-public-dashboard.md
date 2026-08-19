# Remove the public BI dashboard: design

Not part of the MT-* multi-tenant SaaS epic numbering — Asana's own MT-011
and MT-012 are unrelated devops/QA tasks (subdomain deployment, multitenant
user testing). This is a standalone cleanup item found while auditing the
tenancy work, tracked separately as CLEANUP-001.

## Problem

An audit of the visualization surface for tenant leaks (the natural next
step after the MT-009/MT-010 tenancy work) found the same class of bug as
the mobile SQLite leak, but worse: several `@api_view`s have no permission
class, so with no `DEFAULT_PERMISSION_CLASSES` set they default to
`AllowAny`, and take a sequential `form_id` straight from the URL path. An
anonymous attacker can iterate `/visualization/progress/1`, `/2`, `/3` and
pull every tenant's form aggregates without ever logging in.

Those endpoints exist for exactly one feature: the public BI dashboard
builder at `/dashboard/:slug`. It is a large, custom-built system —
roughly 2,900 backend lines and 45 frontend files (chart renderer, its own
compute layer for cross-tabs/KPI stacks/histograms, a JSON-based config
registry, a full map component with its own popup and filter chain) — for
a feature that is, on inspection, both the one carrying the vulnerability
and the one adding most of the surface's complexity.

The decision here is not "harden it" but "remove it." Rather than teach a
general-purpose dashboard config system to be host-scoped and
tenant-aware, this deletes the public dashboard outright and closes the
vulnerability by removing the code that has it.

## Scope decision

The visualization surface splits into two genuinely different consumers,
confirmed by tracing every endpoint to its actual frontend caller:

- **The public BI dashboard** (`/dashboard/:slug`, `DashboardRenderer` and
  everything under `components/dashboard/`, `pages/dashboard/`,
  `config/visualizations/`) — anonymous-access, the complex piece, the one
  with the leak. **Removed.**
- **manage-data's map and monitoring overview**
  (`ManageDataMap.jsx`, `MonitoringOverview.jsx`) — authenticated,
  core operational screens for looking at a tenant's own submitted data,
  unrelated to the dashboard builder except for sharing a Django app.
  **Kept**, and given the `IsAuthenticated` + `for_user` scoping that
  read-isolation (MT-003) originally called for but couldn't apply while
  the endpoints were `AllowAny`.

This is not an even split of "remove everything under `v1_visualization`."
Two backend pieces are shared by both consumers and must stay:
`GeolocationListView` (`/maps/geolocation/{form_id}`) is called by both
`ManageDataMap.jsx` and the dashboard's map widget; `functions.py` is
imported by both `views.py` (kept) and `dashboard_views.py` (removed), so
only its dashboard-only symbols are deleted, not the file.

## What gets deleted

### Backend

Confirmed dashboard-exclusive by import/consumer tracing — deleted whole:

- `dashboard_views.py` (`visualization_values`, `visualization_escalation`,
  `visualization_progress`)
- `dashboard_serializers.py`, `dashboard_examples.py`
- `values_functions.py`, `escalation_functions.py`, `progress_functions.py`
- `formula.py` — its only consumer is `visualization_values_formula`,
  whose only frontend caller is the dashboard map's
  `useMapByParent.js`. Deleted with its serializer
  (`FormulaValuesSerializer` in `serializers.py`) and its test
  (`tests_formula_pure.py`).

Trimmed, not deleted, because they're shared:

- `views.py`: remove `visualization_values_formula` and `DatapointDetailView`
  (the latter's only consumer is the dashboard map's popup card). Keep
  `formdata_stats`, `monitoring_stats`, `GeolocationListView`.
- `functions.py`: remove `resolve_default_administration_id` and
  `split_criteria_by_form` (dashboard-only). Keep
  `apply_criteria_to_monitoring_qs` (used by `monitoring_stats`).
- `serializers.py`: remove the formula and dashboard-only serializers,
  keep `FormDataStatsFilterSerializer` and whatever backs the kept views.
- `urls.py`: remove the `values`, `values/formula`, `escalation`,
  `progress`, and `maps/datapoint` routes. Keep `monitoring-stats`,
  `formdata-stats`, `maps/geolocation`.
- `models.py`: `ViewDataOptions` stays — it backs the kept endpoints, not
  the dashboard. No migration needed; nothing DB-backed is dashboard-only.

### Frontend

Deleted whole, confirmed by consumer tracing that nothing outside this set
references them:

- `components/dashboard/` — the entire tree: `ChartRenderer.jsx`,
  `DashboardRenderer.jsx`, `DashboardMap/*`, `widgets/*`, `compute/*`
  (cross-tab, KPI stack, histogram, fiscal-month rotation, accessibility,
  compliance), `custom-components/*` (the EPS/RWS individual-overview
  widgets).
- `pages/dashboard/` (`Dashboard.jsx`), its export from `pages/index.js`.
- `config/visualizations/` — the JSON dashboard-config files, the
  registry (`listVisualizations()`), and its README.
- `lib/dashboardFilterHints.js`.
- `util/hooks/useDashboardValues.js`, `useDashboardEscalation.js`,
  `useDashboardProgress.js`, `useDashboardFilters.js`,
  `useVisualizationRequest.js`, and their barrel exports in
  `util/hooks/index.js`.

Trimmed:

- `App.js`: remove the `Dashboard` import and the
  `/dashboard/:slug` route.
- `lib/config.js`: remove both entries from `allowedGlobal` (line 663).
  `/dashboard/` goes because the feature is gone; `/glaas/` goes because
  it is already dead — grepping the whole repo finds no page, route, or
  backend endpoint for it anywhere, just this one stale string. `App.js`'s
  `public_state`/`isPublic` checks (`allowedGlobal.map(...).filter(...)`)
  keep working unchanged with an empty array; nothing special-cases a
  non-empty list.
- `components/layout/Header.jsx`: remove `dashboardForms`,
  `showDashboardsMenu`, the `DashboardMenu` dropdown, and the
  `listVisualizations` import. The nav loses the "Dashboards" menu
  entirely.

## Harden what's kept

`formdata_stats`, `monitoring_stats`, and `GeolocationListView` get
`permission_classes = [IsAuthenticated]` (the commented-out line already
sitting in `GeolocationListView` becomes real) plus `for_user(request.user)`
scoping on their form/administration lookups, exactly the pattern MT-003
and MT-009/MT-010 already established. This is the actual fix for the
authenticated half of the original audit; it was blocked before only
because these three shared a Django app with `AllowAny` dashboard
endpoints that made a blanket `IsAuthenticated` impossible to apply
app-wide.

## Error handling

- An anonymous request to any surviving `v1_visualization`/`maps` endpoint
  now gets 401, not data.
- A foreign `form_id` or `data_id` on a surviving endpoint 404s via
  `for_user`, matching every other detail lookup in the codebase.
- `/dashboard/:slug` and every endpoint under it simply stop resolving —
  404 from the router, not a tenant-scoped 404 from a live feature.

## Testing

- The three kept endpoints reject an anonymous caller with 401 and 404 a
  foreign form or datapoint for an authenticated one, per tenant.
- Enumeration is dead: there is no endpoint left that returns data by a
  bare sequential id with no auth.
- Full backend and frontend suites pass with the deleted modules and their
  tests removed; `flake8` and `npm run lint` clean.
- Manual: `/dashboard/anything` 404s; the Header nav shows no Dashboards
  entry; manage-data's map and monitoring overview work unchanged for an
  authenticated user, and reject cross-tenant form ids.

## Out of scope

- Any change to `ManageDataMap.jsx` or `MonitoringOverview.jsx` beyond
  what the auth/scoping change forces (e.g. handling a 401).
- Rebuilding a tenant-scoped public dashboard later. If a public-dashboard
  feature is wanted again, it is a new design against the current
  tenancy model, not a revival of this code.
