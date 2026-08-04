# Two-phase registration with email verification: design

## Problem

The initial registration iteration shipped a deliberately simple flow: one
form (email, password, name, subdomain), no email verification, immediate
login, and a root administration unit named after the subdomain as a
placeholder. Two gaps surface once real onboarding matters:

1. No email verification. Anyone can claim a subdomain with a typo'd or
   throwaway address; there is no proof the registrant owns the email.
2. The root unit is a placeholder. It is named after the subdomain
   (`acme`), and nothing gives the tenant a clean, mandatory step to name
   their actual top unit ("Kenya"). This blocks bulk upload, whose template's
   level-0 column must reconcile with a properly named single root.

This iteration replaces the simple flow with a two-phase one: a light signup,
an email activation step, and a mandatory project-configuration form that
captures the tenant's identity and hierarchy names before the dashboard is
reachable. It is sequenced late, after tenant-scoping and level management,
so the per-tenant hierarchy and the manage-levels redirect target both exist.

## Decisions (from brainstorming)

- Two phases with verification between them. Phase 1 is a light form;
  an activation email gates phase 2, the configuration form; only a
  configured tenant reaches the dashboard.
- Create the hierarchy in phase 2, not phase 1. Level 0 and the root unit
  are created, already named, by the configuration form. There is never a
  placeholder root, which dissolves the bulk-upload reconciliation problem.
- `configured` is derived, not stored. It is computed as "this tenant has
  a `Levels` row at level 0 with a non-empty name and a root
  `Administration`." No new column, and it is the same predicate the
  bulk-upload gate uses. It requires the per-tenant hierarchy from
  tenant-scoping, hence the sequencing.
- Password is set in phase 1, before activation. The activation link only
  verifies the email; it does not set a password. This differs from the
  invitation flow, which sets the password *after* activation, and that flow
  is unchanged.
- The tenant and subdomain are claimed in phase 1. Creating the `Tenant` at
  signup locks the subdomain immediately, so two people cannot race for it
  during the email round-trip.

## State model

A registrant's `SystemUser` moves through three states, all expressible
without a new column:

| State | Signal | Can log in? | Reaches dashboard? |
|---|---|---|---|
| Unverified | `is_active = False` | No | No |
| Verified, unconfigured | `is_active = True`, tenant has no named level 0 | Yes | No, routed to config |
| Configured | tenant has a named level 0 + root | Yes | Yes |

