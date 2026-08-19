# Dashboard publish and read API: design

## Problem

VIZ-005 stores drafts. Nothing makes a dashboard visible to anyone but its
author, and there is no endpoint a viewer can read.

Two things have to be true at once. Editing a published dashboard must not
change what colleagues see mid-edit — a half-finished widget must not appear
on someone else's screen. And a dashboard whose question was soft-deleted in
the form builder must still load, with the broken widget visibly broken
rather than the whole page blank.

## Decisions (from VIZ-001)

- **Publish snapshots the widget rows into `published_config`** (D-2).
  Viewers read that field; the builder edits the live rows. A published
  dashboard being edited keeps serving its last snapshot until someone
  presses Publish again. This is what makes "edit a live dashboard" safe
  without a separate draft-copy record.
- **A JSONField, not a version table.** `FormPublishedVersion` exists because
  historical submissions must render against the schema used at collection
  time. A dashboard is a view — no stored artifact is bound to a past version
  of it — so version history buys nothing today. Rolling back to a previous
  published state is not supported. If it is ever wanted, promoting the field
  to a table is additive.
- **The read namespace is authenticated** (D-7). Unlike `/api/v1/forms`,
  there is no anonymous dashboard surface. That is the CLEANUP-001 fix, and
  it is the reason `/dashboard/:slug` goes away in VIZ-009.
- **Broken widgets degrade; they do not fail the dashboard** (D-9). The
  serializer annotates rather than filters, so the viewer can show a
  placeholder in the right grid position instead of silently reflowing the
  layout around a hole.

## Components

### 1. Publish

`POST /manage/dashboards/{id}/publish`, permission `dashboard_publish`.

Serializes the live widget rows into `published_config` in the VIZ-001 §4.1
shape, sets `status = published` and `published_at = now`. Validation runs
again first — publishing an invalid dashboard is refused, even though save
should have caught it, because `published_config` is what viewers read and
nothing revalidates it downstream.

Republishing an already-published dashboard re-snapshots. It is the only
operation that changes what viewers see.

### 2. Unpublish

`POST /manage/dashboards/{id}/unpublish`, permission `dashboard_publish`.

Sets `status = draft`. `published_config` is deliberately **left alone** —
it is a record of what was last live, and clearing it would destroy the only
thing a re-publish could be compared against. The read namespace filters on
`status`, not on the field's presence, so an unpublished dashboard is
immediately unreachable to viewers.

### 3. Duplicate

`POST /manage/dashboards/{id}/duplicate`, permission `dashboard_create`.

Clones the dashboard and its widget rows as a new draft: fresh slug
(`"<slug>-copy"`, uniquified), `status = draft`, `published_config = None`,
`created_by` set to the caller. `root_form` is copied — the clone is in the
same family, and a duplicate that could change families would contradict D-3.

### 4. The read namespace

| Method | URL | Returns |
|---|---|---|
| GET | `/api/v1/dashboards` | published dashboards in the caller's tenant |
| GET | `/api/v1/dashboards/{slug}` | one dashboard's `published_config` |

Authenticated, no feature permission beyond being signed in — a dashboard is
published *to the tenant*. Scoped through `for_user`, filtered to
`status = published` and live rows. The detail endpoint serves
`published_config` in a single row fetch: no widget join, no per-widget
query.

### 5. Widget health annotation

Because `DashboardWidget.question` is a real FK (D-1), the check is a join
rather than a JSONB scan. On read, each widget is annotated:

    is_broken: true,
    broken_reason: "question_deleted" | "form_deleted"

set when the referenced question's `deleted_at` is not null, or its form is
gone. The dashboard still returns 200 with every other widget intact.

The annotation is computed on the snapshot as it is served, not baked into
`published_config` at publish time — a question can be deleted at any point
after publishing, and a stale `is_broken: false` would be worse than none.

## Data flow

    draft ──POST /publish──▶ published        widget rows → published_config
      ▲                          │
      │                          ├─ PUT edits rows; viewers still see the
      │                          │  old snapshot until the next publish
      └──POST /unpublish─────────┘

    GET /dashboards/{slug}
      → for_user + status=published + not deleted
      → published_config, widgets annotated with is_broken

## Error handling

- A foreign or draft slug on the read namespace → 404. Draft and
  nonexistent are indistinguishable to a viewer, which is correct: a draft
  is not theirs to know about.
- Publishing a dashboard that fails validation → 400, `status` unchanged.
- Publishing or unpublishing without `dashboard_publish` → 403.
- A soft-deleted question never raises. `PROTECT` does not fire on a soft
  delete, and the read path expects the dangling reference.
- Publish and duplicate are atomic.

## Testing

- **Edit-does-not-leak (D-2), the one that matters**: publish, then `PUT` a
  changed widget array, then `GET /dashboards/{slug}` — the response is
  unchanged. Publish again — now it changes.
- Unpublish makes the slug 404 for a viewer while the dashboard stays
  editable for its author, and `published_config` survives.
- Duplicate produces a draft with a unique slug, the same `root_form`, the
  same widget count, and no `published_config`.
- Two tenants: neither can list or fetch the other's published dashboard by
  slug.
- Broken widgets: soft-delete a question referenced by two of five widgets →
  `GET` returns 200, exactly those two carry `is_broken: true`, the other
  three are untouched.
- The detail endpoint's query count does not grow with widget count.
- Publishing an invalid dashboard is refused and leaves `status` alone.

## Out of scope

- Version history and rollback (D-2). One snapshot field, no table.
- Anonymous or tokenized public sharing (D-7). Any future public dashboard
  carries its own token model rather than reopening anonymous access.
- The viewer UI (VIZ-008) and the form-builder delete warning (VIZ-009),
  both of which consume what this slice produces.
