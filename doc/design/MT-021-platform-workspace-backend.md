# Platform workspace backend: design

**Epic:** MT — Platform Admin Console (`epic/platform-admin-console`)
**Part 1 of 3.** MT-022 builds the console UI on these endpoints; MT-023
adds cross-tenant inspection and workspace switching.

## Problem

The deployment has tenants but no way to operate them. There is no address at
which Akvo staff can sign in as themselves, no way to see how many workspaces
exist or how much is in them, no way to suspend a workspace that has stopped
paying, and no way to turn on a commercial feature without editing an
environment variable and restarting the process.

That last one is the sharpest. Embedded dashboards are sold per workspace, and
the entitlement is `EMBED_TENANTS` — a comma-separated environment variable
parsed into a `frozenset` at startup. Selling the feature to a customer means
a deploy.

This closes the gap the multi-tenant roadmap deferred as item 6.E: *"any
tenant-management / platform-admin capability (no way to suspend, delete, or
inspect tenants — fine for launch, wanted operationally later)"*.

This part builds the backend: a platform-operator identity, a host to serve
them on, tenant lifecycle and entitlements, and the read endpoints the console
needs. Reading a tenant's *data* is deliberately not here — that is MT-023.

## Decisions

- **A platform admin is a new flag, never `is_superuser`.** That flag already
  means *workspace owner* everywhere in this codebase and would grant
  workspace powers by accident.
- **The console lives on a reserved `admin.` host**, resolved in
  `utils/tenant_host.py` beside `is_embed_host()`. Host parsing stays in one
  module.
- **Login is relaxed on that host only**, and only for tenant-less platform
  admins. No new sign-in page: the existing `/login` is served there.
- **A tenant has three states on two columns.** Deactivated and deleted differ
  in reversibility and visibility, not in enforcement.
- **Delete is soft, with no purge in this epic.** Every tenant FK is `PROTECT`.
- **Renaming a subdomain is a hard rename** behind a warning computed from
  live data. No alias table.
- **No `Tenant.name` column.** The subdomain is the name.
- **Entitlements live in a JSON column**, validated against a constants class
  at the serializer boundary.
- **Console endpoints query unscoped, visibly**, never through `for_user()`.

## Components

### 1. Platform admin identity

    class SystemUser(...):
        is_platform_admin = models.BooleanField(default=False)

A platform admin is `tenant=None, is_platform_admin=True`. The two flags are
independent and no code path sets both.

