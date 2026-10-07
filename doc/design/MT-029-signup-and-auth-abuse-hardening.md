# Sign-up and auth abuse hardening: design

**Epic:** MT — Multi-tenancy
**Issue:** [#525](https://github.com/akvo/akvo-mis/issues/525)
**Branch:** `feature/525-signup-auth-abuse-hardening`
**Builds on:** MT-006 (two-phase registration, which introduced
`register` and `RegisterSerializer`), MT-008 (subdomain routing, which
introduced `BASE_DOMAIN` and `is_base_domain`), the uninitiated-tenant
purge (#507) and the workspace name blacklist (#511).

This is pre-launch hardening. No abuse has been observed.

## Problem

`POST /api/v1/register` is unauthenticated, public, and does three
expensive things per call (`backend/api/v1/v1_users/views.py`): it
creates a `Tenant`, claiming a subdomain out of a global namespace; it
creates a superadmin `SystemUser`; and it sends an email synchronously,
inside the request.

Nothing limits how often anyone may do that. The same is true of the
three sibling endpoints on the same public surface —
`register/resend-activation`, `login`, and `user/forgot-password`. All
four are plain `@api_view(["POST"])` with no `throttle_classes`, and
`REST_FRAMEWORK` in `backend/mis/settings.py` sets no defaults, so
every one of them will serve an unbounded request rate to an anonymous
caller.

**Outbound email is the largest exposure.** `send_email`
(`backend/utils/email_helper.py`) runs in the request thread and
swallows every exception. Three of the four endpoints call it. An
unthrottled caller therefore has a free, anonymous SMTP relay through
our own credentials, pointed at any address they like. The cost is
sender reputation, which is slow to build, slow to repair, and relied on
by every transactional mail the platform sends. It also ties up a worker
on an SMTP round-trip per request, on a deployment that runs exactly one
backend pod.

**The subdomain namespace is scarce and global.** This is the premise
MT-028 rests on: a workspace's subdomain *is* its name, claimed
first-come on a free tier. A script can burn every good short name in
an afternoon. The #507 purge reclaims names from sign-ups that never
activate, which bounds the damage in time but does not prevent the land
grab, and does nothing about names that *are* activated by a throwaway
mailbox.

**Credential stuffing has no speed limit.** `login` will check as many
email/password pairs per second as the pod can serve.

**`register` has no server-side host gate.** `frontend/src/App.js`
renders the route only on the base-domain host, and that is the only
gate — the view itself checks nothing. On a single-host deployment
(`BASE_DOMAIN` unset, which is how `mohhs-mis` and `unicef-fsm` run),
an unauthenticated POST still creates a tenant and a superuser on a
deployment whose operator never turned sign-up on.

That last one reads worse than it is, so it is worth bounding
precisely. It is not a data-disclosure bug: `for_user`
(`backend/utils/tenant_scoped_model.py`) filters on the requesting
user's own tenant, so a self-registered account on a single-host
deployment sees only its own empty workspace. What it gets an attacker
is unauthenticated row creation, superuser rows in a database nobody
expected them in, and the email relay above.

## Decisions

**Four controls, all in the application**, so they behave the same on
SaaS, single-host and local-dev deployments and can be exercised by the
test suite: resolve the real client address so a per-IP throttle
keys on something meaningful; give throttle counters a cache nothing
else clears; throttle the four endpoints per IP *and* per submitted
email; verify a Cloudflare Turnstile token at `register`, wired now and
switched off until launch. Plus the host gate, which is a correctness
fix rather than a rate control.

**Not the Next.js shape.** The original proposal was to rebuild the
frontend on Next.js so that reCAPTCHA could run client-side with the
`register` call moved server-side and the backend IP-whitelisted to the
frontend server.

The captcha half never needed Next.js. A site key is public by design
and its token is verified by a server-to-server call; that server can
be Django exactly as easily as a route handler. The site key even has
an existing delivery channel — `appConfig` in `config.js`.

The IP-whitelisting half does not do what it appears to. A bot does not
call `/api/v1/register`; it calls whatever public route the browser
calls, which then calls the backend *from the whitelisted address*.
Whitelisting changes which address the traffic arrives from and refuses
none of it. The only control actually refusing the bot in that design is
the captcha verification, which we can have without the rewrite. It also
costs something real: with every request arriving from one address,
per-IP throttling stops working unless the client address is
deliberately re-forwarded and re-trusted — which is the problem in
Component 1, reintroduced on purpose.

**Turnstile rather than reCAPTCHA.** No Google account coupling, no
consent-banner question for a platform NGOs put their name on, free at
this scale, and the same verify-the-token-server-side shape.

**Cloud Armor shapes volume and cannot express sign-up policy.** The
GKE `BackendConfig` already exists in both environments
and carries no `securityPolicy`; adding edge rate limiting is one field
plus a `gcloud compute security-policies` rule. It cannot key on an
email address, it does nothing in local dev, the test suite or
single-host deployments, it lives on a separate release cycle from the
code it protects, and it bills per policy and per request. The sign-up
rules we want belong in Django. See *Out of scope*.

## Components

### 1. Client address resolution

`REST_FRAMEWORK["NUM_PROXIES"]`, read from a `NUM_PROXIES` environment
variable, defaulting to 0, and set to 2 in both k8s secrets.

The deployed request path is GCLB (GCE Ingress) → `frontend` Service
(NodePort) → nginx pod → `backend` Service → backend pod. The
manifests live in `akvo-config/k8s-manifests/{test,production}/akvo-mis/`;
the `deploy/docker-compose.app.yml` in this repository is not used by
any environment.

The GCLB is an L7 proxy that appends *both* the client address and its
own, producing:

    X-Forwarded-For: [<client-supplied>, ]<client-ip>, <GFE-ip>

nginx never sets `X-Forwarded-For` (`frontend/nginx/conf.d/default.conf`
sets `Host`, `X-Real-IP` and `X-Forwarded-Host` only) and unmodified
request headers are proxied through, so Django receives that header
intact. The client address is the second entry from the right.

DRF indexes from the right, which is what makes this safe:

    if num_proxies is not None:
        if num_proxies == 0 or xff is None:
            return remote_addr
        addrs = xff.split(',')
        client_addr = addrs[-min(num_proxies, len(addrs))]
        return client_addr.strip()

    return ''.join(xff.split()) if xff else remote_addr

A caller may prepend anything to `X-Forwarded-For` and the GCLB
preserves it, so the *leftmost* entry is attacker-controlled. Counting
from the right steps over that. This is also why neither the header nor
`X-Real-IP` should be parsed by hand anywhere in this codebase. DRF's
`BaseThrottle.get_ident` is the single reader, and `RegisterSerializer`
calls it too so the captcha and the throttles cannot disagree about who
the caller is.

**The default of 0 matters more than the 2.** `num_proxies == 0`
returns `REMOTE_ADDR`, which is correct wherever nothing trustworthy
sets the header. Leaving the setting unset is *not* equivalent: DRF
then falls through to `''.join(xff.split())` — the entire header,
attacker-supplied prefix included — as the throttle key, so a bot gets
free key rotation by varying a header. A non-zero default is worse
still. Note the `min(num_proxies, len(addrs))` clamp: with
`NUM_PROXIES=2` and a one-entry header the index collapses to
`addrs[-1]`, which is then whatever the client sent. On local dev and
single-host deployments, where nothing strips or appends, a default of
2 would hand a bot exactly the rotation this is meant to deny, which is
why the value is set in the manifests and not in the code.

`X-Real-IP` is deliberately left alone. It is set from `$remote_addr`,
which at the nginx pod is the node or GFE address; it is wrong, nothing
reads it, and fixing it properly needs `ngx_http_realip_module`
configured with `set_real_ip_from` over Google's published front-end
ranges.

### 2. Throttle storage

A `throttle` alias in `CACHES`, a `FileBasedCache` at
`/var/tmp/cache-throttle`, with the throttle base classes pointed at it.

Counters must not live in `default`, because `v1_forms.signals` clears
`default` wholesale on any form change, and a budget that resets
whenever an admin edits a form is not a budget. This is the same
reasoning, and the same remedy, as the existing `embed` alias, whose
comment asks unrelated callers to do exactly this.

Under `TESTING` the alias becomes a `LocMemCache`. A file-based cache
shared between `manage.py test --parallel 4` processes is the
cross-process race the `embed` comment describes, and throttle counters
are more sensitive to it than cached previews: one worker spending
another's budget fails tests by shuffle order.

**Stated assumption: one pod.** Both environments run the backend at
`replicas: 1` with the HorizontalPodAutoscaler pinned
`minReplicas: 1, maxReplicas: 1`, so a pod-local cache is globally
consistent. Nothing in the code states this, and nothing checks
it. Raising `maxReplicas` multiplies every limit below by the replica
count, silently, with no test failing. If the backend is ever scaled
out, the throttle cache must move to a shared backend in the same
change.

### 3. The throttles

`backend/utils/throttling.py`, four `SimpleRateThrottle` subclasses
following the shape `DashboardAIThrottle` already established in
`v1_visualization/dashboard_builder_views.py`.

| scope | keyed on | default rate |
|---|---|---|
| `email_dispatch_ip` | client address | `10/hour` |
| `email_dispatch_email` | submitted email, lowercased and hashed | `3/hour` |
| `login_ip` | client address | `60/hour` |
| `login_email` | submitted email, lowercased and hashed | `10/hour` |

`register`, `register/resend-activation` and `user/forgot-password`
each carry both `email_dispatch_*` throttles; `login` carries both
`login_*`. Rates sit in `DEFAULT_THROTTLE_RATES`, each read from an
environment variable, because they are pre-launch guesses and a limit
that bites a real user should be a secret change rather than a release.

These subclass `SimpleRateThrottle` rather than `AnonRateThrottle` on
purpose: `AnonRateThrottle` exempts authenticated callers, and an
authenticated caller hammering `forgot-password` is exactly as
expensive as an anonymous one.

**Why per-email as well as per-IP.** A per-IP limit alone is defeated
by any residential-proxy pool, and those are cheap. A per-email limit
protects the thing worth protecting when mail is involved — one mailbox
from being flooded, and our sending reputation from being spent — but
it is keyed on something the caller chooses, so it cannot stand alone
either.

The email key is read from `request.data` before validation, because
throttles run before the serializer. It may therefore be any string the
caller sent; a nonsense key throttles a nonsense caller. The address is
hashed so that no mailbox reaches a cache dump, a traceback, or a cache
file name, and a body that is not a JSON object yields no key rather
than raising — a bare list would otherwise answer a malformed request
with a 500.

**Why four scopes and not eight.** `register`, `resend-activation` and
`forgot-password` share one pair. They are not the same flow, but each
sends a mail, which is the exposure being closed, and one pair is half
the configuration to tune. The cost: somebody who signs
up and then resends the activation mail twice has spent their
three-per-hour budget and cannot request a password reset until the
hour rolls over. At these rates few registrants will reach
it, and splitting the scopes later is a settings change and two class
attributes.

**Why `login_ip` is loose and `login_email` is tight.** An entire
office arrives from one NAT address, so a tight per-IP login limit
locks out a customer. `60/hour` is useless as a stuffing budget per
address while staying out of a shared office line's way; the real limit
is the `10/hour` per email.

**Why `3/hour` is not lower.** A sufficiently tight per-email
limit on `forgot-password` is itself an attack: it lets anyone who
knows an address deny its owner password recovery. Three an hour is
above any legitimate need and leaves a recovering user a path even
while being targeted.

### 4. Turnstile

Two settings, both from env: `TURNSTILE_SITE_KEY` and
`TURNSTILE_SECRET`. An empty secret means the control is off, which is
how it ships.

The site key joins `appConfig` in
`backend/api/v1/v1_data/management/commands/generate_config.py`, beside
`baseDomain`. `Register.jsx` renders the widget only when the key is
present, injecting Cloudflare's script from that component on mount —
not from `public/index.html`, which would pull third-party JavaScript
into every page of every workspace to serve one form on the base
domain. There is no npm dependency; the widget is a script and a div.

`RegisterSerializer` gains an optional write-only `captcha_token`.
When `TURNSTILE_SECRET` is set, `validate()` posts the token, the
secret and the client address to Cloudflare's `siteverify` and refuses
the registration on a negative verdict, keyed to `captcha_token`.

**Enabling is two steps, in order.** `/config.js` is proxy-cached by
nginx for a day (`proxy_cache_valid 200 206 1d`), so a browser can hold
a config with no site key for up to 24 hours after one is set. Set
`TURNSTILE_SITE_KEY` first and let the cache turn over, which starts
clients sending tokens; set `TURNSTILE_SECRET` afterwards, which starts
the backend requiring them. Both together opens a window of up to a day
in which the backend rejects every registrant whose cached bootstrap
script cannot produce a token.

**Fail open on a verification outage.** If the `siteverify` call errors
or times out, the registration proceeds and the failure is captured to
Sentry. Pre-launch, with no observed abuse, a Cloudflare outage closing
the sign-up form entirely is the worse outcome. The decision is
revisable: inverting it is one `return None`, written out rather than
folded into the `try` block so that the next reader can find it. The
call takes an explicit short timeout; without one it would hang on the
single backend pod, inside a request already holding a synchronous SMTP
connection.

`requests` is declared in `backend/requirements.txt` as part of this
work. It was already arriving transitively and two modules already
imported it.

### 5. The sign-up gate

Two checks at the top of `register`: `settings.SIGNUP_ENABLED`, and
`is_base_domain(request.get_host())`.

`SIGNUP_ENABLED` is a three-state setting defaulting to
`bool(BASE_DOMAIN)`. The default is what fixes the finding without
anyone editing a manifest: `mohhs-mis` and `unicef-fsm` run with
`BASE_DOMAIN` unset, so they go from silently accepting self-service
sign-ups to refusing them, which is what their operators would already
have assumed. The SaaS deployments set `BASE_DOMAIN` and are
unaffected, and an explicit `false` can still turn sign-up off on one.

It is an explicit setting rather than a bare `if BASE_DOMAIN` in the
view because local development commonly runs with `BASE_DOMAIN` unset
and the `/register` form is reachable there. Without an override the
form would render and the endpoint would refuse it, which is a
confusing afternoon; `SIGNUP_ENABLED=true` is documented in
`env.example`, the file a developer already copies.

It is also forced `True` under `manage.py test`, because `BASE_DOMAIN`
is forced empty there and the default would otherwise turn every
existing registration test into a 403.

## API contract

No new endpoints and no model changes. Four endpoints gain refusals.

| Method | URL | New responses |
|---|---|---|
| POST | `/api/v1/register` | 403 gate, 429 throttle, 400 captcha |
| POST | `/api/v1/register/resend-activation` | 429 throttle |
| POST | `/api/v1/login` | 429 throttle |
| POST | `/api/v1/user/forgot-password` | 429 throttle |

`register` accepts one new optional field:

```json
// POST /api/v1/register
{
  "email": "founder@acme.org",
  "password": "...",
  "subdomain": "acme",
  "language": "en",
  "captcha_token": "<Turnstile token, when a site key is configured>"
}
```

Refusals:

```json
// 403 -- sign-up not offered on this deployment or this host
{ "message": "Self-service sign-up is not available here" }

// 400 -- captcha required or rejected
{
  "message": "...",
  "details": { "captcha_token": ["Please complete the verification challenge."] }
}
```

A throttled request gets DRF's standard 429 with a `Retry-After`
header.

### Configuration

| Variable | Default | Deployed |
|---|---|---|
| `NUM_PROXIES` | `0` | `2` (both environments) |
| `SIGNUP_ENABLED` | follows `BASE_DOMAIN` | unset |
| `TURNSTILE_SITE_KEY` | empty | empty, then set at launch |
| `TURNSTILE_SECRET` | empty | empty, then set after the site key |
| `THROTTLE_EMAIL_DISPATCH_IP` | `10/hour` | unset |
| `THROTTLE_EMAIL_DISPATCH_EMAIL` | `3/hour` | unset |
| `THROTTLE_LOGIN_IP` | `60/hour` | unset |
| `THROTTLE_LOGIN_EMAIL` | `10/hour` | unset |

`SIGNUP_ENABLED` is deliberately absent from the manifests: both SaaS
deployments set `BASE_DOMAIN`, so the default already resolves to on,
and an explicit entry would be a second place for the same fact to be
stated and to drift.

## Error handling

A refused sign-up is 403, not 404. Whether a deployment offers
self-service sign-up is observable from its front page, so there is no
secret to keep, and a 404 on a route that exists sends the next
debugger hunting for a routing bug. The 404 that a workspace host
already returns for an unknown subdomain comes from `TenantMiddleware`
and means something different; the two are pinned apart by tests.

A captcha failure is shown under the widget, not in a toast. It
does not travel through `FORM_FIELDS` to get there: that list drives
`form.setFields`, which needs a registered antd field, and the control
here is Cloudflare's iframe rather than an `Input` — a `Form.Item` with
a `name` injects `value`/`onChange` into its only child, which on a
plain `div` means unknown props on a DOM node. So the message is held
in component state and rendered through the item's `help`, and it is
removed from `details` before the field mapping runs so that it cannot
also raise a toast.

The widget is reset on any 400, not only a captcha one. A Turnstile
token is single-use, so somebody who merely mistyped their email would
otherwise be left holding a spent token and unable to submit again.

An unparseable request body stays a 400. The email throttle is the
first thing to touch `request.data`, which is where parsing happens;
catching `ParseError` there would answer a malformed body with a silent
success instead of the 400 DRF already gives it.

## Testing

Unit tests on the throttle classes, in
`backend/api/v1/v1_users/tests/tests_throttling.py`: what the key is,
since a wrong key is invisible from a 200. Some of them
synthesize `X-Forwarded-For` as the GCLB builds it and assert that two
client addresses get separate budgets while a client-supplied prefix
cannot move the key. `NUM_PROXIES` is otherwise an unexplained integer
in a settings file, and that test is what fails if somebody tidies it.

Endpoint tests that each limit is actually wired, which is what catches
a decorator never added or added in the wrong order. Rates are patched
on the throttle class rather than through `override_settings`, because
DRF binds `SimpleRateThrottle.THROTTLE_RATES` to
`api_settings.DEFAULT_THROTTLE_RATES` in its own class body at import
time and `override_settings` cannot reach it.

Rates are `None` under `manage.py test`, which is what keeps the rest
of the suite green: every Django test request arrives from `127.0.0.1`
and the cache is process-wide, so live rates would fail unrelated
endpoint tests by call count and by shuffle order. One test asserts
that inertness directly, so the next person to change it learns from
one clear failure instead of a scatter of unrelated ones.

Turnstile tests mock `siteverify` for a positive verdict, a negative
verdict, a no-token-while-enabled case — the stale-`config.js` window,
which must be a 400 on the field rather than a 500 from posting `None`
upstream — and a network error that passes while capturing to Sentry.
One asserts that with the secret empty, no outbound call is made at
all.

Gate tests for the base domain, an existing workspace host, an unknown
workspace host (404 from the middleware, not 403 from the gate), and
the `TESTING` default.

Frontend tests in `Register.test.js`: no widget without a site key, a
widget with one, and a `captcha_token` error rendered under it.

The full suite runs `--shuffle --parallel 4`. Both flags matter here:
they are what would expose a throttle counter leaking between tests or
between workers.

## Task sequence

Six tasks, each ending in a test run. Task 1 changes no endpoint
behaviour, so the `NUM_PROXIES` reasoning can be reviewed on its own
before anything depends on it.

1. **Throttle plumbing.** The `throttle` cache alias, `NUM_PROXIES` and
   `DEFAULT_THROTTLE_RATES` in `backend/mis/settings.py`; a new
   `backend/utils/throttling.py`; the variables in `env.example`; unit
   tests in `backend/api/v1/v1_users/tests/tests_throttling.py`.
2. **Apply the throttles.** Four `@throttle_classes` decorators in
   `backend/api/v1/v1_users/views.py`, plus endpoint tests. The whole
   `v1_users` suite is re-run here: every Django test request arrives
   from `127.0.0.1`, so if the rates were not inert under `TESTING`
   this is where it shows.
3. **The sign-up gate.** `SIGNUP_ENABLED` in settings, the two checks
   in `register`, `env.example`, and tests appended to
   `tests_register.py`.
4. **Turnstile verification, switched off.** `requests` in
   `backend/requirements.txt`; the four settings; a new
   `backend/utils/turnstile.py`; `captcha_token` and its check in
   `RegisterSerializer`; the serializer's request context in
   `register`; tests in `tests_turnstile.py`.
5. **The Turnstile widget.** `turnstileSiteKey` in `generate_config.py`
   and its `test_config_js.py` assertion; the widget, the token and the
   error slot in `frontend/src/pages/register/Register.jsx`, with
   `Register.test.js`.
6. **The deployment variables**, in `akvo-config` — a separate
   repository and a separate pull request. `num-proxies: "2"` and the
   two empty Turnstile keys in `3-secrets.yml`, and the matching
   `optional: true` env entries in `8-deployment-backend.yml`, for both
   `test` and `production`. Nothing above takes effect in staging or
   production until it lands: `NUM_PROXIES` stays 0 and every caller
   shares one rate-limit bucket.

`SIGNUP_ENABLED` is deliberately left out of task 6, for the reason
given under *Configuration*.

## Risks

**`NUM_PROXIES` is correct only for the current proxy chain.** Putting
Cloudflare, another load balancer, or a service mesh in front of the
GCLB changes the arithmetic, and it fails silently: every client shares one
bucket, or each client gets a fresh one per request. The client-address
keying test is what makes that visible, and it is the first thing to
re-read if the ingress changes.

**Scaling the backend out silently multiplies every limit** by the
replica count, because the throttle cache is pod-local. See Component 2.

**The captcha's two-step enable can be done backwards**, breaking
sign-up for up to a day. Nothing in the code prevents it; the ordering
is documented in `env.example` and in the settings comment.

**The throttles are live from the moment this ships**, with the captcha
off. A legitimate flow that exceeds them — a demo day where one person
registers several workspaces from one address, a training session doing
bulk password resets — surfaces as a 429. The rates are env overrides
for exactly that reason.

**Single-host deployments lose self-service sign-up on deploy.** That
is the intent, and it is a behaviour change on a live system:
`mohhs-mis` and `unicef-fsm` should be confirmed as not relying on it
before this ships.

## Out of scope

**nginx `limit_req`.** Worth having eventually as the layer that
refuses a flood before it reaches a Django worker. Keying it on
anything trustworthy requires `ngx_http_realip_module` with
`set_real_ip_from` over Google's front-end ranges; keying it on raw
`$http_x_forwarded_for` would key on the attacker-controlled leftmost
entry, and a rate limit a bot bypasses by setting a header is worse
than none because it looks like protection.

**Cloud Armor.** See *Decisions*. One field on the existing
`BackendConfig` when there is traffic worth shaping.

**`timeoutSec: 84600` and synchronous SMTP.** The `BackendConfig`
gives a request ~23.5 hours before the load balancer intervenes, and
`send_email` holds an SMTP connection inside the request on a
single-pod deployment, so a hung mail server occupies a worker with no
backstop. Same exposure as this work, different change: moving
transactional mail onto the existing django-q worker.

**Email enumeration on `forgot-password`.**
`ForgotPasswordSerializer.validate_email` raises
`"Invalid email, user not found"` when no account matches, which
confirms whether an address is registered. `resend-activation` was
deliberately built the other way round, and `FindWorkspace` carries a
comment explaining why it avoids the same oracle. Rate limiting makes
harvesting slower but does not close it. Noted here rather than fixed,
because changing it changes an existing contract and its tests.

**Disposable-email-domain refusal at sign-up.** Cheap, and aimed
squarely at sign-up abuse, but it is a name-policy question of the kind
MT-028's `self_service_reason` already answers and belongs with that
machinery.

**`register/activate` and `user/set-password`.** Both consume
`signing.dumps` tokens, unguessable without `DJANGO_SECRET`. A rate
limit buys nothing.

**`find-workspace`.** Nothing to harden: it is client-side navigation
only, with no endpoint behind it, built that way deliberately so that
an anonymous visitor cannot enumerate customers.

## References

- Prior art: `doc/design/MT-006-two-phase-registration.md`,
  `doc/design/MT-008-subdomain-routing.md`
- Deployment manifests: `akvo-config/k8s-manifests/{test,production}/akvo-mis/`
- [Cloudflare Turnstile server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
- [GCLB `X-Forwarded-For` handling](https://cloud.google.com/load-balancing/docs/https#target-proxies)