`is_active` (Django's own field) carries verification. `configured` is
derived per tenant. An invited user (existing add-user flow) joins an
already-configured tenant and has a name from the invite, so they read as
configured and skip the config form entirely.

## Components

### 1. Phase 1: light registration (backend + frontend)

`POST /api/v1/register` is public. Payload: `email`, `password`, `subdomain`,
with no name yet.

One atomic transaction:

    Tenant(subdomain=…)
    SystemUser(email=…, is_superuser=True, is_active=False, tenant=…)

Then send an activation email containing a signed token
(`signing.dumps(user.pk)`, reusing the machinery the invite flow already
uses). The response is `200 {"message": "check your email"}` with no auth
token, because the user is inactive. Validation (unique email, unique
DNS-label subdomain, password validators) is unchanged from the simple flow.

Frontend `/register`: email, password, subdomain only; on success it shows a
"check your email" state rather than logging in.

### 2. Activation (backend + frontend)

`POST /api/v1/register/activate` takes payload `{"token": …}`. It verifies
the signed token (with a max age, say 7 days), sets `is_active = True`, and
returns an auth token plus the profile (with `configured: false`) so the
frontend can carry the now-active user straight into the config form.

`POST /api/v1/register/resend-activation` takes payload `{"email": …}`. It
re-sends the activation email if an inactive user with that email exists, and
always returns 200, never revealing whether the address is registered.

Frontend: an `/activate/:token` landing route calls activate, stores the
returned token, and redirects to `/configure`. An expired or invalid token
shows a message with a resend action.

### 3. Phase 2: project configuration (backend + frontend)

`POST /api/v1/register/configure` is authenticated, and permitted only for an
active, not-yet-configured superadmin. Payload: `first_name`, `last_name`,
`level_0_name`, `root_unit_name`.

One atomic transaction:

    user.first_name, user.last_name = …
    Levels(level=0, name=level_0_name, tenant=user.tenant)
    Administration(parent=None, level=<that level 0>,
                   name=root_unit_name, tenant=user.tenant)

After it, `configured` derives true. The endpoint returns the updated
profile. A second call once configured is rejected (409 or 400).

Frontend `/configure`: a mandatory form (first name, last name, level-0 name,
root-unit name) with inline help explaining what the level-0 name and root
unit are, examples included. On success, redirect to the manage-levels screen
so the tenant adds level 1 and beyond.

### 4. The dashboard gate

- Login (`POST /login`): `authenticate()` already rejects
  `is_active=False`, so an unverified user gets 401, surfaced as "please
  verify your email" with a resend affordance. An active user logs in
  normally, and the login response carries `configured`.
- `configured` on the profile and login response is a derived boolean, so the
  frontend knows where to route without inspecting the hierarchy itself.
- Frontend routing guard: an authenticated but not-`configured` user is
  redirected to `/configure` on any dashboard route, and cannot leave it until
  configured. A configured user is never sent there.

### 5. Invitation flow, unchanged

The existing add-user and invite path is untouched: invited users set their
password *after* clicking the invite link, receive a name at invite time, and
join a tenant that is already configured. They therefore read as configured,
skip `/configure`, and land on the dashboard as before. The password-timing
difference (registration before activation, invitation after) is intentional.

## Data flow

    POST /register {email, password, subdomain}
      → Tenant + SystemUser(is_active=False) → activation email → "check email"
    click activation link → POST /register/activate {token}
      → is_active=True → auth token, configured=false → /configure
    POST /register/configure {names, level_0_name, root_unit_name}
      → user named + Levels(0, named) + root Administration(named)
      → configured=true → redirect to manage-levels

## Error handling

- Phase 1: duplicate email or subdomain, malformed subdomain, and weak
  password each return 400 per-field. The transaction is atomic, so there is
  no partial tenant or user.
- Activation: an invalid or expired token returns 400 with a resend
  affordance; activating an already-active user is a no-op success.
- Configuration: a call by an unauthenticated or already-configured user
  returns 401 or 400; the hierarchy creation is atomic.
- Email delivery is a hard dependency for any signup. If Mailjet is
  unavailable, phase 1 still creates the inactive user so the subdomain is
  claimed, but the operator must be able to resend; deliverability is an
  operational concern to monitor.

## Testing

- Phase 1 creates an inactive user and a tenant, sends an activation
  email, and returns no auth token; a duplicate subdomain or email is rejected
  and creates nothing.
- Activation flips `is_active` on a valid token, rejects an expired one,
  and returns a usable auth token; resend re-sends for an inactive user and
  is a silent 200 for an unknown address.
- The gate: a verified-but-unconfigured user is routed to `/configure`
  and cannot reach the dashboard; login of an inactive user returns 401.
- Configuration names the user and creates a named level 0 and root for the
  tenant; `configured` then derives true; a second configure call is rejected.
- Per-tenant `configured`: two tenants configure independently, and one being
  configured does not mark the other configured.
- Invitation users are unaffected: configured tenant, name present,
  password set after activation, no `/configure` detour.
- Regression: the full suite passes; the auto-create gating from the
  earlier iteration still holds.

## Out of scope

- Rate limiting and CAPTCHA on signup, meaning abuse controls beyond
  verification.
- Subdomain routing and per-tenant URLs.
- Administration bulk-upload hardening, the next iteration, which consumes
  the cleanly named root this flow produces.
- Changing the invitation flow.
