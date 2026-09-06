# Public dashboard visibility: design

**Status:** shipped — GitHub [#352], PR [#360], commit `6e4fa412`.
Nine commits, backend and frontend.

## Problem

CLEANUP-001 deleted the previous public dashboard because an anonymous
caller could name any form id and walk any workspace's aggregates.
VIZ-001 D-7 then made the read namespace authenticated outright. That was
the right immediate fix and the wrong end state: sharing a dashboard with
a funder or a ministry is a core reason to build one.

Reopening it means answering the question CLEANUP-001 could not: what may
an anonymous caller ask about?

## Decisions

- **`is_public` is a column, not a third `status` value.** "Is this
  finished" and "who may see it" are different questions that must move
  independently. Folded together, Unpublish and Make-private become the
  same button, and an author could not take a dashboard off the public
  web without also hiding it from colleagues.
- **Visibility has its own endpoint** (`POST /manage/dashboards/{id}/
  visibility`) rather than being a field on `update`. `update` validates
  the whole payload and rewrites every widget row, so riding on it would
  let a half-configured widget block the one action whose purpose is
  *reducing* exposure.
- **The invariant is enforced from both ends.** A draft cannot be made
  public — the flag has no observable effect there, and allowing it would
  make Publish the button that exposes a dashboard to the internet.
  Unpublish clears the flag, so an unpublish/republish cycle can never
  silently put a dashboard back online.
- **An anonymous caller names one dashboard and may query only the ids
  that dashboard's published snapshot names.** This is the rule that
  replaces what CLEANUP-001 deleted.
- **The allowlist is read from `published_config`, never the live widget
  rows.** An author who deleted a widget without republishing has not yet
  narrowed what the public dashboard *shows*, so they must not have
  narrowed what it may *query* either.
- **Refusal is 404, never an empty result.** An out-of-allowlist id
  answered with `[]` would let a regression here read as "that widget has
  no data" — the one failure mode nobody investigates.

## Components

[`public_scope.py`](../../backend/api/v1/v1_visualization/public_scope.py)
holds the boundary. `resolve_view_scope(request)` returns
`(tenant, allowlist)`: an authenticated caller gets the tenant it always
had and `ALLOW_ANY`, so the signed-in path is unchanged; an anonymous
caller gets the named dashboard's own tenant, never anything the request
supplied.

Three details that were each a hole before they were closed:

- **Scope resolves *before* the serializer.** Serializer validators issue
  tenant-unscoped existence queries, so resolving afterwards let an
  anonymous caller tell 400 ("Form N not found") from 404 and enumerate
  another workspace's schema by id.
- **Question ids hide in three grammars.** `criteria`, `columns` and
  formula `buckets` all carry them under other names, so checking
  `form_id` alone would have made the allowlist decorative. Each is
  parsed in `public_scope.py`, read *raw* from the query string — the
  serializers' hooks replace those strings with parsed structures, and an
  extractor handed a parsed list finds nothing to check.
- **Every extractor strips a clause before splitting**, matching the
  downstream parsers byte for byte. Without it, a leading space injected
  as `%20` desynced the two and an `overdue` criterion's second question
  id went unchecked while the downstream parser still queried it.

`annotate_broken` moved from `for_user` to tenant-based resolution. Given
an anonymous caller, `for_user` returns the tenant-less queryset, which
would mark every widget on a public dashboard broken and render the whole
page as an error — a failure that looks like data loss rather than like a
missing permission. The tenant was the right axis anyway: the question is
which ids are live in this workspace, and that never depended on who was
asking.

A `None` tenant serves *nothing* rather than filtering `tenant IS NULL`,
which would hand tenant-less rows — present in the test suite and in any
database predating the MT-002 backfill — to anonymous callers on the base
domain.

**Frontend.** The public/private switch lives in the Dashboard settings
panel, in its own bordered block: every other field there is dirty state
flushed by Save, while this one writes immediately through its own
endpoint. `PublicDashboardMenu` puts published dashboards in a header
dropdown next to the user menu, so a read-only or anonymous visitor has a
way in that does not involve the Control Center sidebar.

## Access tiers

| Caller | Sees |
|---|---|
| Anonymous | Published + public dashboards of the host's workspace |
| Signed in, no dashboard access | The same |
| Signed in, any dashboard access | All published dashboards in their own workspace |

The authenticated gate is "any dashboard feature access", not
`dashboard_view` alone: a role with Edit but not View would otherwise be
able to build a private dashboard and unable to open it.

## Testing

Every guard has a committed test proven to fail without it, including the
cross-tenant case — two workspaces publishing the same guessable slug,
each host serving only its own.

Twelve `v1_visualization` test modules had never authenticated their
client and were unknowingly exercising the anonymous-and-unscoped path.
Setting a JWT once in the shared mixin's `setUp` put them back on the
authenticated path without touching an assertion.
`tests_values_tenant_scope.py` was handled separately because one of its
tests deliberately covers the anonymous path; its contract is superseded,
not broken, and it now passes a public dashboard slug instead of
authenticating.
