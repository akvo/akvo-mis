# Free-tier registration foundation: design

## Problem

Akvo MIS is moving toward a multi-tenant SaaS product with a free tier. Today a
fresh deployment cannot bootstrap itself: the frontend config bakes in a
country-specific TopoJSON file, and the only way accounts come into being on an
empty database is a hardcoded `admin@akvo.org` / `Test105*` superuser
auto-created by the login endpoint.

This workstream supersedes the 2026-07-21 "SaaS Instance Bootstrap" spec and
sprint plan, which are abandoned in favour of smaller steps. The goal of this
iteration is deliberately narrow:

1. Drop the TopoJSON object from `config.js`.
2. Create a `Tenant` table and relate superusers to tenants.
3. Add a free-tier registration form: a registrant becomes a tenant superadmin
   with a usable control center.

Multi-tenancy proper (scoping data by tenant, subdomain routing) is future
work. In this iteration only the table and the user link exist. Other features
are allowed to break or behave oddly across tenants; that is accepted.

## Decisions (from brainstorming)

- Post-registration state is a usable control center. Registration creates
  enough hierarchy (level 0 plus a root administration unit) that the
  superadmin's profile resolves and the control center renders.
- Multiple registrations are allowed and share global data. Tenant #2's
  superadmin sees, and can modify, the same levels and administration units as
  tenant #1. That is visibly wrong for real use and accepted: the tenant FK
  laid down now is what fixes it later.
- Form fields are account plus subdomain: email, password, first name, last
  name, subdomain. The subdomain is stored on the tenant for future routing.
- Level 0 is created without a name. The empty string works because
  `Levels.name` is a non-null `CharField`.
- No email verification. Register, then be logged in immediately. Mailjet is
  already integrated, so verification can be added later without rework.
- The login-time auto-create of `admin@akvo.org` is disabled outside test runs.
  Registration is now how accounts come into being; a hardcoded credential
  auto-created on a public endpoint undermines that and is a security hole on
  any reachable instance. It is gated behind a new `settings.TESTING` flag
  rather than deleted, because 43 test modules log in as `admin@akvo.org`
  relying on the auto-create side effect. Full deletion is a future cleanup
  with the same production behavior.

## Delivery: three sequential PRs

Each lands green on its own:

1. TopoJSON drop: pure deletion, zero relation to tenancy.
2. Tenant table: one migration, no behavior change.
3. Registration: endpoint plus page, depends on the tenant table.

The topojson drop is first because it is the standing decision from earlier
analysis, and it keeps the registration review free of map-code deletions.

## Components

### 1. Drop TopoJSON (backend + frontend)

Backend:

- `generate_config.py`: remove the `source/{COUNTRY_NAME}.topojson` read and
  the `var topojson` emission. `levels`, `appConfig` and `roleFeatures` stay
  baked. `COUNTRY_NAME` is no longer imported here, though it survives
  elsewhere: the entities CSV path still uses it.
- `backend/source/fiji.topojson` stays on disk for now. The seeder's
  production path (`administration_seeder.py:87`) still reads it, and seeder
  changes are out of scope. The file is deleted together with that seeder
  path in a future step.

Frontend:

- `lib/geo.js`: remove the module-scope `window.topojson` dereference and
  everything derived from it: `geojson`, `countiesjson`, `getGeometry`,
  `shapeLevels`, `getBounds`. Keep `tile`, `getColorScale`, `fixCoordinates`,
  `normalizeLon`, `shiftLonPositive`. Reimplement `defaultPos()` as a neutral
  world view returning the legacy `{ coordinates, bbox }` shape so callers
  need no reshaping.
- `components/map-view/MapView.jsx`: remove the
  `Map.getGeoJSONList(window?.topojson)` polygon layer and the code orphaned
  by it (`mapStyle`, `selectedAdm`, the `takeRight` import). The fullscreen
  button falls back to the new `defaultPos()` bbox.
- `pages/manage-data/components/ManageDataMap.jsx`: remove the `getBounds`
  zoom-to-selection call; the map stays at the default viewport.
- Delete `components/map/index.js` and `components/maps/Maps.js`, which are
  exported from the barrel but imported by no page, along with their exports
  in `components/index.js`.
- `setupTests.js`: remove the `window.topojson` mock. Rewrite
  `lib/__test__/geo.test.js` for the surviving exports.

