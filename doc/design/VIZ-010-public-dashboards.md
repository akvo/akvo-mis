# Public dashboards: design

## Problem

A dashboard is published *to the tenant*: `/api/v1/dashboards` is
`IsAuthenticated`, and a viewer needs an account in that workspace. There is
no way to show one to a district officer, a donor or the public, which is a
routine thing for a monitoring programme to want.

VIZ-001 D-7 ruled out an anonymous surface and said why: *"Public sharing, if
it is ever wanted, is a deliberate feature with its own token model."* This is
that feature, and it deliberately reverses D-7.

It must not be built by leaving `/visualization/*` unauthenticated. Those
endpoints take a sequential `form_id` straight from the query string with no
tenant scoping, so anonymous access to them is not "the dashboards we chose to
publish" — it is every form in every workspace, whether or not any dashboard
references it:

    GET /visualization/values?form_id=1   → 200, real aggregates
    GET /maps/geolocation/1               → 200, datapoint names, GPS,
                                            administration paths
    GET /visualization/progress/1,2,3…    → enumerable

`Forms` is tenant-owned (`tenant_fk` / `TENANT_PATH`), so one workspace
choosing to publish would be publishing every other workspace's data too —
which is not that workspace's decision to make. **This slice does not close
that hole; VIZ-003 still does. What it removes is the reason to leave it
open.**

## Decisions

- **Visibility is a field, not a share token** (D-1). `Dashboard.visibility`
  is `internal` (default) or `public`. The ask is "anyone can see this
  dashboard", not "anyone holding this link", and a token adds a secret to
  store, rotate and leak. An unlisted-link tier can be added later without
  disturbing this.

- **Public exists only on the workspace subdomain** (D-2). `TenantMiddleware`
  already resolves `request.tenant` from the host and 404s a host that names
  no workspace; the base domain resolves to `None`. Reading the tenant from
  there rather than from a parameter makes the public surface per-workspace by
  construction, keeps the base domain as the signup context, and means the
  feature is inert wherever `BASE_DOMAIN` is unset — including the test suite,
  which must opt in with `override_settings`.

- **The anonymous data path is keyed by dashboard and widget, never by form**
  (D-3). This is the decision the whole design rests on. A public request
  names `{slug}` and `{widget_id}`; the server resolves widget → dashboard →
  tenant from its own rows and calls the aggregation functions directly. No
  `form_id`, no `question_id`, no criteria grammar on the wire, so there is
  nothing to enumerate and no query for an anonymous caller to author. A
  widget id that belongs to another dashboard is a 404 for the same reason a
  foreign form is.

