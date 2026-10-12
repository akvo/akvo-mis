# Tenant inspection and workspace switching: design

**Epic:** MT — Platform Admin Console (`epic/platform-admin-console`)
**Part 3 of 3.** Builds on MT-021 (operator identity, admin host, tenant
lifecycle) and MT-022 (the console UI).

## Problem

An operator can see that `acme` has 128,430 datapoints and five dashboards.
They cannot see *any* of it. The support case that motivated this epic — a
customer reports a dashboard that will not load, and it reproduces nowhere
else — is still unanswerable.

This part lets an operator read one workspace's data and dashboards through
the workspace's own application, read-only, and move between
workspaces without going back to the console.

It deliberately re-opens the boundary that MT-003, MT-004 and MT-010 built.
Those iterations were reviewed on the premise that `for_user()` is the only
way rows are scoped. **That premise still holds** — what follows changes what
`for_user()` *resolves to*, rather than bypassing it — but reviewers of those
iterations should read this document.

## Decisions

- **Inspection is a token that swaps the acting tenant**, not a bypass inside
  `for_user()` and not a parallel set of read-only endpoints.
- **The operator is given synthetic `is_superuser` while inspecting**, because
  swapping the tenant alone produces a crippled view. The cost is named below.
- **Read-only is enforced twice, independently**, in the middleware and in the
  authentication class — never in a permission class.
- **The hand-off is a one-time code**, not a token in a URL.
- **Lifetime reuses `ACCESS_TOKEN_LIFETIME`**; revocation is per-request.
- **No reason prompt.** Inspect is one click.
- **Switching workspaces is authorised by the inspection token itself**, via
  one endpoint on the tenant host.

## Components

### 1. Why not the two simpler shapes

A blanket `if user.is_platform_admin: return self.all()` inside `for_user()`
was rejected: every list endpoint would mix tenants with no way to tell rows
apart, pagination would stop meaning anything, and the bypass would apply to
writes as readily as reads.

Rebuilding read-only viewers under `/admin/` was rejected as the largest
frontend scope of the three. It duplicates `manage-data`, `DataDetail`,
`DashboardViewer` and the chart components, which then drift from the
originals — so the operator would be debugging a copy of the page the customer
is complaining about.

### 2. The inspection token

    # api/v1/v1_users/authentication.py  (new)
    class TenantInspectionToken(AccessToken):
        token_type = "tenant_inspection"
        lifetime   = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        # claims: operator_id, tenant_id

Registered in `AUTH_TOKEN_CLASSES` beside `MobileAssignmentToken`, which
established this pattern.

**`for_user()` is not modified at all.** The authentication class hands back a
doctored user and every scoping mechanism resolves from there:

    class InspectionAwareJWTAuthentication(AssignmentAwareJWTAuthentication):
        def get_user(self, validated_token):
            if not isinstance(validated_token, TenantInspectionToken):
                return super().get_user(validated_token)

            # Re-checked on every request: revoking an operator ends every
            # live inspection at once, which a token lifetime cannot do.
            operator = SystemUser.objects.filter(
                pk=validated_token["operator_id"],
                is_platform_admin=True,
                is_active=True,
                deleted_at=None,
            ).first()
            if operator is None:
                raise AuthenticationFailed("Operator access revoked")

            # In memory only, never saved. See below.
            operator.tenant = Tenant.objects.get(
                pk=validated_token["tenant_id"]
            )
            operator.is_superuser = True
            operator.is_inspecting = True
            return operator

The doctored attributes cannot reach the database. The only write path on the
request user is `UserActivity`, which re-fetches by pk and saves
`update_fields=["last_login"]`. `request.user.pk` is the operator's, so
`last_login` stamps the operator's own row — correct, and no guard is needed.

### 3. Why the synthetic `is_superuser`

Swapping the tenant is necessary and not sufficient, and the failure is quiet
enough to be worth stating.

An operator holds no `user_user_role` rows in the inspected tenant. With only
a tenant swap, `ability.js` falls to its `else if (user)` branch with
`roles = []` and grants `read data`, `manage form` and `manage control-center`
— no dashboards, no users, no master data, no form builder. On the backend,
`FeatureAccess`, `DashboardAccess` and `IsSuperAdminOrFormUser` all check
`is_superuser` *or* a role row, so those endpoints answer 403. The operator
would land in a crippled imitation of the customer's app: worse than useless
for support, because it looks right and behaves wrong.