Accepted losses: the administration boundary polygon overlays and
zoom-to-selection. Markers, legends, and colour gradation are unaffected.
The polygon join was a name string match against the shapefile and cannot
survive customer-defined administrative units anyway.

### 2. Tenant table + user link (backend)

The new model goes in `v1_users` rather than `v1_profile`. That app already
imports `v1_users.models.SystemUser`, so the reverse FK would be circular, and
all registration machinery lives in `v1_users` anyway:

    class Tenant(models.Model):
        subdomain = models.CharField(max_length=63, unique=True)
        created_at = models.DateTimeField(auto_now_add=True)

`SystemUser` gains:

    tenant = models.ForeignKey(
        Tenant, null=True, default=None,
        on_delete=models.PROTECT, related_name="users",
    )

Nullable so every existing user (and the seeder's fake users) is untouched.
`PROTECT` because deleting a tenant that still has users should be an explicit
future decision, not a cascade. One migration; no endpoint, no serializer
change, no behavior change anywhere.

### 3. Free-tier registration (backend + frontend)

`POST /api/v1/register` is public, no auth. Payload: `email`, `password`,
`first_name`, `last_name`, `subdomain`.

Validation:

- `email` unique among users, valid format; `password` through the existing
  password validators.
- `subdomain` unique among tenants, slug format (lowercase letters, digits,
  hyphens; no leading or trailing hyphen; max 63 chars, which makes it a valid
  DNS label, since it will one day be one).

One atomic transaction:

    Tenant(subdomain=…)
    SystemUser(email=…, is_superuser=True, tenant=…)
    Levels(level=0, name="")                     — only if no level 0 exists
    Administration(parent=None, level=<level 0>,
                   name=<subdomain>)             — only if no root exists

The level-0 and root creation is conditional because registrations after the
first reuse the existing global hierarchy (see Decisions). The endpoint returns
the same auth token payload as login, so the registrant lands logged in.

Auto-create gating: the empty-user-table auto-create of `admin@akvo.org` /
`Test105*` in the login view is gated behind `settings.TESTING`, true only
under `manage.py test`. On a fresh production instance the login page simply
rejects unknown credentials; the way in is `/register`. The 43 test modules
that rely on the auto-create keep working unchanged.

Frontend:

- Public `/register` page, a plain Ant Design form matching the login page's
  look, exported through `pages/index.js`, routed in `App.js` outside the
  auth guard.
- A "Register" link on the login page.
- On success: store the returned token exactly as login does and redirect to
  the control center.

## Data flow

    Empty database
      → POST /api/v1/register        → Tenant + superadmin + level 0 + root unit
                                     → auth token, registrant logged in
      → control center renders       → profile resolves the root administration
      (later iterations: levels management, tenant scoping, subdomain routing)

## Error handling

- Duplicate email or subdomain returns 400 with per-field errors. The
  transaction is atomic, so no partial tenant or orphaned user is reachable.
- A malformed subdomain returns 400 naming the slug rule.
- The register endpoint stays open permanently. There is no "instance claimed"
  state. Abuse controls (rate limiting, verification) are future work.

## Testing

Backend:

- Registration on an empty database creates tenant, superuser, level 0, and
  root unit atomically; the profile endpoint then returns a real
  administration.
- A second registration creates a new tenant and superuser but no second level
  0 or root unit.
- Duplicate email, duplicate subdomain, and malformed subdomain are each
  rejected with 400 and create nothing.
- With `TESTING` overridden to `False`, the login endpoint no longer
  auto-creates `admin@akvo.org` on an empty user table.
- `generate_config` succeeds with no topojson file present; the emitted config
  contains no `var topojson`.

Frontend:

- `/register` renders, validates required fields, submits the exact payload,
  and redirects on success.
- `geo.test.js` covers the surviving exports; the full suite passes with the
  `window.topojson` mock removed.
- Lint clean (`flake8`, `npm run lint`), with no `eslint-disable`.

## Out of scope

- Tenant scoping of any query, model, or permission.
- Subdomain routing or per-tenant URLs.
- Email verification, rate limiting, CAPTCHA.
- Levels management UI, seeder changes, bulk-upload fixes. These were all part
  of the abandoned 2026-07-21 plan and return as separate future steps.
- Restoring map boundary overlays, which would join on `Administration.code`
  rather than names. That is a future feature.
