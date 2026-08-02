# Running subdomain routing locally

Each workspace lives at its own host — `acme.app.com` — and a session is
only valid on the host of the workspace it belongs to. In production that
needs wildcard DNS and a wildcard TLS certificate for the base domain,
which are operational, not code. Locally, `/etc/hosts` stands in for the
wildcard, and the flow you get is the same one production has.

None of this is on by default. With `BASE_DOMAIN` empty every host is the
base domain, nothing resolves to a workspace, and the app behaves exactly
as it did before subdomain routing existed. Turn it on only when you are
working on it.

## One-time setup

**1. Pick a base domain and use it everywhere.** In `.env`:

    BASE_DOMAIN=localapp.test

Use a name you do not own on the real internet. `.test` is reserved for
exactly this by RFC 2606, so it can never collide with a live domain.

**2. Add the base domain to `/etc/hosts`:**

    127.0.0.1  localapp.test

**3. Restart the stack** so the backend and worker pick up the new
variable, and the frontend picks up the base domain baked into
`config.js`:

    ./dc.sh up -d --force-recreate backend worker frontend

Now `http://localapp.test:3000` is the main site: registration and a
find-workspace field, no login.

## Per workspace

`/etc/hosts` has no wildcard, so each workspace you register needs its own
line. This is the only repeated step.

1. Open `http://localapp.test:3000/register` and create a workspace, say
   `new-tenant`.
2. Add its host:

       127.0.0.1  new-tenant.localapp.test

3. Read the activation email at http://localhost:8025 (Mailpit). Its link
   already points at `http://new-tenant.localapp.test:3000/activate/...`,
   because activation hands back a session and that session is only valid
   there.
4. Follow the link, fill in the configuration form, and use the app on
   that host.

## Four things that will bite you

**The base domain and the workspace hosts must share a suffix.** The
resolver finds a workspace by stripping `BASE_DOMAIN` off the host and
looking up what is left. `BASE_DOMAIN=localapp.test` with a browser on
`acme.localhost` resolves to nothing, and you get a 404.

**`ALLOWED_HOSTS` must accept the subdomains.** It is currently `["*"]`,
so this is already true. If it is ever tightened, Django's leading-dot
form is a subdomain wildcard: `.localapp.test`.

**The dev proxy must forward the browser's Host.** `setupProxy.js` sets
`changeOrigin: false` on the API proxy for this reason — with it on, every
request would reach Django as `127.0.0.1:8000` and no workspace would ever
resolve. If you add a proxy entry that the app authenticates through,
leave `changeOrigin` off.

**The port is part of the local address.** The resolver strips it, so
`:3000` does not affect which workspace is found; but redirects and
emailed links carry it, and `http://acme.localapp.test` without the port
reaches nothing.

## Testing without hosts entries

The Django test client cannot edit `/etc/hosts`, so tests send an
`X-Tenant-Subdomain` header instead, which the middleware honours when
`ALLOW_TENANT_HEADER` (or `DEBUG`) is set. It is a test affordance, not a
development workflow — use real hosts locally, so that what you exercise
is what production does. Production must never enable it: it would make
the host boundary spoofable by a request header.

## What you should be able to see

- `http://localapp.test:3000/login` redirects to find-workspace — the
  main site belongs to no workspace, and the backend refuses to sign
  anyone in there.
- `http://new-tenant.localapp.test:3000/login` shows the workspace's name.
- A second workspace's user is refused at the first one's login (401).
- A session from one workspace, used on another's host, is redirected
  back to its own.
- `http://nobody.localapp.test:3000` — after adding it to `/etc/hosts` —
  answers 404 rather than a login page.
