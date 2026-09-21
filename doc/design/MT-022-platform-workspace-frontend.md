# Platform workspace frontend: design

**Epic:** MT — Platform Admin Console (`epic/platform-admin-console`)
**Part 2 of 3.** Builds on MT-021's endpoints. MT-023 adds the inspection
banner and workspace switcher.

## Problem

MT-021 gives the deployment an operator identity, a host to serve them on, and
the endpoints to list workspaces, read their counts, suspend them, rename them,
toggle entitlements and manage operators. None of it is reachable from a
browser.

This part builds that surface: an `/admin` route tree served only on
`admin.<BASE_DOMAIN>`, four pages, and the two confirmation dialogs that stand
in front of the destructive actions.

Mockups of every screen: [`MT-022-mockup/`](MT-022-mockup/index.html).
Static HTML in this repo -- open `index.html` in a browser, no build step.

## Decisions

- **No new sign-in page.** The existing `pages/login` is served on the admin
  host unchanged; only the post-login destination differs.
- **No new design language.** The console uses the app's own tokens — Poppins,
  `$blue #1651b6`, the white 86px header, `$bg-page #f0f2f5`, 6px radius,
  round buttons — and antd components already used in `control-center`.
- **Host decides the route tree, not the session.** `RouteList` branches on
  `onAdminHost()` before anything else, the same way it already branches on
  `onBaseDomainHost()`.
- **Destructive actions state consequences as counts, not warnings.** The
  rename dialog shows how many devices and links will break, fetched live.
- **No charts.** The summary is numbers in a table.

## Components

### 1. Host detection

    // util/tenant.js
    export const onAdminHost = () => {
      const base = baseDomain().toLowerCase();
      if (!base) {
        return false;
      }
      return window.location.hostname.toLowerCase() === `admin.${base}`;
    };

Same shape as `onBaseDomainHost()`, and read off the address bar rather than
off the tenant lookup — an unknown workspace resolves to no tenant exactly as
the admin host does, so a lookup cannot tell the two apart. Note the default
differs from `onBaseDomainHost()`: with no base domain that helper returns
`true` (a single-host install *is* the base domain), while this one returns
`false`, because a single-host install has no console.

### 2. Route tree

`RouteList` gains a branch before the existing ones:

    if (onAdminHost()) {
      return <AdminRoutes />;
    }

`AdminRoutes` serves `/login` with the existing `Login` page and the console
pages under `/admin`, everything but login wrapped in a guard that redirects a
non-operator session to `/login`.

| Page | Route | Notes |
|---|---|---|
| Sign in | `/login` | The existing `pages/login`, unchanged |
| Tenants | `/admin/tenants` | Table, search, state filter, counts |
| Tenant detail | `/admin/tenants/:id` | Stat tiles, features, users, danger zone |
| Operators | `/admin/operators` | List, invite, revoke |

The signed-in-on-main-site redirect at `App.js:550` already no-ops for
operators: `UserSerializer.get_subdomain` returns `""` for a tenant-less user,
so `ownWorkspace` is falsy and the effect returns early. **No change needed
there, and it must not be "tidied".**

### 3. A fix that belongs with this work

`LoginForm.jsx` renders the "Create an account" link **twice** — once gated on
`showRegister` (`onBaseDomainHost()`), and again unconditionally a few lines
below. The unconditional copy is a pre-existing bug: it already shows a dead
link on every workspace login page, since `/register` redirects away anywhere
but the base domain. It would do the same on the console. Delete the
duplicate.

### 4. Tenants list

An antd `Table` over `GET /admin/tenants/summary`: subdomain as the identity
(linking to the detail page), the root administration unit's name beneath it,
a state tag, six numeric columns, last activity, entitlement tags, and an
`Inspect` link.

Search filters by subdomain or name; a segmented control filters by state.
**Inspect is disabled for suspended and deleted workspaces** — their hosts no
longer resolve, so offering the link would be offering a dead one. Easy to
miss when reading the API alone; obvious once drawn.

### 5. Tenant detail

Six stat tiles across the top (users, forms, dashboards, datapoints, devices,
last activity), then two columns:

- **Users** — name, email, role, status, device count, and a
  Deactivate/Reactivate button per row. A deactivated user's row states how
  many of their devices are blocked, because that consequence is the whole
  point of the action and is otherwise invisible.
