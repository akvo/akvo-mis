# Public dashboard tenant isolation: design

## Problem

The visualization endpoints that power dashboards are `@api_view` with no
permission class, so with no `DEFAULT_PERMISSION_CLASSES` set they default
to `AllowAny`. Several take a `form_id`, a sequential integer, directly in
the path. An anonymous attacker can therefore iterate
`/visualization/progress/1`, `/2`, `/3` and pull every tenant's form
aggregates without logging in. This is the same class as the public-admin and
mobile-SQLite leaks, but worse, because it is trivially enumerable and
unauthenticated.

An audit split the endpoints into two groups by their actual consumer:

- The public-dashboard data layer, meaning `/visualization/values`,
  `/visualization/values/formula`, `/visualization/escalation/{form_id}` and
  `/visualization/progress/{form_id}`, is consumed only by the public
  `/dashboard/:slug` route (`pages/dashboard/Dashboard.jsx` via
  `DashboardRenderer` and its hooks). Anonymous dashboards are a real, working
  feature: the route is public, whitelisted in `config.js`'s `allowedGlobal`,
  and its config is a static bundle. So these must stay reachable anonymously.
- The authenticated-only viz endpoints, meaning
  `/visualization/formdata-stats/{form_id}`, `/visualization/monitoring-stats`,
  `/maps/geolocation/{form_id}` and `/maps/datapoint/{data_id}`, are consumed
  only by authenticated pages (manage-data map, home). They are `AllowAny` by
  omission, not by intent.

Read-path isolation listed the group-2 endpoints for `for_user` scoping, but
that cannot work while they are `AllowAny`, since an anonymous request has no
user. This iteration owns the whole visualization surface and reconciles that.

## Decisions (from brainstorming)

- Keep public dashboards and host-scope them. The public data layer stays
  anonymous but is bounded to the tenant resolved from the request host, so a
  `form_id` outside the host's tenant returns 404. The enumeration dies while
  the feature survives.
- Tighten the authenticated-only endpoints to `IsAuthenticated` plus
  `for_user`. They have no anonymous consumer; requiring auth closes their
  enumeration and is what read-isolation assumed. This supersedes
  read-isolation's visualization coverage.
- This is security, not a feature. It stops cross-tenant data exposure. It does
  not build per-tenant dashboard configs: the dashboard definition stays a
  shared static bundle, so tenants see the same dashboard *structure* but only
  their own *data*.

## Components

### 1. Host-scope the public-dashboard data layer

For `visualization_values` (`/visualization/values`),
`visualization_values_formula` (`/visualization/values/formula`),
`visualization_escalation/{form_id}`, and `visualization_progress/{form_id}`:

- Resolve `request.tenant`, set by the subdomain middleware and present even
  for anonymous requests.
- Require every form the request references to belong to `request.tenant`.
  The path `form_id`, and any form named in the `values` or `values/formula`
  api block or query params, must satisfy
  `Forms.objects.filter(tenant=request.tenant, pk=<id>).exists()`, and
  otherwise return 404.
- Base the underlying `FormData` and `Answers` aggregation on the tenant's data
  (a `for_user`-style filter by `request.tenant`), so even a shared form id can
  never surface another tenant's rows.
- On the base domain (`request.tenant is None`) these return 404 or empty:
  public dashboards exist only on tenant subdomains.

The endpoints stay `AllowAny`, so anonymous access is preserved; the tenant
boundary comes from the host, not a user.

### 2. Tighten the authenticated-only viz endpoints

For `formdata_stats/{form_id}`, `monitoring_stats`, `GeolocationListView`
(`/maps/geolocation/{form_id}`), and `DatapointDetailView`
(`/maps/datapoint/{data_id}`):

- Add `permission_classes([IsAuthenticated])`.
- Scope their queries by `for_user(request.user)`, so form and datapoint
  lookups 404 on a foreign object.

The implementation plan verifies each endpoint's real consumer before
tightening. Any that turns out to also serve the public dashboard moves to
group 1 and is host-scoped instead.

### 3. Read-isolation reconciliation

Read-isolation's spec and plan list the group-2 endpoints (and the map
`@api_view`s) for `for_user` scoping. Those items move here, with a
note in the read-isolation docs, because the correct fix is auth-tightening
plus scoping (group 2) or host-scoping (group 1), which read-isolation's
user-only model could not express for the `AllowAny` ones.

## Error handling

- An anonymous request on a tenant host for a form outside that tenant returns
  404, which kills the enumeration.
- An anonymous request on the base domain returns 404 or empty, since there is
  no tenant context.
- Authenticated stats and map endpoints: an unauthenticated caller gets 401,
  and a foreign form or datapoint gets 404 via `for_user`.
- A public dashboard config that references a form absent from the host tenant
  renders empty rather than erroring, which is what a shared static config does
  on a tenant that lacks that form.

## Testing

- Public data layer: two tenants on two subdomains; an anonymous viewer on
  tenant A's host gets only A's aggregates from `values`, `escalation`,
  `progress` and `values/formula`; requesting B's `form_id` on A's host returns
  404; the same request on the base domain returns 404 or empty.
- Enumeration is dead: iterating `form_id` on A's host never returns B's
  data.
- Authenticated endpoints: `formdata-stats`, `monitoring-stats`,
  `geolocation` and `datapoint` reject an anonymous caller with 401 and 404 a
  foreign form or datapoint for an authenticated one.
- Reconciliation: read-isolation's visualization tests run here and pass;
  no viz endpoint remains `AllowAny` and unscoped.
- Regression: the full suite passes; with subdomain routing inert
  (`BASE_DOMAIN` unset in tests) the host scope resolves to the tenant-less
  path and existing fixtures are unaffected. The group-1 endpoints then scope
  by the header override or the authenticated user, per the middleware.

## Out of scope

- Per-tenant dashboard *config* authoring. The dashboard definition stays a
  shared static bundle; only the data is tenant-bounded.
- The `/glaas/` public path, the other `allowedGlobal` entry. Audit it
  separately if it serves tenant data.
- Any change to the isolation model beyond the visualization surface.