The name matters beyond the column. In this epic **operator** means a platform
admin, and **superadmin** keeps its existing meaning of workspace owner.
Reject any new code that says "super admin" for the platform-level actor.

    # utils/custom_permissions.py
    class IsPlatformAdmin(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            return bool(
                user.is_authenticated
                and user.is_platform_admin
                and user.tenant_id is None
            )

Operator zero comes from a management command, because nobody can invite
themselves and a fresh deployment has nobody to send the first invitation:

    ./dc.sh exec backend python manage.py createplatformadmin \
        --email ops@akvo.org

It follows the shape of the existing `createsuperuser` override and refuses to
create an account that already exists in a tenant.

### 2. The admin host

    # utils/tenant_host.py
    ADMIN_SUBDOMAIN = "admin"

    def is_admin_host(host):
        """Does this host serve the platform console?"""
        if not settings.BASE_DOMAIN:
            return False
        return _normalize(host) == f"{ADMIN_SUBDOMAIN}.{settings.BASE_DOMAIN}"

This mirrors `is_embed_host()` deliberately. A future custom-domain tier still
has one file to change.

The alternative — `<base domain>/admin` — was rejected because the base domain
is the public signup page, and a privileged session on the same origin as an
anonymous marketing surface puts the `AUTH_TOKEN` cookie (which is not
`HttpOnly`) within reach of any script later added to that page.

`resolve_tenant_from_host()` must never resolve this host to a tenant. That is
free once registration reserves the label:
`RegisterSerializer.validate_subdomain` gains the reservation beside the
existing `EMBED_HOST` collision check, for the same reason that one exists, and
the rename endpoint applies the same rule.

**The migration deliberately does not enforce it.** An earlier draft had it
refuse to apply when a `Tenant` row already held `subdomain="admin"`. That
hardcodes one label into an irreversible place: which label the console answers
on is a decision this deployment may revisit — `platform` is as plausible as
`admin` — and a migration keyed to the string would turn a later change of mind
into a schema problem. `ADMIN_SUBDOMAIN` is a single constant in
`utils/tenant_host.py`, and with no migration referencing it, changing it is a
one-line edit. A pre-existing row is renamed by hand instead.

With `BASE_DOMAIN` unset — mohhs, unicef-fsm, and the whole test suite —
`is_admin_host()` is false for every host and the console is unreachable.
Tests that exercise it opt in with `override_settings`.

### 3. Login on the admin host

`login()` currently refuses any sign-in when `BASE_DOMAIN` is set and the host
resolves to no tenant:

    if settings.BASE_DOMAIN and getattr(request, "tenant", None) is None:
        return 400 "Sign in at your workspace address, not the main site"

An operator has no tenant, so this refuses them everywhere. The relaxation is
narrow: permit sign-in on the admin host, and only for a user that is both
tenant-less and `is_platform_admin`. A workspace account whose credentials are
typed into the console gets the same 400 it gets on the base domain, so the
console is not an oracle for whether an email exists in some tenant.

`authenticate()` is already called with `tenant=None` here.
`TenantAwareBackend` handles that by scanning every user with the email and
returning the one whose password matches. Acceptable, but **the platform-admin
filter must be applied to the returned user**, not assumed from the lookup.

**No new sign-in page is built.** The console reuses `pages/login` as it
stands, served on the admin host; only the post-login destination differs. A
second login design would be a second thing to keep in step with password
rules, activation and error states, for no gain.

### 4. Tenant lifecycle

    class Tenant(models.Model):
        subdomain  = CharField(max_length=63, unique=True)
        is_active  = BooleanField(default=True)   # new
        deleted_at = DateTimeField(null=True)     # new
        features   = JSONField(default=dict)      # new
        created_at = DateTimeField(auto_now_add=True)

| State | `is_active` | `deleted_at` | Host resolves | Reversible in UI |
|---|---|---|---|---|
| Active | `True` | `None` | yes | — |
| Deactivated | `False` | `None` | no | yes |
| Deleted | any | set | no | no |

Both non-active states are enforced at one line —
`resolve_tenant_from_host()` gains `.filter(is_active=True, deleted_at=None)`
— so an unreachable workspace produces the same "Workspace not found" 404 a
typo'd subdomain does. The frontend needs to learn nothing new.

**A live JWT must not outlive the suspension**, and filtering in the resolver
is what achieves that — no second check is needed. `ACCESS_TOKEN_LIFETIME` is
12 hours, so a check at sign-in alone would leave everyone already signed in to
a suspended workspace working for the rest of the day. Because the resolver
filters, the host stops resolving for *every* request, and the middleware's
existing unresolvable-host branch 404s them all, token or no token.

`public_tenant()` is deliberately left alone. Its `BASE_DOMAIN` branch reads
`request.tenant`, which the filter has already vetted; its fallback branch
serves a single-host install, where suspending the only workspace is not an
operation anyone performs.

**Delete is soft and this epic ships no purge.** Every tenant FK is
`on_delete=PROTECT`, deliberately, so that removing a tenant that still owns
data stays an explicit decision. A hard delete means flipping those to
`CASCADE` across every tenant-owned model plus object-storage cleanup, and the
migration is the risky part, not the endpoint. The accepted cost: no
self-service answer to an erasure request, and storage is never reclaimed.
Both stay shell operations until someone asks for better.

### 5. Renaming a subdomain

"Edit tenant name" means changing the address, not a display label. There is
deliberately **no `Tenant.name` column**: a second field would be a synonym
that drifts out of step with the address people actually type. The console
shows the subdomain as identity, and where a human label helps, the root
`Administration` unit's name, which `/register/configure` already creates.

Most of the system survives a rename for free, because the subdomain is
derived at read time and never cached: `resolve_tenant_from_host()` looks it
up live, `tenant_web_url()` builds activation links from it live, and
`UserSerializer.get_subdomain` and the middleware's 403 redirect hint are live
reads. Moving the embed entitlement off `EMBED_TENANTS` (§6) removes the one
place that keyed anything by the subdomain *string*, which is why §6 must land
before this.

Three things genuinely break, and the endpoint does not pretend otherwise:

1. **Mobile devices in the field.** `app/src/database/tables.js` persists
   `serverURL` per device, set once at `GetStarted` and editable only in
   Settings. `MobileAssignmentToken.lifetime` is 99999 days, so devices never
   re-authenticate and never re-fetch configuration. After a rename every
   enrolled device's sync 404s, with no push channel to correct it.
2. **Public dashboard URLs** — bookmarks, partner sites, printed reports.
3. **Embedded dashboards** — `<iframe>`s on third-party pages.
   `embed_views.py` suggests the embed document deliberately knows no
   subdomain, so this may survive; confirm during implementation rather than
   assume.

A subdomain-alias table would turn a rename from an outage into a redirect and
was considered; it is out of scope, and remains the obvious upgrade if
renaming turns out to be common. Without it the mitigation is an honest,
computed warning:

    GET /admin/tenants/<id>/rename-impact
      → {"published_dashboards": 3, "public_dashboards": 2}

There is no `mobile_devices` count. The app syncs against the deployment's own
address rather than a workspace's, and its replies are partitioned by the
token's assignment rather than by the host, so a rename leaves every enrolled
device working.

**Corrected during MT-022.** This originally returned an
`embedded_dashboards` count, which was wrong twice over. The spec asked for
third-party `<iframe>` breakage to be *confirmed rather than assumed*, and
confirming it showed embeds survive a rename: `embed_url_for` builds
`EMBED_HOST/api/v1/embed/<token>` and the token carries a dashboard id, never
an address. It also double-counted, because a published embed dashboard has a
`published_config` and so was counted again as a link. The two dashboard
counts now partition the published set — internal links, and the publicly
shared ones whose readers cannot be told the new address.

The dialog states those as facts about *this* workspace and requires the
operator to type the current subdomain to confirm. A warning that says "this
may break things" gets clicked through; one that says "23 enrolled devices
will stop syncing" does not.

The endpoint reuses `RegisterSerializer`'s DNS-label `RegexField` and its
`validate_subdomain` embed-collision check, plus the `admin` reservation.
Uniqueness stays a database constraint turned into a 400, matching
`register()`.

It also renames the master-data directory. `utils/custom_generator.py` puts
device SQLite files at `./source/<subdomain>/<table>.sqlite`. After a rename
that path is a new empty directory; `download_sqlite_file` regenerates lazily
when a file is missing, so it self-heals, but it leaves orphans under the old
name and makes one device sync slow. An `os.rename` avoids both and is
best-effort — a failure logs and falls through to lazy regeneration.

### 6. Feature entitlements

    # api/v1/v1_profile/constants.py
    class FeatureFlags:
        embedded_dashboard = "embedded_dashboard"
        FieldStr = {embedded_dashboard: "Embedded Dashboard"}

`tenant_may_embed()` keeps its shape and changes one line:

    def tenant_may_embed(tenant):
        if not settings.EMBED_HOST or tenant is None:
            return False
        return bool(tenant.features.get(FeatureFlags.embedded_dashboard))

`EMBED_HOST` stays the *deployment* capability — without an origin of its own
there is nowhere safe to run a third-party snippet, whatever was sold.
`EMBED_TENANTS` was the *commercial* entitlement and becomes a one-time data
migration into `features`; the setting is then deleted, and with it the last
thing keyed by subdomain string.

A JSON column gives up per-key validation and indexability. Validation is
bought back at the boundary: `PUT /admin/tenants/<id>/features` validates every
key against `FeatureFlags.FieldStr` and rejects an unknown one with 400, so a
typo is a failed request rather than a silently-false flag. Indexability is not
bought back — "which tenants have embedding" becomes a scan. With tenants in
the tens that is fine; at thousands the answer is a real column or a join
table.

### 7. User deactivation

**The mobile requirement is already satisfied.**
`IsMobileAssignment.has_permission` ends with `return user.is_active`, so
flipping the flag refuses every device call on the next sync. Two real gaps
remain, and they are the whole of the mobile work:

1. **Soft-deleted users are not checked.** `IsMobileAssignment` consults
   `is_active` but not `deleted_at`, so a soft-deleted user's device keeps
   syncing indefinitely. A pre-existing bug this epic's requirement makes
   visible; one-line fix, and it gets a test of its own.
2. **The app's handling of a mid-sync 403 was wrong**, as the investigation
   this called for found. `syncFormVersion` caught the 403, sent it to Sentry
   and returned, so the background task rescheduled and the device polled
   indefinitely; submission sync showed a generic red "failed"; the datapoint
   sync showed a raw error toast. Nothing named the cause.

   The guard is an axios response interceptor, because all three sync paths
   share one client and a check per caller is a check the fourth caller
   forgets. It lives in `background-task.js`, not `api.js`: the client is
   imported by most of the app and most of its test suite, and pulling
   `expo-background-task` into it would make every one of those imports need
   a native module. A 403 reaches this app from `IsMobileAssignment` and
   nowhere else, so there is no other meaning to disambiguate.

   It notifies once and unregisters both sync tasks — repeating the message
   every 15 minutes nags about something only an administrator can undo, and
   polling an endpoint that will keep refusing costs battery and load for
   nothing. That forced a second change: `handleOnRegisterTask` re-registered
   only tasks already registered, so unregistering would have left sync
   permanently dead rather than dormant. It now registers the two sync tasks
   when absent, which is what makes reactivating an account and reopening the
   app resume syncing.

### 8. Console API

All behind `IsPlatformAdmin`, all on the admin host, all querying
`Tenant.objects` directly rather than through `for_user()` — the bypass is
visible in each view rather than hidden in a shared queryset.

This is safe by construction rather than by vigilance: `for_user()` on a
tenant-less user filters `tenant IS NULL`, so an operator hitting any
*ordinary* endpoint gets nothing back. Cross-tenant reading has to be opted
into explicitly, and MT-023 is the only opt-in.

Console code lives in `admin_views.py` and `admin_serializers.py` inside
`v1_users` rather than in an app of its own. It has no models, and
`v1_visualization` already establishes the several-view-modules-per-app
pattern; a new app would mean an `INSTALLED_APPS` entry and an `apps.py` for
nothing. Keeping them in their own two files is what makes the unscoped
surface something a reviewer can hold in their head.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/tenants` | List, search, filter by state |
| `GET` | `/admin/tenants/summary` | Counts for every tenant, at a cost that does not grow |
| `GET` | `/admin/tenants/<id>` | Detail |
| `POST` | `/admin/tenants/<id>/deactivate` · `/activate` | Suspend / restore |
| `DELETE` | `/admin/tenants/<id>` | Soft-delete |
| `POST` | `/admin/tenants/<id>/rename` | Change subdomain |
| `GET` | `/admin/tenants/<id>/rename-impact` | Live breakage counts |
| `PUT` | `/admin/tenants/<id>/features` | Toggle entitlements |
| `GET` | `/admin/tenants/<id>/users` | Users in that tenant |
| `POST` | `/admin/users/<id>/deactivate` · `/activate` | Flip `is_active` |
| `GET`/`POST` | `/admin/operators` | List / invite |
| `DELETE` | `/admin/operators/<id>` | Revoke |

The counts are one annotated query, never N+1:

    Tenant.objects.annotate(
        users_count      = Count("users", distinct=True,
                                 filter=Q(users__deleted_at=None)),
        forms_count      = Count("forms", distinct=True,
                                 filter=Q(forms__deleted_at=None)),
        dashboards_count = Count("dashboards", distinct=True,
                                 filter=Q(dashboards__deleted_at=None)),
        datapoints_count = Count("forms__form_form_data", distinct=True,
                                 filter=Q(
                                     forms__form_form_data__deleted_at=None)),
        devices_count    = Count("users__mobile_assignments", distinct=True),
    )

The `_count` suffixes are not decoration: Django refuses an annotation whose
name collides with a field or reverse accessor, and `users`, `forms` and
`dashboards` are all reverse accessors on `Tenant`. The serializer sources the
plain names from them, so the wire format is unaffected.

The root-unit name needs a `prefetch_related` and must be filtered in Python.
A queryset filter on a related manager ignores the prefetch cache and issues
its own query, so `get_name` doing `.filter(parent=None)` would be one query
per workspace — the very N+1 the annotation exists to avoid.

**The endpoint is not a single query overall**, and no test should claim it
is: host resolution, JWT authentication and the `last_login` stamp each cost
one before the view is entered. What matters, and what is pinned, is that
adding a workspace adds nothing.

There is no delete endpoint for data or dashboards anywhere under `/admin/`.
The absence is the enforcement; no flag guards it.

Operator invitations reuse `send_activation_email` and the existing
`/register/activate` token flow — proving an address then setting a password is
the same problem as a user invitation. Revoking clears the flag and ends the
operator's sessions; it does not delete the account, because
`TenantInspection.operator` (MT-023) is a `PROTECT` FK, so a delete would
raise.

## Error handling

| Situation | Response |
|---|---|
| Non-operator on `/admin/*` | 403 |
| Workspace credentials on the admin host | 400, same message as the base domain |
| Operator credentials on a tenant host | 401 "Invalid login credentials" — `TenantAwareBackend` scopes to the host's tenant and a tenant-less account matches nothing |
| Request for a deactivated or deleted workspace host | 404 "Workspace not found" |
| Live JWT for a workspace suspended mid-session | 404 on the next request |
| Rename to a taken or reserved subdomain | 400 naming the field |
| Unknown key in a features payload | 400 listing the accepted keys |
| Unknown `state` in a tenant-list query | 400 listing the accepted states |
| Master-data directory rename fails | Logged; rename still succeeds, files regenerate lazily |

## Testing

The suite runs with `BASE_DOMAIN` unset, so every host-dependent test needs
`override_settings(BASE_DOMAIN="app.com")` and passes `HTTP_HOST=` to the
client, following `tests_login_host.py`. That the console is inert without a
base domain is itself worth a test.

New modules under `backend/api/v1/v1_users/tests/`, named `tests_*.py` per
repo convention, reusing `TenantTestHelperMixin.create_tenant` / `.bearer`:

- `tests_platform_admin_identity.py` — the flag defaults to false;
  `createplatformadmin` creates a tenant-less operator who is not a
  superadmin, and refuses a duplicate tenant-less address.
- `tests_platform_admin_host.py` — the admin host resolves to no tenant;
  registration refuses `admin`; everything is inert with `BASE_DOMAIN` unset;
  and a workspace that already holds the label locks that host for both sides
  without handing either one the other's powers.
- `tests_platform_admin_login.py` — an operator signs in on the admin host; a
  workspace account is refused there; an operator is refused on a tenant host.
- `tests_tenant_lifecycle.py` — a deactivated tenant 404s at the host, refuses
  login, and kills an already-issued JWT on its next request; the same for
  deleted; reactivation restores all of it.
- `tests_tenant_features.py` — `tenant_may_embed` follows the JSON column, and
  every flag has a label.
- `tests_admin_tenants.py` — the console lists workspaces the operator belongs
  to none of; a workspace user gets 403; deactivate, activate and soft-delete;
  an unknown feature key is a 400.
- `tests_admin_summary.py` — counts match hand-built fixtures across two
  tenants with overlapping shapes, soft-deleted rows excluded, and adding a
  workspace costs no extra query.
- `tests_admin_rename.py` — impact counts match fixtures; the regex and
  reserved words are enforced; a collision is a 400; the master-data directory
  moves, and a failure to move it still leaves the workspace usable.
- `tests_admin_users.py` — the listing is scoped to one workspace; deactivate
  and reactivate; an operator cannot be reached through it.
- `tests_admin_operators.py` — invite, revoke, no self-revoke, and the
  invitation links to the console rather than the base domain.

Outside `v1_users`:

- `api/v1/v1_mobile/tests/tests_deactivation_cascade.py` — deactivating a user
  fails `IsMobileAssignment` on the next device call; **soft-deleting one does
  too** (the §7 gap); reactivating restores sync.
- `app/src/lib/__test__/account-deactivated.test.js` — a refused device names
  the cause, stops polling, and says it once rather than every interval.

Two existing modules moved with the entitlement. `override_settings` against a
setting that no longer exists is still legal — Django simply adds it — so
every test that said `EMBED_TENANTS=...` would have gone on passing while
silently exercising an *unentitled* workspace. They now write the column
through one `set_embedding` helper.

Run with:

    ./dc.sh exec backend python manage.py test api.v1.v1_users
    ./dc.sh exec backend coverage run --rcfile=./.coveragerc \
        manage.py test --shuffle --parallel 4

## Task sequence

Each row is an independently testable commit. `→` marks its dependency.

| # | Task | Depends |
|---|---|---|
| 1 | `is_platform_admin` + migration, `IsPlatformAdmin`, `createplatformadmin` | — |
| 2 | `is_admin_host()`, `admin` reservation, middleware branch, `login()` relaxation | 1 |
| 3 | `Tenant.is_active`/`deleted_at`/`features` + migration; lifecycle filter in `resolve_tenant_from_host` | — |
| 4 | `FeatureFlags`, `tenant_may_embed` reads JSON, `EMBED_TENANTS` data migration, delete the setting | 3 |
| 5 | `admin_views.py` / `admin_serializers.py` in `v1_users`: tenant list, detail, deactivate/activate, soft-delete, features | 2, 3 |
| 6 | `GET /admin/tenants/summary`, single annotated query | 5 |
| 7 | Rename + `rename-impact` + master-data directory move | 4, 5 |
| 8 | Tenant user list, user deactivate/activate; `IsMobileAssignment` `deleted_at` fix | 5 |
| 9 | Operators: list, invite, revoke | 2 |
| 10 | Verify the mobile app surfaces "account deactivated" on a mid-sync 403 | 8 |

Task 4 must precede task 7: the rename is only safe once nothing is keyed by
the subdomain string.

## Risks

**`EMBED_TENANTS` must be migrated before it is deleted.** A deployment that
runs the migration without the setting present silently disables embedding for
every paying customer. Verify the data migration against production values
before release.

**Renaming has no undo.** The alias table is the mitigation that was not built.
If support tickets about broken devices follow the first rename, build it
before the second.

**`admin` may already be taken**, on a deployment that predates the
reservation. Nothing blocks it, and nothing needs to: the collision cannot be
escalated. The host resolves to that workspace, so the console's checks refuse
the operator and the workspace's own checks refuse its owner — both are locked
out of that one host, neither gains the other's powers, and every other
workspace is untouched. It is loud, local, and fixed by renaming the workspace.
`tests_platform_admin_host.AdminHostCollisionTestCase` pins all three
properties, because no guard does.

## Out of scope

- Reading a tenant's data or dashboards — MT-023.
- The console UI — MT-022.
- A subdomain alias table, a tenant purge command, per-tenant quotas or
  billing. `features` is an entitlement switch, not a plan model.