**The named cost:** this is a synthetic state no real user holds. It can
surface combinations the customer's own staff never see, and it does not
literally satisfy "see what the tenant users see". The honest fix is user
impersonation — see *Out of scope*. When that lands, this decision is removed
rather than extended.

### 4. Read-only, enforced twice

The session now has workspace-owner authority. The only thing between
inspection and *acting as* the workspace owner is the write guard, so there
are two and neither relies on the other:

1. `TenantMiddleware` refuses any method outside `GET`/`HEAD`/`OPTIONS` on an
   inspection token, with 403, before any view runs.
2. `InspectionAwareJWTAuthentication.authenticate()` refuses the same, so a
   request reaching a view by a route the middleware did not cover still fails
   closed.

**The second guard is in the authentication class, not a permission class, and
that placement is the whole of its value.** This project does not set
`DEFAULT_PERMISSION_CLASSES`, and DRF's per-view `permission_classes`
*replaces* the default rather than composing with it — so a permission-class
guard would apply to no view that declares its own permissions, which is every
view in this codebase. Authentication runs for every DRF request regardless of
what the view declares, and cannot be switched off by adding an endpoint.

**The middleware's own copy must be swapped too.** `TenantMiddleware.__init__`
holds `self.jwt_auth = JWTAuthentication()` — the base class, which resolves a
user from a `user_id` claim. An inspection token has no such claim, so the
base class fails to authenticate it, returns `None`, and the middleware's
host-enforcement branch is skipped for exactly the sessions that most need
checking. It must use `InspectionAwareJWTAuthentication`.

This matters concretely because `TenantStampedSerializerMixin.create()` reads
`getattr(user, "tenant", None)` and would otherwise stamp new rows into the
*inspected* tenant. That path must be unreachable, not merely unlikely.

### 5. The hand-off

    POST /api/v1/admin/tenants/42/inspect        (admin host, no body)
      → TenantInspection row
      → {"code": "<single-use, 60s>"}

    browser opens https://acme.app.com/inspect?code=…

    POST /api/v1/inspect/exchange                (tenant host)
      → burns the code
      → Set-Cookie: AUTH_TOKEN=<inspection token>   host-only
      → redirect /control-center

A JWT in a query string lands in nginx access logs, browser history and any
`Referer` the page emits, and stays valid there for its whole lifetime. A
60-second single-use code bounds that to one use.

The cookie is set exactly as `login()` sets it — host-only, no `domain`
attribute — so the inspection session is confined to that tenant's origin, and
the operator's console session on `admin.<base>` is a separate cookie the
tenant host never sees. Because it is the same cookie the app already reads,
**the entire existing React app works unchanged**: no `sessionStorage`, no
axios interceptor, no special-casing.

There is no reason prompt. Inspecting is one click, and asking for a typed
justification on every support call buys a free-text field nobody reads at the
cost of friction on the most common action in the console.

### 6. The code store

    class TenantInspection(models.Model):
        operator     = FK(SystemUser, related_name="inspections")
        tenant       = FK(Tenant,     related_name="inspections")
        code_hash    = CharField(max_length=64, unique=True)
        code_used_at = DateTimeField(null=True)
        created_at   = DateTimeField(auto_now_add=True)

**Every column here is functional, and the model is not an audit feature.**
Nothing in the requirements asks who looked at what, and nothing in this epic
reads these rows once the code is burned.

The reason it is a table rather than a cache entry is that `CACHES` is
`FileBasedCache` at `/var/tmp/cache`, which is per-pod: the mint happens on
one request and the exchange on another, and with more than one replica the
second would miss. The reason it holds `operator` and `tenant` is that the
exchange receives nothing but a code and has to learn from somewhere which
token to build.

That the rows remain afterwards gives a forensic trail for free — "which of
our staff opened this workspace" is answerable with a query. Free is the
operative word: it is a byproduct, not a control, and no part of this design
should be justified by it. There is no endpoint that reads it and no screen
that shows it, deliberately.

No `reason` column, and no `expires_at`: the cookie's expiry comes from
`TenantInspectionToken.lifetime` at exchange time, and a second copy would be
one more thing to keep in step.

### 7. Lifetime and revocation

A short bespoke lifetime was specified at first and dropped. If re-minting is
one click — and with §8 it is — a short timer adds friction for the legitimate
operator and stops nobody, because anyone who can mint once can mint again.

