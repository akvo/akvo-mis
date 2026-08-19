# Dashboard list and create flow: design

## Problem

A tenant has no way to see the dashboards they own or to make a new one.
There is no `/dashboards` route, no nav entry, and the only dashboard screen
in the app renders a JSON file from the bundle at an anonymous
`/dashboard/:slug`.

This slice builds the way in: the list screen, the create flow, the routes,
and the API client module every later frontend task calls. It also lands the
contract fixtures — the mechanism that lets the frontend track run in
parallel with the backend track for the rest of the milestone rather than
waiting on it.

The mockup for this slice is `doc/design/VIZ-Example/index.html`: app header
`31–51`, list screen `52–116`, create modal `413–448`, toast `449–457`.

## Decisions

- **The create modal asks for a name and a form family, not a template.**
  The mockup offers "start from a template" with three presets (`_preset`,
  `index.html:534–563`). Templates cannot work across tenants: question ids
  are tenant-local, so a copied widget array binds to nothing (VIZ-001
  §13.1). The field that replaces the template picker is the one D-3
  actually requires — **pick the root registration form up front**, because
  it fixes the dashboard's entire data universe. The cold-start problem the
  templates were reaching for is not solved in this epic — a new dashboard
  opens on a blank canvas. `VIZ-AI-001` is the eventual answer, a suggestion
  generated from the tenant's own form; it is a separate epic.
- Fixtures are a deliverable, not a scaffold. One JSON file per VIZ-001 §6
  response shape lands in `__fixtures__/`, and every later frontend task
  develops and tests against it until the matching backend task merges. At
  each phase boundary the fixtures are checked against the live endpoint;
  drift found there is a bug in the fixture or the view, never a reason to
  fork the contract.
- The list is the only place a dashboard's identity is edited. Name and
  description are also editable in the builder's settings panel, but slug is
  derived server-side and never shown as an input.
- Keep the mockup's thumbnail strip. It is not in VIZ-001 and it is worth
  building: each card renders a miniature of its widget layout from `type` +
  `col_span` (`_thumb`, `index.html:581–588`), which is what makes a list of
  a dozen similar-sounding dashboards scannable.

## Components

### 1. Routes and navigation

Three routes in `frontend/src/App.js`, backed by a new
`frontend/src/pages/dashboards/`:

| Route | Screen | Slice |
|---|---|---|
| `/dashboards` | list | this one |
| `/dashboards/:slug` | viewer | VIZ-008 |
| `/dashboards/:slug/edit` | builder | VIZ-006 |

The nav entry is gated on `dashboard_view` through the existing CASL ability,
so a user without it never sees the menu item. The legacy `/dashboard/:slug`
route keeps working until VIZ-009 removes it.

### 2. The API client module

`frontend/src/util/dashboardApi.js` wraps every VIZ-001 §6 endpoint — list,
create, retrieve, update, destroy, publish, unpublish, duplicate, sources,
and the published-read namespace. No component calls `api.get` directly.
One module means the `measure` expansion (VIZ-008) and the widget payload
shape (VIZ-006) each have exactly one place to live.

### 3. List screen

Cards, each showing name, description, updated date, a draft/published
badge, and the thumbnail strip. Row actions gated per permission: open,
edit (`dashboard_edit`), duplicate (`dashboard_create`), delete
(`dashboard_delete`). Empty state when the tenant has none
(`index.html:105`). Toast on save and delete (`449–457`).

Every dashboard on this screen is a tenant-owned row from
`GET /manage/dashboards`. Nothing is seeded, and nothing ships in the bundle.

### 4. Create flow

A modal (`index.html:413–448`) with two fields:

- **Name** — free text.
- **Data source** — a registration form, from the tenant's published
  registration forms. This is `root_form`, and the modal explains what it
  means in one line: *this dashboard will show data from this form and its
  monitoring forms*.

On submit, `POST /manage/dashboards` creates the draft and the app navigates
straight to `/dashboards/:slug/edit`. Slug is generated server-side from the
name; the client never sends one.

**`root_form` cannot be changed afterwards** (D-3). The modal is the only
place it is chosen, and the builder shows it as read-only text. Re-pointing
a dashboard at a different family means creating a new one — surfaced in the
UI as a plain sentence, not an error the user hits later.

### 5. Fixtures

`frontend/src/pages/dashboards/__fixtures__/`:

    dashboardList.json        GET  /manage/dashboards
    dashboardDetail.json      GET  /manage/dashboards/{id}
    dashboardSources.json     GET  /manage/dashboards/{id}/sources
    dashboardPublished.json   GET  /dashboards/{slug}
    registrationForms.json    the create modal's form picker

Shapes come from VIZ-001 §6 verbatim. The sample content mirrors the
mockup's `FORMS` constant (`index.html:460–479`) — an EPS registration form
and its monitoring child — so the fixtures exercise the family relationship
rather than a single flat form.

## Data flow

    /dashboards
      → GET /manage/dashboards            → cards
      → "Create dashboard"                → modal: name + registration form
      → POST /manage/dashboards           → draft, slug derived server-side
      → navigate /dashboards/:slug/edit   → VIZ-006

## Error handling

- A 403 from any endpoint means the caller lost a permission mid-session; the
  screen surfaces the message rather than a raw error. Client-side gating is
  UX, the server is authoritative.
- A slug collision returns 409; the client retries once with the
  server-suggested slug, and otherwise asks for a different name.
- A tenant with no published registration form cannot create a dashboard.
  The modal says so and links to the form builder, rather than offering an
  empty picker.

## Testing

- Every screen renders from fixtures with the backend absent.
- Permission gating per action: a user with `dashboard_view` only sees no
  create, edit, duplicate or delete control, and the API client is never
  called for them.
- The create modal lists only published registration forms — no monitoring
  forms, no drafts.
- Creating navigates to the builder route with the slug from the response.
- The empty state renders when the list is empty; the thumbnail strip renders
  proportional widths from `col_span`.

## Out of scope

- The builder itself (VIZ-006) and the viewer (VIZ-008). The two routes are
  registered here and render a placeholder.
- Templates, in any form (see Decisions).
- Publishing controls. The list shows a draft/published badge; the actions
  that change it arrive with VIZ-006 and VIZ-007.
