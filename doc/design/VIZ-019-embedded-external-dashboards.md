# Embedded external dashboards: design

**Status:** in review — GitHub [#361], PR [#366] **open**, branch
`feature/361-embedded-dashboards` (13 commits, 48 files). Not on `main`.

## Problem

Workspaces already have dashboards built elsewhere — Power BI, Tableau,
Metabase. Asking them to rebuild those here to have one place to look is
not a trade they will make, and the builder will never match a dedicated
BI tool feature for feature.

The obvious implementation is the dangerous one. An author's embed
snippet is third-party markup carrying third-party scripts. Rendered in
this application's origin it is cross-site scripting against every
visitor of a public page — and `AUTH_TOKEN` is a cookie without
`HttpOnly`, so a snippet could read the session straight out of
`document.cookie`.

## Decisions

- **One table, two kinds.** A dashboard is either `widgets` — built here
  from `DashboardWidget` rows against a root form — or `embed`, rendered
  from a pasted snippet. `root_form` becomes nullable; `embed_snippet` is
  its mirror. A separate model would duplicate tenant, slug uniqueness,
  status, `is_public`, `published_at` and soft deletes, then force the
  list, the read namespace and the header menu to union and re-sort two
  querysets — working directly against the point of the feature, which is
  that both kinds appear in one place.
- **The union is a database check constraint**, not validator-only.
  `validate_dashboard_payload` guards a single path; `duplicate()` writes
  rows without going through it, and so would a data migration or a shell
  session. The constraint also excludes the empty string, which
  `NOT NULL` does not — an embed holding `''` renders as an empty frame
  with nothing wrong in any log.
- **`kind` is immutable after creation**, for the same reason `root_form`
  is: switching strands either the widget rows or the snippet, and
  neither has a defensible automatic resolution.
- **The snippet's content is never inspected.** No URL scheme check, no
  parsing, no vendor branch. It renders on an origin of its own, so a
  validator here would reject working embeds we failed to anticipate
  while preventing nothing. The two remaining bounds — non-empty, under
  `EMBED_SNIPPET_MAX` — are bounds on storage, not opinions about
  content.
- **`EMBED_HOST` is a host that is not ours.** An *opaque* origin is the
  obvious alternative and does not work: a `srcdoc` frame sandboxed
  without `allow-same-origin` reports `window.origin === "null"`, and
  both target vendors fail there — Tableau's API requests carry
  `Origin: null` and CORS refuses them, Power BI's own frame inherits the
  sandbox and cannot reach its storage. Measured before choosing this
  shape. Serving the snippet as a document on a separate host lets the
  frame carry `allow-same-origin`, because the origin it grants is the
  embed host's. The embed host holds no session: `AUTH_TOKEN` is
  host-only, so the browser never sends it there.
- **The guard is inverted, deliberately.** It is no longer "never add a
  token"; it is *never point this frame at our own origin*, because with
  `allow-same-origin` set a same-origin `src` hands the snippet this
  page's DOM and cookies. `EmbedFrame` refuses such a src, absolute or
  relative, and treats an unparseable one as ours — the safe reading of
  "I cannot tell where this points" is "do not frame it".
  `allow-top-navigation` stays withheld.
- **An embedded dashboard's anonymous allowlist is empty.** It queries
  none of our data endpoints, so `/visualization/values`, `/escalation`,
  `/values/formula` and `/maps/geolocation` all answer 404 for a caller
  holding its slug.
- **No filter bar on an embed.** There is no data of ours to filter, and
  a control that changes nothing is worse than no control.

## Components

**Backend.** `0004_dashboard_embed` adds `kind` and `embed_snippet` and
the check constraint; every existing row already satisfies the widgets
arm, so the migration is pure schema.
`v1_visualization/embed_views.py` (new on the branch) serves the snippet
document on the embed host.
`public_scope.allowlist_from` returns the empty allowlist for an embed —
and, in the same change, subtracts `None` when building the widgets
branch's form set, so an unparseable `form_id` resolving to `None` cannot
satisfy `None in self.forms`.

**Frontend.** `EmbedFrame`, `EmbedEditor`, and a `kind` branch through
`CreateDashboardModal`, `DashboardBuilder`, `DashboardList` and
`DashboardViewer`. `DashboardVisibilityToggle` was extracted so both
kinds share one control.

## One deployment prerequisite

`EMBED_HOST` must be a real, separate host. Without it the feature has no
isolation boundary and must stay off. Documented in `env.example` and the
README on the branch.

## Note for reviewers

Preview uses a dedicated cache alias, not `default`. `v1_forms.signals`
clears the default cache in full on any form save, and several test
`setUp`s clear it outright — under `--parallel 4` another process seeding
forms deleted pending previews mid-test. The same would happen in
production whenever a colleague edited a form, and a cross-origin frame
reports nothing, so it would be indistinguishable from a broken embed.
