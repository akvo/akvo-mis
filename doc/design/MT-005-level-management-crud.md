# Level management (CRUD): design

## Problem

After isolation is complete, a freshly registered tenant has exactly one
level, the unnamed level 0 created at registration, plus its root unit.
There is no way, through the UI or API, to define deeper tiers ("Province",
"District", …). That blocks everything downstream: administrative units below
the root, roles (which bind to a level), and meaningful data scoping. Level
creation exists today only in the seeder and the registration flow; there is
no create, update, or delete endpoint.

This iteration adds tenant-scoped level management, both the API and the
screen to drive it, so a tenant superadmin can build their hierarchy's shape
through the app. It is the onboarding-completeness step that follows
isolation.

## Decisions (from brainstorming)

- API and UI ship together. An API with no screen does not unblock a real
  tenant; the iteration's point is that onboarding can proceed through the
  app.
- Append-only, delete-deepest, freeze. Rename is always allowed; add
  appends at the tenant's `max(level) + 1`; delete removes only the deepest
  tier; add and delete freeze once the tenant has units below its root.
  Arbitrary insertion, reordering, and cascading re-pathing are rejected as
  disproportionate to a depth that is set once during onboarding.
- Delete blocks on bound roles. `Role.administration_level` cascades to
  roles, their access rows, and user assignments. Rather than silently wipe
  them, a level with any bound role cannot be deleted (400).
- Separate route. Management lives at `/levels-management`, leaving the
  existing `GET /api/v1/levels` (already tenant-scoped by read isolation, and
  fetched by the frontend store) untouched.

## Prerequisite correction

This iteration reuses `for_user`. While designing it, `Role`'s FK to `Levels`
was confirmed to be named `administration_level`, not `level`. The
read-isolation and tenant-scoping plans specify `Role`
`TENANT_PATH = "level__tenant"`, which is wrong; it must be
`"administration_level__tenant"`. Those plans are unimplemented, so this is a
documentation fix, applied to:
`docs/plans/2026-07-23-tenant-scoping-database.md` and
`docs/plans/2026-07-24-tenant-isolation-read-filtering.md`.

## Components

### 1. Levels management API

A superadmin-only `LevelViewSet` routed at `/api/v1/levels-management`, every
operation scoped through `for_user(request.user)` so a tenant sees and
mutates only its own tiers.

- `GET /levels-management` returns the tenant's levels ordered by `level`.
- `POST /levels-management` creates. `tenant` is stamped from
  `request.user.tenant`; `level` is derived server-side as
  `(max level for this tenant) + 1`. A client-supplied `level` is ignored.
  Only `name` is accepted, and it may be empty. Frozen when the tenant has
  units below root.
- `PUT|PATCH /levels-management/{pk}` renames. Only `name` changes;
  `level` and `tenant` are immutable. Never frozen.
- `DELETE /levels-management/{pk}` deletes the deepest tier only.
  Allowed only when all of these hold: it is the tenant's deepest level; the
  tenant has no units below root; no `Administration` sits at that level; no
  `Role` is bound to it.

Permission: superadmin (`is_superuser`, which post-isolation means
tenant-admin). A non-superadmin gets 403.

### 2. The freeze and delete gates

Freeze gate (add and delete):
`Administration.objects.for_user(user).count() <= 1`. A count of 1 is the
root alone; anything more means units exist below root and structure is
frozen. Rename ignores this gate.

Delete has additional guards, checked in order, each a distinct 400 message:

1. The level is not the tenant's deepest: "only the deepest level can be
   removed".
2. Units exist below root (the freeze gate): "levels cannot be removed
   once administrative units exist".
3. An `Administration` sits at this level: the same units message. This is
   the case that protects level 0, whose root unit lives there.
4. A `Role` is bound to this level: "this level is in use by one or more
   roles; remove them first".

In practice, once delete-deepest and the freeze gate both pass, the only
`Administration` that can be at the target level is the root at level 0, so
guard 3 is what forbids deleting the last remaining level while the root
exists.

### 3. Levels management screen

A master-data screen, superadmin-gated, reachable from the master-data area.

- Lists the tenant's levels in depth order, marking the top tier.
- Add appends a tier, clearly shown as the next level down.
- Rename works on any tier inline, at any time.
- Delete removes the deepest tier.
- When the tenant has units below root, add and delete controls are disabled
  with an inline explanation; rename stays available. The client may
  pre-disable for UX but must handle a server 400 regardless, since the
  server response is authoritative.
- After every successful mutation the screen calls `fetchLevels()` (the store
  refresh introduced with runtime levels delivery) so dependent screens see
  the change without a reload.

## Data flow

    Registered tenant (level 0 + root only)
      → GET  /levels-management            → [level 0]
      → POST /levels-management {name:"Province"}  → level 1 (tenant-stamped)
      → POST /levels-management {name:"District"}  → level 2
      → PUT  /levels-management/{id} {name:"County"} → rename, any time
      → (tenant uploads units) → add/delete now frozen
      → DELETE /levels-management/{deepest} before units → removes deepest

## Error handling

- All structural violations return 400 with a message naming the reason: not
  deepest, units exist, or roles bound. The client surfaces the message
  rather than a raw error.
- `level` and `tenant` in a write payload are never bound. `level` is
  derived and `tenant` is stamped.
- A level id belonging to another tenant is not found via `for_user`, so it
  returns 404.
- A non-superadmin gets 403.
- Create and delete run inside a transaction so a rejected mutation leaves
  the level set unchanged.

## Testing

- Rename succeeds at any time, including after units exist.
- Add appends at `max(level) + 1` for the tenant, and is rejected once units
  exist below root.
- Delete removes only the deepest tier, and is rejected on a non-deepest
  tier, when units exist below root, when an `Administration` sits at the
  level (level 0 with its root), and when a `Role` is bound to the level.
- Isolation: tenant A cannot list, rename, or delete tenant B's levels;
  a B level id returns 404 for A.
- Permission: a non-superadmin is refused at every verb.
- Screen: renders the tenant's levels in depth order; add, rename, and
  delete each drive the API and refresh the store; the frozen state disables
  add and delete with an explanation while leaving rename active.
- Regression: the existing `GET /api/v1/levels` read is unchanged; the
  seeder and registration paths, which create levels directly, are untouched.

## Out of scope

- Inserting a tier at an arbitrary position, reordering, or any cascading
  re-pathing of units.
- Changing what a level *means*, meaning its role in scoping or naming.
- Administration bulk-upload changes (blank-row handling, pollable jobs),
  which are the next onboarding iteration.
- Creating any levels at registration beyond the existing level 0.
- Subdomain routing and tenant management UI.