The controls that actually bite are elsewhere:

- **Writes are refused server-side** (§4).
- **The operator's status is re-checked on every request** (§2). Revoking an
  operator ends every live inspection *immediately*, which no token lifetime
  can do. The cost is one indexed primary-key lookup per request.

Expiry still exists so a forgotten tab is not authenticated to a customer's
data indefinitely, and it reuses the 12 hours already configured in
`SIMPLE_JWT` rather than introducing a second number to justify.

### 8. Switching workspaces

The console and a tenant are different origins, so the tenant host cannot call
`/admin/*` with the operator's console cookie. Without help, moving from
tenant A to tenant B means: exit, return to the console tab, find B, open a new
tab — three steps across two origins, on the thing operators do most.

Instead, one endpoint on the *tenant* host, authorised by the inspection token,
which already carries `operator_id`:

    POST /api/v1/inspect/switch  {"tenant_id": 57}
      → re-verify the operator is still a platform admin (§2)
      → write a fresh code row
      → return a one-time code for the new tenant (§5)
      → the browser navigates to that tenant's /inspect

Same origin, so no CORS. Each switch writes its own code row, because each
needs its own one-time code.

A companion `GET /api/v1/inspect/tenants` returns the list for the dropdown,
authorised the same way, and **omits suspended and deleted workspaces** —
their hosts do not resolve, so offering them would be offering a dead link.

**The accepted trade:** the inspection token stops being a key to one workspace
and becomes a key to any. It remains read-only, remains re-authorised on every
switch, and dies the moment the operator is revoked — and an operator who can
already mint a code for any tenant from the console gains convenience rather
than authority. But a leaked inspection token reaches further than it
otherwise would.

### 9. Frontend

