# The platform console

The console is where a deployment's own staff manage the workspaces on
it: list them, read their counts, suspend, rename, toggle entitlements
and manage the people who can do any of that. It is a different product
from the workspace app and is served on a host of its own.

*Operator* means a platform administrator — someone who works on the
deployment. *Superadmin* stays what it has always been: the owner of one
workspace. The two are separate flags on separate accounts, and an
operator belongs to no workspace at all.

## Where it lives

    admin.<BASE_DOMAIN>

`admin` is reserved: registration and rename both refuse it, so no
workspace can take the address from under the console. With
`BASE_DOMAIN` empty there is no console, because a single-host install
is one workspace and has nothing to administer across.

The label is `ADMIN_SUBDOMAIN`, and `admin` is only its default. Change
it if that address is already taken — by another service on the same
domain, or by a workspace registered before the name was reserved, since
the reservation refuses new registrations but does not rename rows that
predate it. The reservation follows the setting, so whatever the console
is on is what registration refuses.

Two things to know before changing it on a running deployment. The
frontend cannot read a Django setting, so the label reaches it through
`config.js` — **run `manage.py generate_config` after changing it**, or
the browser keeps looking for the console at the old address while the
server answers at the new one. And an operator invitation already in
someone's inbox points at the old host; those links stop working, so
re-invite anyone still pending.

Locally that means one more `/etc/hosts` line beside the ones in
[`subdomain-local-dev.md`](subdomain-local-dev.md):

    127.0.0.1  admin.localapp.test

Sign-in is the app's own login page, served on this host. Only an
operator is accepted there; a workspace account typed into it is
refused with the same message the base domain gives, so the console
never becomes a way to find out which addresses exist in which
workspace.

## The first operator

**Operator zero is created on the server, not in the console:**

    ./dc.sh exec backend python manage.py createplatformadmin \
        --email ops@example.org --password '<password>'

Every other operator is invited from **Operators → Invite operator**,
which mails an activation link to `admin.<BASE_DOMAIN>/activate/<token>`.
The invited account is inactive and has no usable password until that
link is followed, and the console lists it as *pending* until then.

The first one cannot come that way because nobody exists to send the
invitation. On a fresh deployment the operators list is therefore empty
until this command has been run — that empty list is the bootstrap step,
not a fault.

Revoking an operator clears the flag and ends their console access at
once, including any inspection session already open. The account itself
remains. Nobody can revoke themselves: doing so would end the session
mid-request and leave the console reachable only by whoever else happens
to hold the flag.

## Resetting a password

An operator's reset link is mailed to the console host, not to the base
domain, for the same reason the activation link is: what waits at the
end of it is a session, and a session is only valid on the host that
issued it. The base domain refuses to sign anyone in, so a reset sent
there could never be completed.

Locally, check the mail in Mailpit at <http://localhost:8025>. The link
is built from `WEBDOMAIN`, so that variable has to be the address the
browser actually uses or the mailed link will point somewhere else.

## Renaming a workspace

The dialog names what breaks, counted from that workspace: dashboard links
inside it, and the publicly shared ones whose readers cannot be told a new
address. Both are real outages — there is no alias table, so the old address
stops resolving at once.

**Enrolled mobile devices are not affected**, which is worth knowing because
it is the first thing people expect to break. The app is configured against
this deployment's address, not a workspace's, and a device's replies are
partitioned by the token it carries rather than by the host it calls — so a
rename leaves it syncing, and still unable to see any other workspace.

The exception is a deployment that deliberately pointed devices at a
workspace's own address. Nothing in the app does this and the server cannot
tell which devices were set up that way, so if that is how yours is
configured, re-enrol those devices after a rename.

## Inspecting a workspace

**Inspect** on the workspaces list opens that workspace's own application,
at its own address, in a read-only session. There is no separate viewer: what
you see is the customer's app, with the customer's data, which is the point —
a support case about a dashboard that will not load is answered by opening
the dashboard that will not load.

One click, no reason prompt. A typed justification on every support call
would buy a free-text field nobody reads at the cost of friction on the most
common action in the console.

An orange bar across the top names the workspace, says **read only**, gives
the time the session ends, and carries the two things you need from it: a
workspace switcher and **Exit inspection**. Switching moves this tab straight
to another workspace without going back to the console. Suspended and deleted
workspaces are not offered and cannot be inspected — their addresses no longer
resolve, so the link would lead nowhere.

**Read only means the server refuses the write, not that the button is
hidden.** Write controls are greyed out as a courtesy; the refusal happens
server-side whether or not the browser tries. Two independent guards enforce
it, so a page reached by an unusual route still cannot write.

### What the session is, exactly

While inspecting, you hold the authority of that workspace's owner, minus
every write. That is more than any one of the customer's staff typically has,
and it is not the same as *being* one of them: a bug that happens only to a
particular user with a particular role may not reproduce for you. Seeing the
app as a named user is a separate feature that does not exist yet.

The session lasts twelve hours, but it does not depend on that. Every single
request re-checks that you are still a platform admin, so **revoking an
operator ends every inspection they have open, immediately** — including tabs
left open on other machines. Suspending or deleting the workspace ends it too.

Sessions are confined to one address each. The cookie the workspace sets is
that workspace's alone and never reaches the console, so signing out of one
does not sign you out of the other, and closing the tab does not end the
console session.

**Exit inspection clears the browser's copy of the session, not the session.**
The token stays valid for its remaining time; what ends it everywhere, at
once, is revoking the operator. That is the difference worth knowing on the
day it matters: if you think a session may have been left somewhere it should
not be, exiting the tab is not the answer — revoking the operator is.

### The record it leaves

Each inspection writes a row to `tenant_inspection` naming the operator, the
workspace and the time. That table exists to carry the one-time hand-off
code, not as an audit feature: no screen shows it, no endpoint reads it, and
nothing in the console is built on it. The rows do stay, so "which of our
staff opened this workspace" is answerable with a query — but treat that as
a byproduct rather than a control.

Customers are not notified when their workspace is inspected. Whether they
should be is a commercial decision, not a technical one.
