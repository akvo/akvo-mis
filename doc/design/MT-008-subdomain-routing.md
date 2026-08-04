# Subdomain routing with host-bound tenant enforcement: design

## Problem

Every tenant already has a subdomain, chosen at registration, but nothing uses
it: the app is served on a single host and resolves the tenant purely from the
logged-in user. For a real multi-tenant SaaS, and as the foundation for a
future custom-domain subscription tier, the URL host should identify the
tenant, each tenant's app should live at its own subdomain, and a session
should be bound to the tenant whose host it was created on.

This iteration makes the subdomain real: resolve the tenant from the request
host, expose it as `request.tenant`, and enforce that an authenticated user's
tenant matches the host. It is defense in depth on top of `for_user`, which
still governs data, not a replacement for it.

## Infrastructure prerequisite

Subdomain routing cannot be exercised end to end without wildcard DNS
(`*.app.com`) and a wildcard TLS certificate for the base domain. These are
operational rather than code, and must be in place for production.

Local development uses `/etc/hosts` to simulate subdomains (see "Local
development" below), which mirrors the production host-based flow closely. A
header override survives only as a fallback for automated tests.

## Decisions (from brainstorming)

- Resolve, bind, enforce. The middleware resolves the tenant from the
  host, attaches `request.tenant`, and rejects an authenticated request whose
  user's tenant does not match the host tenant.
- The base domain signs up; the subdomain is the app. Registration and a
  "find your workspace" entry live on the bare base domain, where there is no
  tenant yet. Activation, login, and the dashboard live on the tenant's
  subdomain.
- A generic host-to-tenant resolver. One function maps a host to a tenant:
  subdomain lookup today, a custom-domain branch later. Nothing else parses
  hosts.
- Custom domains are later. Adding a nullable column later is as cheap as
  now; the expensive part is per-domain TLS provisioning and DNS-ownership
  verification, which is future subscription-tier work. The resolver is built
  to accept it without restructuring.
- Mismatch response: an API request gets 403; browser navigation is redirected
  to the user's own subdomain; an unknown host gets 404.
- Tenant-branded login needs a minimal public "tenant info by host"
  read (name and root only, no data) so the pre-login page can show which
  workspace it is.

## Components

### 1. Configuration

A `BASE_DOMAIN` setting (say `app.com`), read from the environment. A host is
"the base domain" when it equals `BASE_DOMAIN` (optionally `www.` plus
`BASE_DOMAIN`); otherwise its first label is a candidate subdomain.

### 2. Host-to-tenant resolver

    resolve_tenant_from_host(host) -> Tenant | None

- Strip a port and lower-case the host.
- If the host is the base domain, return `None` (tenant-less context).
- If the host is `<label>.BASE_DOMAIN`, return
  `Tenant.objects.filter(subdomain=<label>).first()`.
- Anything else, meaning an unknown or malformed host, returns `None`.

This is the single seam for custom domains: a later branch checks a
`Tenant.custom_domain` column before falling back to the subdomain rule. No
other code inspects the host.

### 3. Tenant-resolution middleware

Runs on every request:

- Sets `request.tenant = resolve_tenant_from_host(request.get_host())`.
- Test and CI override: when `DEBUG` (or an explicit `ALLOW_TENANT_HEADER`
  flag) is set, an `X-Tenant-Subdomain` request header overrides the host
  lookup. This exists for automated tests, since the Django test client cannot
  edit `/etc/hosts` and uses host `testserver`; interactive local development
  uses real hosts via `/etc/hosts` instead. It is ignored in production.
- Unknown host: if the host is not the base domain and resolves to no
  tenant, return 404 ("workspace not found") before the view runs.
- Enforcement: for an authenticated request on a tenant host, if
  `request.user.tenant_id != request.tenant.id`, return 403. Exempt are the
  base domain (`request.tenant is None`) and the public tenant-less endpoints:
  `register`, `register/activate`, `register/resend-activation`, `health`,
  `config.js`. `login` is subdomain-scoped, described below. The exemption
  list is explicit, not pattern-guessed.

Authentication note, specific to this stack: the project authenticates via DRF
simplejwt at the view layer, so `request.user` is `AnonymousUser` in Django
middleware for JWT API requests. The middleware therefore performs the
enforcement check by invoking simplejwt's
`JWTAuthentication().authenticate(request)` itself to obtain the user,
returning `None` for unauthenticated and public requests, which then bypass
enforcement. It does not rely on `request.user` being pre-populated. Host
*resolution* (`request.tenant`) needs no user and always runs; the
*enforcement* branch only runs when the JWT auth returns a user.

### 4. Login becomes subdomain-scoped and enforced

`POST /login` on a tenant host authenticates only users whose tenant matches
the host: after the normal credential check, reject with 401 a user whose
`tenant_id` differs from `request.tenant.id`, so a beta user cannot sign in at
`acme.app.com`. On the base domain, `login` is not offered, since the base
domain signs up and finds workspaces; a login POST to the base domain is
refused with a message to use the workspace URL.

### 5. Public tenant-info-by-host read

`GET /api/v1/tenant-info` is public, no auth. It returns, for
`request.tenant`, only `{ "subdomain": …, "name": <root unit name>,
"configured": bool }`, with no data, no user list, and nothing sensitive. It
drives the tenant-branded login page. On the base domain
(`request.tenant is None`) it returns 204 and an empty body so the
base-domain pages know they are tenant-less.

### 6. Frontend

Two contexts, distinguished by whether `tenant-info` resolves a tenant:

- Base domain (`app.com`): registration and a "find your workspace" form
  (enter subdomain, redirect to `<sub>.app.com`). A logged-in user who lands
  here is redirected to their own subdomain.
- Tenant subdomain (`acme.app.com`): a tenant-branded login (name from
  `tenant-info`), the activation landing, the configuration form, and the
  dashboard. While authenticated, if the host tenant differs from the user's
  tenant, the app redirects to the user's own subdomain rather than surfacing
  the 403.

The activation email links to the tenant's subdomain
(`<sub>.app.com/activate/<token>`), so activation and everything after happen
in the tenant's own context.

## Data flow

    app.com/register            → create tenant + inactive user (base domain)
    activation email → acme.app.com/activate/<token>
                                → activate on the tenant's own host
    acme.app.com/login          → tenant-branded; only acme users accepted
    acme.app.com/*  (authed)    → middleware binds request.tenant = acme,
                                  enforces user.tenant == acme (403 otherwise)
    beta-user hits acme.app.com → redirected to beta.app.com (browser) / 403 (API)
    unknown.app.com             → 404 workspace not found

## Error handling

- An unknown subdomain returns 404 before any view.
- An authenticated cross-tenant request returns 403 for the API, or a redirect
  in the browser.
- A cross-tenant login attempt returns 401 with a message to use the correct
  workspace.
- The base domain is always tenant-less; base-domain-only endpoints such as
  registration are exempt from enforcement.
- The dev header override is active only under `DEBUG` or the explicit flag, so
  production cannot be spoofed with `X-Tenant-Subdomain`.

## Local development

Local development simulates subdomains with `/etc/hosts`, so a developer's
flow matches production. This must be documented; a dev-setup doc and a
`CLAUDE.md` note are part of the implementation.

One-time setup:

- `.env`: `BASE_DOMAIN=localapp.test`. The base and every tenant subdomain
  share this base, and they must match, or the resolver cannot strip the base
  to find the subdomain.
- `/etc/hosts`: `127.0.0.1  localapp.test`.
- Django `ALLOWED_HOSTS` includes `.localapp.test`. Django's leading-dot form
  is a subdomain wildcard, so the backend needs no per-tenant change.
- Frontend dev server: disable the CRA host check for the custom host
  (`DANGEROUSLY_DISABLE_HOST_CHECK=true`, local only, or `allowedHosts`
  including `.localapp.test`), or the app will not load on a subdomain host.
- `setupProxy.js`: forward the browser's `Host` header to the backend, and do
  not rewrite it to the container host, so the middleware resolves the
  tenant from the real host.

Per-tenant step, the only repeated one, since `/etc/hosts` has no wildcard:

1. Open `http://localapp.test:3000` and register a tenant, say `new-tenant`.
2. Add `127.0.0.1  new-tenant.localapp.test` to `/etc/hosts`.
3. Open the activation link at
   `http://new-tenant.localapp.test:3000/activate/<token>`, configure, and use
   the app on that subdomain.

The port (`:3000`) is stripped by the resolver, so it does not affect tenant
resolution.

## Testing

- Resolver: the base domain returns None; `<sub>.base` returns the tenant; an
  unknown label returns None; port and case are handled.
- Middleware: sets `request.tenant`; an unknown host returns 404; an
  authenticated cross-tenant request returns 403; a same-tenant request passes;
  base-domain and exempt public endpoints bypass enforcement; the
  `X-Tenant-Subdomain` override works under `DEBUG` and is ignored otherwise.
- Login: a user signs in only on their own subdomain; a cross-subdomain
  attempt is 401; a base-domain login is refused.
- Tenant-info: returns only name, subdomain and configured for the host
  tenant; it is empty on the base domain and leaks no data.
- Frontend: the base domain renders register and find-workspace; a subdomain
  renders the branded login; an authenticated user on the wrong subdomain is
  redirected to their own.
- Regression: with `BASE_DOMAIN` unset or the middleware in a
  single-host or test mode, existing single-host behavior and the full suite
  are unaffected. The test client uses `testserver`, which must be treated as
  the base domain or bypass enforcement.

## Out of scope

- Custom domains. The resolver is ready for a `custom_domain` branch, but
  the column, DNS-ownership verification, and per-domain TLS provisioning are
  future subscription-tier work.
- Changing the data-isolation model. `for_user` still governs every query;
  host enforcement is an additional boundary, not a replacement.
- Wildcard DNS and TLS provisioning, an operational prerequisite rather than
  code.