**Inspection adds exactly one element to the workspace's app: the banner.** No
console chrome wraps it, no alternate layout, no read-only variant of any page.
What the operator sees is the workspace's own `Header`, `Body`, menus and
components — both the point of the approach and what keeps it cheap.

    ┌──────────────────────────────────────────────────────────────┐
    │ ◉ Inspecting acme · read only · ends 02:14                  │
    │                        [ Switch workspace ▾ ] [ Exit ]       │
    ├──────────────────────────────────────────────────────────────┤
    │  (the workspace's own header, unchanged)                     │
    │  (the workspace's own pages, unchanged)                      │

`GET /profile` returns `is_inspecting: true` for such a session, and
`ability.js` gains one early branch:

    if (user?.is_inspecting) {
      can("read", "all");
      return build();
    }

Six lines, and every gated button in the app greys out. That is presentation
only — the server refuses the calls whether or not the browser tries them.

Mockup: [`MT-022-mockup/inspecting.html`](MT-022-mockup/inspecting.html),
which shows the banner and the open workspace switcher over the workspace's
own Manage Users page -- its real header, its real sidebar, its real table,
with the write control disabled.

The banner is a **new** component, `components/layout/InspectionBanner.jsx`.
The existing `components/layout/Banner.jsx` is not a general-purpose banner
despite the name — it is the landing page's countdown, gated on `pathname`
being `/`, `/not-found` or `/coming-soon`. Do not extend it.

New route `/inspect` on tenant hosts posts the code to `/inspect/exchange` and
redirects. The switcher dropdown reads `/inspect/tenants` and posts to
`/inspect/switch`.

`POST /inspect/switch` is itself a write, so both read-only guards must exempt
that one path **by name**. It is the single write an inspection session may
make, and it writes only a code row; exempting by an explicit path rather
than by inference means allowing a second write is a deliberate edit.

## Data flow

    console            admin.app.com   POST /admin/tenants/42/inspect
      │                                 → one-time code (60s)
      ▼
    acme.app.com/inspect?code=…       POST /inspect/exchange
      │                                 → burns code, sets AUTH_TOKEN
      ▼
    acme.app.com/control-center       the real app, read-only
      │
      │  banner ▾ "globex"         POST /inspect/switch {tenant_id}
      ▼                                 → re-verify operator, new code row,
    globex.app.com/inspect?code=…     new one-time code

## Error handling

| Situation | Response |
|---|---|
| Any write on an inspection token | 403, from the middleware, before the view |
| A write on a route the middleware missed | 403, from the authentication class |
| Code reused or older than 60s | 400, no cookie set |
| Operator revoked mid-session | 401 on the next request, from `get_user` |
| Switch to a suspended or deleted tenant | 404; it is not offered in the list either |
| Inspecting a tenant that is suspended while inspected | 404 at the host, per MT-021 §4 |

## Testing

New modules under `backend/api/v1/v1_users/tests/`, all with
`override_settings(BASE_DOMAIN="app.com")`.

**The test that matters most** — `tests_inspection_read_only.py`. Parametrised
over `POST`/`PUT`/`PATCH`/`DELETE` against a representative sample of tenant
endpoints, asserting both 403 *and* that no row was created or modified. The
second half is the point: a 403 from the wrong layer with a row already
written would pass a status-only assertion.

The two guards must also be tested **apart**. A test exercising them together
proves nothing about either, and the reason there are two is that one may be
bypassed. So the same cases run once with `TenantMiddleware` removed from
`MIDDLEWARE`, asserting the authentication layer alone still refuses every
write.

- `tests_inspection_handoff.py` — a code works once and is refused the second
  time; a code older than 60 seconds is refused; the cookie is host-only.
- `tests_inspection_scope.py` — an inspection session reads exactly one
  tenant's rows and never another's; the summary counts it sees match that
  tenant; `is_inspecting` appears on `/profile`.
- `tests_inspection_revocation.py` — revoking the operator makes the next
  request 401; deactivating them does too.
- `tests_inspection_switch.py` — a switch writes a new code row, the old code
  stays burned, a suspended tenant is refused and absent from
  `/inspect/tenants`.

Frontend, following the existing `__test__` conventions:

- `components/can/__test__/ability.test.js` — an `is_inspecting` user can read
  and cannot create, edit, delete or upload.
- `pages/inspect/__test__/Inspect.test.js` — posts the code, redirects on
  success, shows an error and does not redirect on 400.
- `components/layout/__test__/InspectionBanner.test.js` — renders the
  workspace name and expiry; the switcher lists tenants and excludes
  suspended ones.

Run with:

    ./dc.sh exec backend python manage.py test api.v1.v1_users
    ./dc.sh exec frontend npm test

## Task sequence

| # | Task | Depends |
|---|---|---|
| 1 | `TenantInspectionToken`, `TenantInspection` model + migration, mint + one-time-code exchange | MT-021 §8 |
| 2 | `InspectionAwareJWTAuthentication`, middleware read-only guard, middleware auth-class swap, `is_inspecting` on `/profile` | 1 |
| 3 | `/inspect/switch`, `/inspect/tenants` | 2 |
| 4 | `/inspect` exchange route, `ability.js` read-only branch, inspection banner | 2, MT-022 §2 |
| 5 | Banner workspace switcher | 3, 4 |

Tasks 1 and 2 are one reviewable unit in spirit but split because the
read-only guard deserves its own gate — it is the control everything else
rests on.

## Risks

**This is the largest blast radius in the epic.** The synthetic `is_superuser`
grants workspace-owner authority to a session whose only restraint is the
write guard. Treat any third path to a write as a release blocker.

**A leaked inspection token reaches every workspace** (§8), not one. Bounded
by read-only, by per-request re-verification, and by the operator's own
account lifecycle.

**Reviewers of MT-003, MT-004 and MT-010 should read this document.** The
isolation premise is intact but the mechanism now has a deliberate second
entry point.

## Out of scope

**User impersonation.** The intent behind this feature is that an operator
sees what a tenant's *users* see, and that a future feature lets them
reproduce a bug that happens only to one person. §3 does not deliver that: it
gives a workspace-owner view, a synthetic state no real user holds.

The seam is one branch, and naming it now means whoever builds it does not
have to re-derive this design. `TenantInspectionToken` gains an `as_user_id`
claim, and `InspectionAwareJWTAuthentication.get_user` returns *that user* — a
real `SystemUser`, loaded through `objects_with_deleted` so a deactivated or
soft-deleted account can be inspected, which is exactly when one would want
to. Every scoping mechanism then resolves correctly with no further change:
`for_user`, `ability.js`, `FeatureAccess`, `user_form`, the administration
dropdown's role-level logic, approval trees. §3 is deleted rather than
extended.

Two things that version must handle and this one does not: `UserActivity`
would stamp `last_login` on the *impersonated* user and must be skipped for
inspecting sessions; and the banner must name the person being impersonated
and their state.

**Notifying a customer when their workspace is inspected.** The
`TenantInspection` table supports it; whether to send the email is a
commercial decision, not a technical one.