- **Features** — one switch per `FeatureFlags` key, writing through
  `PUT /admin/tenants/:id/features`.
- **Danger zone** — delete, in its own bordered card.

Header actions: Inspect, Rename, Suspend.

### 6. Rename dialog

Opens on `GET /admin/tenants/:id/rename-impact` and renders the counts as
statements of fact:

> **The old address stops working immediately**
> - **23 enrolled mobile devices** will stop syncing and must each be
>   reconfigured by hand in Settings.
> - **3 published dashboard links** will break, including any bookmarked or
>   printed.
> - **1 embedded dashboard** will stop loading on the external sites hosting
>   it.

The submit button stays disabled until the operator types the *current*
subdomain. A warning that says "this may break things" gets clicked through;
one that names 23 devices does not.

### 7. Operators

List, invite by email, revoke. A note on the page explains that the first
operator comes from `createplatformadmin`, because nobody can invite
themselves — otherwise the empty state reads as a bug.

## Data flow

    admin.app.com/login
      → POST /api/v1/login            (existing page, existing call)
      → AUTH_TOKEN cookie, host-only
      → /admin/tenants

    /admin/tenants
      → GET /api/v1/admin/tenants/summary      one query, all counts

    /admin/tenants/42
      → GET /api/v1/admin/tenants/42
      → GET /api/v1/admin/tenants/42/users
      ↳ PUT    /features         toggle
      ↳ POST   /deactivate       suspend
      ↳ DELETE /admin/tenants/42 soft-delete
      ↳ GET    /rename-impact → POST /rename

## Error handling

| Situation | Behaviour |
|---|---|
| Non-operator session reaches `/admin/*` | Redirect to `/login` |
| 403 from any console endpoint | Notification, stay on the page |
| Suspended or deleted workspace | Inspect disabled, state tag shown |
| Rename returns 400 (taken or reserved) | Field-level error on the input |
| `rename-impact` fails to load | Dialog opens with the counts unresolved and the confirm button disabled — never a rename behind an unknown consequence |

That last row matters: failing open here would let someone rename a workspace
without seeing what it breaks, which is exactly the outcome the dialog exists
to prevent.

## Testing

Jest and Testing Library, following `frontend/src/util/__test__/tenant.test.js`
for the `window.location` patching pattern.

- `util/__test__/tenant.test.js` — extend for `onAdminHost()`: true on
  `admin.app.com`, false on `app.com`, false on `acme.app.com`, false with no
  base domain.
- `pages/admin/__test__/Tenants.test.js` — renders counts from a mocked
  summary; the state filter narrows rows; Inspect is disabled for suspended
  and deleted rows.
- `pages/admin/__test__/TenantDetail.test.js` — toggling a feature issues the
  `PUT`; deactivating a user issues the `POST` and updates the row.
- `pages/admin/__test__/RenameDialog.test.js` — the confirm button is disabled
  until the typed subdomain matches; it stays disabled when `rename-impact`
  fails; the counts render.
- `pages/admin/__test__/Operators.test.js` — invite issues the `POST`; revoke
  asks for confirmation.

Run with:

    ./dc.sh exec frontend npm test
    ./dc.sh exec frontend npm run test:ci

## Task sequence

| # | Task | Depends |
|---|---|---|
| 1 | `onAdminHost()`, `/admin` route tree, layout shell, `/login` on the admin host, delete the duplicate register link | MT-021 §2 |
| 2 | Tenants list: table, search, state filter, counts | MT-021 §8 summary |
| 3 | Tenant detail: stat tiles, feature switches, user table | MT-021 §8 |
| 4 | Lifecycle actions: deactivate, activate, delete, with confirmation | MT-021 §4 |
| 5 | Rename dialog: live impact, type-to-confirm | MT-021 §5 |
| 6 | Operators page: list, invite, revoke | MT-021 §8 |

Task 1 unblocks as soon as MT-021's admin host lands, so the console shell can
be built while the tenant endpoints are still in progress.

## Out of scope

- The inspection banner, the read-only ability branch and the workspace
  switcher — MT-023.
- Any redesign of the login page or the app header.
- Charts or time series in the console. If trends are wanted later, the
  summary endpoint grows a date range; the table does not become a dashboard.