- **The server expands `measure`, and the authenticated viewer moves to the
  same endpoint** (D-4). `dashboardMeasure.js` turns `current_state` into
  `monitoring=latest` + `sum_by=parent_id` in the frontend today. The public
  path cannot use it — there is no client trusted to expand anything — so the
  expansion moves to Python. Two copies of that rule is exactly the hazard
  VIZ-008 warned about ("if that expansion is written in two places, one of
  them will eventually be wrong, and the number it produces will look
  perfectly reasonable"), so the authenticated viewer is re-pointed at the
  same endpoint in this slice and the JS expansion is deleted. One
  implementation, one place to be wrong.

- **Public serves the published snapshot only** (D-5). `visibility = public`
  **and** `status = published`. Unpublishing removes a dashboard from the
  public surface immediately, because the read path filters on `status`, not
  on `published_config` being present (VIZ-007 §2).

- **Making a dashboard public is its own permission** (D-6).
  `dashboard_share_public = 13`, continuing VIZ-002's block. Publishing to
  colleagues and publishing to the internet are different acts, and a role
  that may do the first should not automatically do the second.

## Components

### 1. `Dashboard.visibility`

An `IntegerField` with `DashboardVisibility` (`internal = 1`, `public = 2`)
alongside `DashboardStatus` in `v1_visualization/constants.py`, defaulting to
`internal`. One migration, no backfill: every existing row is internal, which
is what it was.

`dashboard_share_public = 13` joins the five VIZ-002 access types in
`FeatureAccessTypes` and the `dashboard_builder` group in `FieldGroup`.

### 2. The anonymous namespace

`api/v1/v1_visualization/dashboard_public_views.py`, every view
`AllowAny`, every one scoped to `request.tenant`:

| Method | URL | Returns |
|---|---|---|
| GET | `/api/v1/public/dashboards` | public, published dashboards on this host |
| GET | `/api/v1/public/dashboards/{slug}` | one dashboard's `published_config` |
| GET | `/api/v1/public/dashboards/{slug}/widgets/{id}/data` | that widget's data |

The queryset is `Dashboard.objects.filter(tenant=request.tenant,
visibility=public, status=published, deleted_at__isnull=True)`. `for_user` is
not available — there is no user — so the tenant comes from the host and the
filter is written out.

Widgets are read from `published_config` and annotated with `is_broken` the
same way VIZ-007 §5 does, on serve rather than at publish time.

### 3. `resolve_widget_data(dashboard, widget, filters)`

In `dashboard_functions.py`. Given a stored widget it decides the endpoint and
parameters the frontend used to decide, then calls the existing aggregation:

| Widget | Calls |
|---|---|
| `kpi`, `bar`, `line`, `pie` | the `/values` aggregation |
| `table` | `handle_escalation` |
| `map` | the geolocation query, plus the status-bucket formula |
| `section_title` | nothing |

`expand_measure()` moves here from `dashboardMeasure.js`:
`current_state` → `monitoring=latest` + `sum_by=parent_id`,
`all_submissions` → `monitoring=all`, `include_unmonitored` →
`include_unanswered`, and neither for a widget on the registration form.

Only the dashboard-level filters from VIZ-001 §4.4 are accepted from the
caller — `from_date`, `to_date`, `administration_id` — and
`administration_id` is validated to sit inside the dashboard's own tenant.
Everything else comes from the stored widget.

### 4. The authenticated viewer moves too

`GET /api/v1/dashboards/{slug}/widgets/{id}/data`, the same resolver behind
`IsAuthenticated` and `for_user`. `useWidgetData` stops building
`/visualization/*` requests and asks for widget data by id;
`dashboardMeasure.js` and its tests are deleted, and the builder canvas and
preview follow, since all three surfaces already share that hook.

The builder still calls `/visualization/*` for nothing — the canvas renders
unsaved widgets that have no id yet. Unsaved widgets therefore keep the
authored path: the canvas posts the widget's config to
`POST /api/v1/manage/dashboards/{id}/preview-widget` and gets the same shape
back. One resolver, three callers, no query grammar in the browser.

### 5. Frontend

- A **Dashboards** entry in the app header, shown to anonymous visitors on a
  workspace host when `/public/dashboards` returns anything, and to
  authenticated users always. It lists public dashboards; the internal list
  stays in the control centre.
- `/public/dashboards/:slug` renders through `DashboardGrid` — the same
  renderer as the viewer and the builder preview, per VIZ-008.
- The builder's settings panel gets the visibility control, gated on
  `dashboard_share_public`, worded as what it does: *"Anyone with the link can
  view this dashboard, without signing in."*
- The dashboard list badges a public dashboard distinctly from a published
  one. "Published" and "public" are different things and the card has to say
  which.

## Data flow

    acme.app.com  (anonymous)
      → TenantMiddleware: request.tenant = acme
      → GET /public/dashboards            → public + published, acme only
      → GET /public/dashboards/water      → published_config, widgets annotated
      → per widget:
          GET /public/dashboards/water/widgets/12/data
            → widget 12 belongs to `water`? else 404
            → expand measure, merge filters, aggregate
            → rows

    app.com  (base domain, anonymous)
      → request.tenant = None → 404 everywhere in this namespace

## Error handling

- The base domain, or a host naming no workspace → 404. The middleware
  answers the second before any view runs.
- An internal dashboard requested anonymously → **404, never 403**. A 403
  confirms the slug exists, which is the leak in miniature.
- A draft, a soft-deleted dashboard, or another workspace's slug → the same
  404. A public viewer cannot tell these apart, which is correct.
- A widget id that is not on the named dashboard → 404.
- An `administration_id` outside the dashboard's tenant → 400.
- A widget whose question was soft-deleted → 200 with `is_broken`, per D-9.
  A public dashboard degrades exactly as an internal one does.

## Testing

- Two tenants, and the matrix that matters: `{public, internal}` ×
  `{published, draft}` × `{workspace host, base domain, other workspace's
  host}`. Exactly one cell returns data.
- Enumeration: a widget id belonging to tenant B's public dashboard, requested
  on tenant A's host, is a 404 — and the response is byte-identical to a
  nonexistent id.
- No public endpoint accepts `form_id`, `question_id`, `criteria`, `columns`
  or `monitoring`. Asserted by inspecting the serializer, not by hoping.
- `expand_measure` has the same three cases its JS predecessor did, and the
  JS one is gone: `grep -rn "monitoring=" frontend/src` returns nothing.
- The authenticated and public paths return identical data for the same
  widget, which is what makes one resolver worth having.
- Turning a public dashboard internal makes it 404 for anonymous callers on
  the next request, with no publish step in between.
- `BASE_DOMAIN` unset: the namespace resolves no tenant and serves nothing, so
  a single-host deployment is unaffected.
- `./dc.sh exec -T backend flake8`, `npm run lint` and `npm run prettier`
  clean. Prettier covers `.scss`, which ESLint does not.

## Out of scope

- Tokenised or unlisted sharing. D-1 leaves room for it; nothing here
  anticipates it.
- Custom domains. `resolve_tenant_from_host` is the single seam and gains a
  branch there when a subscription tier wants one.
- Embedding, export and print (VIZ-001 §13).
- Rate limiting. A public endpoint invites it, and there is none anywhere in
  the app today; it belongs in one deployment-wide iteration rather than here.
- **VIZ-003 is not superseded.** The authenticated `/visualization/*`
  endpoints still take an unscoped `form_id` and still need hardening. This
  slice removes the argument for postponing it.
