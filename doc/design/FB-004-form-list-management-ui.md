# Feature Design Document: Form Listing & Management UI

**Task ID**: FB-004
**Author**: Iwan
**Date**: 2026-06-09
**Status**: Implemented (see §14 Implementation Notes for deltas from this design)

**Builds on**: FB-001 (data architecture), FB-002 (backend CRUD API), FB-003 (frontend editor integration)

---

## 1. Context & Problem Statement

```
Currently:
- FormBuilderList.jsx renders an AntD table (Last Updated, Name, Type,
  Status, Version, Actions) with server pagination (10/page).
- Row actions are limited to Edit and "Create Monitoring Form".
- Backend /api/v1/manage/forms already implements duplicate, publish,
  and unpublish endpoints (FB-002) with granular CASL permissions.
- GET /manage/forms returns ALL forms flat — no search, no status/type
  filter, no hierarchy, and no submission count.

Goal:
- Make the list usable at scale with server-side search + status/type filters.
- Surface the already-built duplicate / publish actions as row buttons with
  confirmation modals and per-action permission gating.
- Add Archive as a reversible soft-delete: archived forms drop out of data
  collection automatically and move to an "Archived" tab.
- In the Archived tab, let users Restore (-> draft) or, when a form has no
  submissions, Delete it permanently (users with `form_delete` access).
- Show the registration -> monitoring hierarchy via AntD expandable rows.
```

This task is mostly **wiring and a focused backend filter addition**. The one genuine model change is making `Forms` soft-deletable to power Archive (D-1) — a small, idiomatic addition, since `QuestionGroup` and `Questions` in the same module already use the `SoftDeletes` mixin.

---

## 2. Requirements

### User Acceptance Criteria

| # | Criterion |
|---|---|
| U-1 | Users see all forms in a table with a status indicator (Draft / Published tag) |
| U-2 | Users filter by status (All / Draft / Published) — applied server-side |
| U-3 | Users filter by type (All / Registration / Monitoring) — applied server-side |
| U-4 | Users search forms by name with a debounced input — applied server-side |
| U-5 | Users can Edit, Duplicate, Publish, and Archive a form from its row |
| U-6 | Monitoring forms appear as expandable child rows under their registration parent |
| U-7 | A prominent "Create New Form" button is present |
| U-8 | Archiving a form shows a warning with submission impact before confirming |
| U-9 | Each action is hidden/disabled when the user lacks the matching permission |
| U-10 | The list has two tabs — **Active** and **Archived** — so archived forms are out of the working set but one click away |
| U-11 | From the Archived tab, a user can Restore a form (returns as draft) or Delete it permanently |
| U-12 | Permanent delete is offered only when the form has no submissions and only to users with `form_delete` access (superusers included); otherwise the form can only stay archived or be restored |

### Technical Acceptance Criteria

| # | Criterion |
|---|---|
| T-1 | `GET /manage/forms` accepts `search`, `status`, `type` query params |
| T-2 | List response exposes `submission_count` (or `has_submissions`) per form |
| T-3 | Monitoring children are embedded per registration parent so AntD `expandable` pagination counts parent rows only |
| T-4 | Frontend search debounced (~400-500ms); changing any filter resets to page 1 |
| T-5 | Action buttons open confirmation modals (Publish = confirm; Archive = warning with impact), then call the API and refresh the list |
| T-6 | Button visibility maps to CASL: Edit->`form_edit`, Duplicate->`form_create`, Publish->`form_publish`, Archive/Restore->`form_publish`, Delete permanently->`form_delete` (and only when `submission_count == 0`) |
| T-7 | `Forms` becomes soft-deletable (`SoftDeletes` mixin); Archive = soft-delete, Restore = restore-to-draft. The default `Forms.objects` manager excludes archived forms everywhere, so data-collection endpoints need no manual exclusion |
| T-8 | `unpublish` is unchanged — Archive does **not** reuse it; the FB-003 publish->unpublish correction loop is preserved |
| T-9 | Frontend passes ESLint (curly, no-undefined, prefer-arrow); backend passes flake8; new filter + archive logic covered by tests |

---

## 3. Data Model Changes

### Modified Model: `Forms` becomes soft-deletable

`Forms` currently extends `models.Model` ([models.py:16](../../backend/api/v1/v1_forms/models.py#L16)). Add the existing `SoftDeletes` mixin (already used by `QuestionGroup` and `Questions` in the same module):

```python
from utils.soft_deletes_model import SoftDeletes

class Forms(SoftDeletes):   # was: models.Model
    # ... unchanged fields ...
    # SoftDeletes contributes:
    #   deleted_at = DateTimeField(null=True, blank=True)
    #   objects               -> excludes archived (deleted_at IS NULL)
    #   objects_deleted       -> only archived
    #   objects_with_deleted  -> all rows
```

| Model | Change | Reason |
|-------|--------|--------|
| `Forms` | Add `SoftDeletes` mixin (`deleted_at` + soft-delete managers) | Power a reversible Archive that auto-hides forms from data collection |

### Migration Strategy

```
- One migration: add nullable `deleted_at` to the forms table.
- No backfill: every existing row keeps deleted_at = NULL (= active), so
  behavior is identical on day one. Forms only disappear once explicitly archived.
- Rollback: drop the column; no archived rows means no data loss on revert.
```

### Why soft-delete instead of a `FormStatus.archived` value

The default manager swap is the entire benefit. With `SoftDeletes`, `Forms.objects` filters `deleted_at IS NULL`, so **archived forms are excluded automatically** from every consumer that uses the default manager — no per-site patching:

| Data-collection site | `FormStatus.archived` (rejected) | `SoftDeletes` (chosen) |
|----------------------|----------------------------------|------------------------|
| `list_form` ([views.py:258](../../backend/api/v1/v1_forms/views.py#L258)) | needs explicit exclude | auto-excluded |
| `generate_config` (`Forms.objects.all()`) | **must add filter** | auto-excluded |
| mobile `MobileAssignmentForms` (`obj.forms.all()`) | **must add filter** | auto-excluded |
| `parent.children.all()` | **must add filter** | auto-excluded |

Related managers resolve through `Forms._default_manager`, so archived forms also drop out of mobile assignments and child lookups. See D-1.

### Read-only fields exposed by the list endpoint

| Field | Source | Use |
|-------|--------|-----|
| `name`, `version`, `status`, `type`, `parent` | `Forms` | columns + filters |
| `parent_name` | derived: `obj.parent.name` | parent label in the flattened monitoring view (D-4) |
| `created`, `updated` | `Forms` | "Last Updated" column |
| `published_at` | `Forms` | shown in detail / version history |
| `deleted_at` | `Forms` | drives the "Archived" status display |
| `submission_count` | derived: `obj.form_form_data.count()` | archive impact warning |

---

## 4. API Contract

### New Endpoints

| Method | URL | Action | Permission |
|--------|-----|--------|------------|
| POST | `/api/v1/manage/forms/{id}/archive` | Soft-delete the form (`form.soft_delete()`). Allowed even with submissions. | `form_publish` |
| POST | `/api/v1/manage/forms/{id}/restore` | Restore an archived form; sets `status=draft` (D-7). | `form_publish` |

### Changed Endpoint (FB-002)

| Method | URL | Change | Permission |
|--------|-----|--------|------------|
| DELETE | `/api/v1/manage/forms/{id}` | `destroy()` now calls `hard_delete()` and resolves via `objects_with_deleted` so an archived form can be permanently removed (D-9, D-10). Still 409s if submissions exist. | `form_delete` (D-11) |

### Modified Endpoint

| Method | URL | Change |
|--------|-----|--------|
| GET | `/api/v1/manage/forms` | Add `search`, `status`, `type`, `archived` query params; embed monitoring children; add `submission_count` |

The viewset must serve the archive/restore/retrieve actions via `Forms.objects_with_deleted` (the default `objects` manager cannot see an archived form, so without this you could not fetch one to restore it).

### Reused Endpoints (already implemented in FB-002, unchanged)

| Method | URL | Action | Permission |
|--------|-----|--------|------------|
| POST | `/api/v1/manage/forms/{id}/duplicate` | Duplicate | `form_create` |
| POST | `/api/v1/manage/forms/{id}/publish` | Publish | `form_publish` |
| POST | `/api/v1/manage/forms/{id}/unpublish` | Unpublish for corrections (published -> draft) — **distinct from Archive** | `form_publish` |

### Query Parameters

| Param | Values | Behavior |
|-------|--------|----------|
| `search` | string | Case-insensitive `name__icontains`, matched against parents **and** children (D-5) |
| `status` | `draft` \| `published` | Maps to `FormStatus` int; omitted = all (active forms) |
| `type` | `registration` \| `monitoring` | Maps to `FormTypes` int; omitted = all. Changes the row shape (D-4) |
| `archived` | `true` | When set, lists archived forms (`objects_deleted`) instead of active ones. Omitted = active only (D-8). |
| `page` | int | Existing pagination (10/page) |

### Display modes by `type` filter (D-4)

| `type` | Rows returned | `children` embedded? | Pagination unit |
|--------|---------------|----------------------|-----------------|
| _(omitted)_ | Registration parents | Yes — monitoring children nested/expandable | parent rows |
| `registration` | Registration forms only | No (children suppressed) | registration rows |
| `monitoring` | Monitoring forms, **flattened to top-level** | N/A (already leaf rows) | monitoring rows |

When `type=monitoring`, each row carries its `parent` id/name for display in a column; rows are **not** nested under a registration container (that container would itself be filtered out, which is contradictory). Search behaves differently — see D-5.

### Request / Response Examples

```
GET /api/v1/manage/forms?search=household&status=published&type=registration&page=1
```

```json
{
  "data": [
    {
      "id": 1,
      "name": "Household Survey 2026",
      "type": 1,
      "status": "published",
      "version": 2,
      "parent": null,
      "parent_name": null,
      "updated": "2026-06-09T10:20:00Z",
      "created": "2026-01-15T10:30:00Z",
      "published_at": "2026-01-20T14:22:00Z",
      "deleted_at": null,
      "submission_count": 134,
      "children": [
        {
          "id": 7,
          "name": "Household Monitoring Q2",
          "type": 2,
          "status": "draft",
          "version": 1,
          "parent": 1,
          "parent_name": "Household Survey 2026",
          "updated": "2026-06-08T09:00:00Z",
          "created": "2026-05-30T09:00:00Z",
          "published_at": null,
          "deleted_at": null,
          "submission_count": 0,
          "children": []
        }
      ]
    }
  ],
  "current": 1,
  "total": 1,
  "total_page": 1
}
```

The pagination envelope is the project-standard `Pagination` shape: `{ current, total, total_page, data }` (page size 10).

```
POST /api/v1/manage/forms/1/archive    -> 200 { "id": 1, "status": "archived", "deleted_at": "2026-06-09T11:00:00Z" }
POST /api/v1/manage/forms/1/restore    -> 200 { "id": 1, "status": "draft",    "deleted_at": null }
```

**Pagination semantics**: `total` counts whatever the current **top-level row** is for the active mode (D-4) — registration parents for "all"/"registration", monitoring forms for "monitoring". Nested monitoring children (in "all" mode) ride inside their parent's `children` array and are not paginated independently.

---

## 5. Decision Log

### D-1: Archive = soft-delete via the `SoftDeletes` mixin

**Options Considered**:
1. Map "Archive" to the existing `unpublish` endpoint (published -> draft).
2. Add a `FormStatus.archived` (3) value + archive/restore endpoints.
3. Make `Forms` soft-deletable; Archive = `soft_delete()`, Restore = `restore()`.

**Decision**: Option 3.

**Rationale**:
- Option 1 overloads `unpublish`, which FB-002 built as the *correction loop* (pull a published form back to editable draft, then re-publish). This is **live and tested**, not dead code: the editor's "Unpublish" button calls it ([FormBuilderEdit.jsx:126](../../frontend/src/pages/form-builder/FormBuilderEdit.jsx#L126), shown when `formStatus === "published"`), and `tests_manage_form_snapshot_put.py` covers the full `publish → unpublish → edit → re-publish` lifecycle. Reusing it for Archive would regress that feature. Rejected.
- Option 2 (explicit status) leaves archived forms visible to data collection unless every consumer adds an explicit exclusion (`generate_config`, mobile assignment, `parent.children`, …). Easy to miss; brittle.
- Option 3 reuses the mixin already powering `QuestionGroup`/`Questions` in this module. The default `Forms.objects` manager filters `deleted_at IS NULL`, so archived forms vanish from **all** default-manager consumers with zero per-site changes. Archive is reversible (`restore()`) and orthogonal to the draft/published lifecycle, so `unpublish` is untouched.

**Impact**: `Forms` gains `SoftDeletes` (§3). Archive is allowed even when submissions exist (unlike the permanent hard `DELETE`, which still 409s on submissions — it remains the permanent-delete path, gated by `form_delete` per D-11). The viewset reads through `objects_with_deleted` for archive/restore/retrieve so archived rows are reachable for those actions only. **See D-9 for the required `destroy()` change** the mixin forces.

### D-9: `destroy()` must call `hard_delete()` after the mixin is added

**Problem**: `SoftDeletes` overrides the `.delete()` instance method ([soft_deletes_model.py:67](../../backend/utils/soft_deletes_model.py#L67)) to soft-delete by default. The existing `destroy()` ([views.py:590](../../backend/api/v1/v1_forms/views.py#L590)) calls `form.delete()`. Adding the mixin would **silently convert the DELETE endpoint from a hard delete into a soft delete** — making it a redundant second archive path and meaning nothing is ever truly removed.

**Decision**: Change `destroy()` to call `form.hard_delete()` (= `delete(hard=True)`), keeping the existing 409-on-submissions guard.

**Rationale**: Preserves a clear two-tier model — **Archive** = reversible soft-delete (submissions allowed); **DELETE** = permanent hard-delete (`form_delete`, blocked if submissions exist — D-11). Without this, the two collapse into one.

**Impact**: One-line change in `destroy()` (`form.delete()` → `form.hard_delete()`), plus a `get_object()`/`get_queryset()` change so `destroy` resolves through `Forms.objects_with_deleted` — the form being permanently deleted is archived (D-10) and invisible to the default manager. Permanent removal and the 409-on-submissions guard are unchanged; the permission widens from superuser-only to `form_delete` (D-11).

### D-7: Restore returns the form to draft

**Options Considered**:
1. Restore preserves the form's prior status (a restored published form goes live again immediately).
2. Restore always sets `status = draft`.

**Decision**: Option 2.

**Rationale**: Bringing a retired form straight back into live data collection on a single click is surprising and risky. Returning it to draft forces a deliberate re-publish (which also re-activates the correct snapshot via the existing `publish` path).

**Impact**: `restore` clears `deleted_at` **and** sets `status = FormStatus.draft` in one transaction.

### D-8: Two tabs — "Active" and "Archived"

**Options Considered**:
1. `status` filter gains an "Archived" option; "All" includes archived rows inline.
2. A "Show archived" checkbox toggling `?archived=true`.
3. Two tabs — **Active** and **Archived** — each mapping to the manager split.

**Decision**: Option 3.

**Rationale**: Archived = retired; it should not clutter the working set, and it carries a *different action set* (Restore / Delete permanently) than active forms (Edit / Duplicate / Publish / Archive). Tabs make that mode switch explicit and give the archived list a clear home, rather than hiding it behind a checkbox. It also keeps the soft-delete state out of the `status` enum, which stays draft/published only.

**Impact**: The **Active** tab uses `Forms.objects`; the **Archived** tab uses `Forms.objects_deleted` (`?archived=true`). The search/status/type filters apply within each tab. The status filter inside the **Active** tab remains Draft / Published.

### D-10: The Archived tab offers Restore and (conditional) Delete permanently

**Decision**: Each Archived-tab row offers two actions:
- **Restore** → `POST /{id}/restore` (→ draft, D-7). Permission: `form_publish`.
- **Delete permanently** → the existing `DELETE` (now `hard_delete()`, D-9). Permission: `form_delete` (D-11). **Shown only when `submission_count == 0`.**

**Rationale**: Archive is allowed even when submissions exist (D-1), so an archived form may hold submissions — but `destroy()` still 409s on submissions (D-9). Rather than let the user click into a guaranteed 409, the FE hides/disables "Delete permanently" when `submission_count > 0`, with a tooltip explaining the form can only stay archived or be restored. This keeps the destructive path available exactly where it is safe (no data loss) and authorized (`form_delete`).

**Impact**:
- `destroy()`'s `get_object()` must resolve through `Forms.objects_with_deleted`, since the form being permanently deleted is archived and invisible to the default manager.
- `submission_count` (already in the list payload, T-2) drives the button's enabled state.
- No new endpoint — reuses `DELETE /manage/forms/{id}`.

### D-11: Permanent delete uses the existing `form_delete` permission

**Problem**: `destroy()` is currently hardcoded to `IsSuperAdmin` ([views.py:471](../../backend/api/v1/v1_forms/views.py#L471)), even though `FeatureAccessTypes.form_delete (7)` already exists ([constants.py:50](../../backend/api/v1/v1_profile/constants.py#L50), `"Form Delete"`) and is assignable to roles — it has simply never been wired to an endpoint.

**Decision**: Change `destroy`'s permission map entry from `[IsAuthenticated, IsSuperAdmin]` to `[IsAuthenticated, FormBuilderAccess(FeatureAccessTypes.form_delete)]`.

**Rationale**: `FormBuilderAccess` already auto-grants superusers ([custom_permissions.py:81](../../backend/utils/custom_permissions.py#L81)) and otherwise checks for the `form_builder` / `form_delete` role grant. So this widens permanent delete to **superuser OR any role granted `form_delete`**, consistent with how every other form-builder action is gated, and activates a permission that was defined but dormant. No new constant or permission class is needed.

**Impact**: One-line change in `get_permissions`. Existing superuser callers are unaffected (still allowed). Roles can now be granted permanent-delete rights without superuser status.

### D-2: Hierarchy via AntD expandable rows

**Options Considered**:
1. Server-side group ordering (parent immediately followed by children), flat rows.
2. AntD expandable nested rows with children embedded per parent.
3. Flat list with a parent-name column only.

**Decision**: Option 2.

**Rationale**: Keeps pagination clean (parents per page) and gives a true visual hierarchy without splitting a family across page boundaries.

**Impact**: List serializer returns a nested `children` array per registration form; `total` counts parents only. The frontend uses AntD `Table` `expandable` / `childrenColumnName="children"`.

### D-3: Server-side filtering and search

**Options Considered**:
1. Full server-side `search` / `status` / `type` params.
2. Client-side filter of the current 10-row page only.
3. Load all forms once, paginate/filter client-side.

**Decision**: Option 1.

**Rationale**: The list is server-paginated; client-side options either miss off-page forms (2) or scale poorly (3). Backend filter work is accepted into this task's scope.

**Impact**: `FormBuilderViewSet.get_queryset()` gains query-param filtering; frontend adds debounced search + filter dropdowns that reset to page 1.

### D-4: `type` filter changes the row shape (flatten monitoring)

**Options Considered**:
1. `type=monitoring` keeps children nested under their (filtered-out) registration parent.
2. `type=monitoring` flattens monitoring forms to top-level rows; `type=registration` suppresses children.

**Decision**: Option 2. One row shape per mode — see the table in §4.

**Rationale**: Nesting monitoring rows under a parent the filter excludes would render registration rows the user explicitly filtered away, and would break pagination counts. Flattening matches intent ("show me monitoring forms") and keeps each mode's pagination unit equal to the rows displayed. The parent is still shown via a column, so context is preserved.

**Impact**: Serializer chooses nested vs flat output based on the `type` param. Frontend renders the parent-name column only in monitoring mode.

### D-5: Search matches children and returns the parent as a container

**Options Considered**:
1. Search matches parent names only.
2. Search matches parent **and** child names; a child match pulls in its parent as a non-matching container so the hierarchy stays intact.

**Decision**: Option 2.

**Rationale**: Users searching "monitoring Q2" expect to find a monitoring child even when the parent name doesn't match. Returning the parent as a container preserves the expandable hierarchy and shows where the match lives. This is distinct from the `type` filter (D-4): search is content-driven and benefits from context; a type filter is a hard scope.

**Impact**: When `search` is active in "all" mode, a parent is included if it matches **or** any of its children match; non-matching children of a matched parent are still returned. Implementation note: filter children in the serializer/queryset, then include any parent with surviving children.

### D-6: "Archived" status string is derived from `deleted_at`

**Decision**: `ListFormSerializer.get_status` returns `"archived"` when `deleted_at` is set, otherwise the existing draft/published mapping. The underlying `status` integer (draft/published) is preserved unchanged for when the form is restored.

**Rationale**: Gives the FE a single `status` field to render (Draft / Published / Archived) without exposing `deleted_at` parsing to the client, while keeping the soft-delete state out of the `FormStatus` enum.

**Impact**: Archived rows only ever appear in the `?archived=true` view (D-8), so this string surfaces exactly there.

---

## 6. Type / Constant Mappings

| Frontend control value | Backend constant | DB value |
|------------------------|------------------|----------|
| `status=draft` | `FormStatus.draft` | `1` |
| `status=published` | `FormStatus.published` | `2` |
| `type=registration` | `FormTypes.registration` | `1` |
| `type=monitoring` | `FormTypes.monitoring` | `2` |

| Action button | Endpoint | CASL permission |
|---------------|----------|-----------------|
| Edit | navigate to `/control-center/form-builder/{id}/edit` | `form_edit` |
| Duplicate | `POST .../{id}/duplicate` | `form_create` |
| Publish | `POST .../{id}/publish` | `form_publish` |
| Archive | `POST .../{id}/archive` | `form_publish` |
| Restore | `POST .../{id}/restore` | `form_publish` |
| Delete permanently | `DELETE .../{id}` (only if `submission_count == 0`) | `form_delete` |

| Status string | Backend source |
|---------------|----------------|
| `"draft"` | `status == FormStatus.draft (1)` and `deleted_at IS NULL` |
| `"published"` | `status == FormStatus.published (2)` and `deleted_at IS NULL` |
| `"archived"` | `deleted_at IS NOT NULL` (D-6) |

---

## 7. UI Design

### Layout

**Active tab:**
```
[ Active ] [ Archived ]                                 [ Create New Form ]

[ Search by name... ]  [ Status: All v ]  [ Type: All v ]

| Name             | Type         | Status    | Version | Last Updated      | Actions                  |
|------------------|--------------|-----------|---------|-------------------|--------------------------|
| > Household 2026 | Registration | Published | 2       | Jun 9, 2026 10:20 | Edit Duplicate Archive   |
|     Monitoring Q2| Monitoring   | Draft     | 1       | Jun 8, 2026 09:00 | Edit Duplicate Publish   |
```

**Archived tab:**
```
[ Active ] [ Archived ]

[ Search by name... ]  [ Type: All v ]

| Name             | Type         | Status   | Version | Archived          | Actions                       |
|------------------|--------------|----------|---------|-------------------|-------------------------------|
| Old Survey 2024  | Registration | Archived | 3       | Mar 2, 2026 14:00 | Restore  Delete permanently   |
| Pilot Form       | Registration | Archived | 1       | Jan 8, 2026 09:30 | Restore  [Delete permanently] |
```
(`[Delete permanently]` greyed out — that form has submissions.)

- Tabs map to the manager split (D-8): **Active** → `Forms.objects`; **Archived** → `?archived=true` (`Forms.objects_deleted`). Search/type filters apply within each tab.
- `>` marks an expandable registration row with monitoring children (Active tab, "all" mode only — see D-4).
- Status cell renders **Published**, **Draft**, or **Archived** (derived from `deleted_at`, D-6).
- Action set per row:
  - **Active** tab — Draft: **Publish** + **Archive**; Published: **Archive** (Publish hidden); plus **Edit** and **Duplicate** when permitted.
  - **Archived** tab — **Restore** always; **Delete permanently** only when `submission_count == 0` **and** the user has `form_delete` access (D-10, D-11), otherwise hidden/disabled with an explanatory tooltip.

### Confirmation Modals

| Action | Modal type | Content |
|--------|-----------|---------|
| Publish | `Modal.confirm` | "Publish this form? It becomes available for data collection." |
| Archive | `Modal.confirm` (warning) | "Archive this form? It will be removed from data collection (web and mobile) and moved to the Archived tab. This form has **N submissions** — they are preserved and remain viewable. You can restore it later." |
| Restore | `Modal.confirm` | "Restore this form? It returns as a **draft**; re-publish it to resume data collection." |
| Delete permanently | `Modal.confirm` (danger) | "Permanently delete this form? This cannot be undone. (Available only because the form has no submissions.)" |
| Duplicate | inline (no modal) or light confirm | Calls API, then refreshes; new `(Copy)` draft appears at top |

Submission count `N` comes from `submission_count` (T-2). When `N == 0`, the Archive warning omits the submission clause. The "Delete permanently" tooltip for a form with submissions reads: "Forms with submissions can't be deleted — keep it archived or restore it."

### State Management

Local React state, consistent with the existing `FormBuilderList.jsx` (no new Pullstate store). Filters/search live in component state; each change refetches page 1.

---

## 8. Security Considerations

- [x] Per-action permission gating enforced **both** server-side (`get_permissions` map, extended with `archive`/`restore` -> `form_publish`) and client-side (button visibility). Client gating is UX only; the server remains the authority.
- [x] Query params validated/normalized server-side; unknown `status`/`type` values are ignored (treated as "all") rather than erroring.
- [x] `submission_count` exposes only an aggregate integer — no submission content.
- [x] Archived forms leave data collection automatically via the default-manager swap; confirm `list_form`, mobile assignment forms, and `generate_config` all read through `Forms.objects` (the default manager) and not `objects_with_deleted`.
- [x] Archive is reversible and non-destructive (`soft_delete`). The permanent `DELETE` stays a hard-delete **only because** `destroy()` is changed to `hard_delete()` (D-9) — without that change the mixin would silently soft-delete instead. The 409-on-submissions guard is retained.
- [x] Permanent delete (Archived tab) is defence-in-depth gated: server enforces `form_delete` (superuser auto-included) + 409-on-submissions (D-9, D-11); the FE additionally hides the button unless `submission_count == 0` and the user has `form_delete` (D-10). The server remains authoritative — the FE gate is UX only.

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Backend unit | `get_queryset` filtering by `search`, `status`, `type`; combined filters; empty/invalid params fall back to all |
| Backend unit | List serializer embeds `children` only in "all" mode; `type=registration` suppresses children; `type=monitoring` returns flat monitoring rows with parent ref (D-4) |
| Backend unit | `submission_count` correct (0 and >0) |
| Backend unit | Search matches a child whose parent does not; parent returned as container with the matching child (D-5) |
| Backend integration | Pagination `total` counts the active mode's top-level rows; nested children excluded from the page count |
| Backend unit | Archive: `soft_delete()` succeeds even with submissions; form leaves `Forms.objects`; appears in `objects_deleted` |
| Backend unit | Restore: clears `deleted_at` **and** sets `status=draft` (D-7), regardless of prior status |
| Backend unit | DELETE on a form with no submissions **removes the row permanently** (hard delete, D-9) — regression guard that `destroy()` did not become a soft delete |
| Backend unit | DELETE on a form with submissions still returns 409 |
| Backend integration | Archived form is absent from `list_form`, mobile assignment forms, `parent.children`, and `generate_config` output (default-manager exclusion) |
| Backend unit | `Active` tab returns active forms; `?archived=true` returns only archived; serializer renders `status="archived"` (D-6, D-8) |
| Backend unit | DELETE permanently removes an **archived** form with no submissions (resolves via `objects_with_deleted`, D-10); 409 if it has submissions; 403 for users without `form_delete`; allowed for a non-superuser role granted `form_delete` (D-11) |
| Frontend | Debounced search triggers one refetch; filter change resets to page 1 |
| Frontend | Action buttons render per status + permission; Publish/Archive/Restore/Delete open the correct modal; confirm calls API + refreshes |
| Frontend | Expandable rows render monitoring children under parent in "all" mode |
| Frontend | Switching to the Archived tab loads `?archived=true`; rows expose Restore, and Delete permanently only when `submission_count == 0` and user has `form_delete` (D-10, D-11) |
| Frontend | Archive modal shows the numeric submission count; omits the clause at count 0 (Q-4) |

---

## 10. Compatibility & Migration

### Backward Compatibility
- [x] One additive migration: nullable `deleted_at` on `forms`, no backfill (all existing rows active). Behavior is unchanged until a form is archived.
- [x] Manager swap is safe at rest: with nothing archived, `Forms.objects` returns the same rows as before. Audit any code relying on `Forms.objects` to *include* would-be-archived rows (none exist today).
- [x] Existing `/manage/forms` consumers unaffected — new params are optional; `children`, `deleted_at`, and `submission_count` are additive fields.
- [x] CLI seeder unaffected (creates active forms; `deleted_at` defaults NULL).

### Mobile App Impact
- [x] Mobile consumes `/api/v1/forms`, mobile-assignment forms, and sync endpoints — all read through `Forms.objects` / related managers, so **archiving a form removes it from mobile automatically**. This is the intended behavior (a retired form should stop syncing). No SQLite schema change; no client code change.
- [x] Restoring a form (→ draft) keeps it out of mobile until it is re-published, consistent with normal draft behavior.

---

## 11. Resolved Questions

| # | Question | Resolution |
|---|----------|------------|
| Q-1 | How is Archive modeled? | **Soft-delete** — add `SoftDeletes` to `Forms`; Archive = `soft_delete()`, Restore = `restore()`→draft. Auto-hides from data collection via the default manager (D-1, D-7, D-8). Supersedes the earlier "unpublish" and "derive from published_at" approaches. |
| Q-2 | `type` filter vs expandable children | `registration` hides children; `monitoring` flattens to top-level rows with a parent column (D-4). |
| Q-3 | Search children; parent as container | **Yes** to both — child matches pull in their parent as a non-matching container (D-5). |
| Q-4 | Impact warning content | Show the **numeric submission count** (e.g. "This form has **134 submissions**…"); omit the clause when count is 0. |
| Q-5 | Children payload size | **Embed inline, no hard cap.** Children per registration form are inherently few (single digits); worst realistic page is ~10 parents × a handful of children. Use `prefetch_related("children")`. Revisit with lazy-load only if a single parent exceeds ~50 children. |

No open questions remain. Ready for `/sc:design` or implementation.

---

## 12. Scope Boundary

**In scope**: server-side search + status/type filters, `submission_count` exposure, `Forms` soft-delete + archive/restore endpoints, the `destroy()` → `hard_delete()` + `objects_with_deleted` change (D-9), the **Active / Archived tabs** with Restore and gated Delete-permanently (D-10), surfacing duplicate/publish/archive/restore/delete row buttons with modals, expandable hierarchy, per-action permission gating.

**Out of scope**: a `FormStatus.archived` enum value (rejected in favor of soft-delete); bulk/multi-select actions (future enhancement); the form editor itself (FB-003); the version-history drawer (already built).

---

## 13. References

- `doc/design/FB-001-form-builder-data-architecture.md` — status/type constants, snapshot model
- `doc/design/FB-002-form-builder-backend-crud-api.md` — duplicate / publish / unpublish endpoints, permission map
- `doc/design/FB-003-form-builder-frontend-integration.md` — editor integration, list page origin
- `frontend/src/pages/form-builder/FormBuilderList.jsx` — current list implementation
- `backend/api/v1/v1_forms/views.py` — `FormBuilderViewSet`, `get_permissions`, `list_form`, `unpublish`
- `backend/api/v1/v1_forms/serializers.py` — `ListFormSerializer`
- `backend/utils/soft_deletes_model.py` — `SoftDeletes` mixin reused for Archive
- `backend/api/v1/v1_forms/functions.py` — existing soft-delete usage for questions/groups (precedent)

---

## 14. Implementation Notes (deltas from this design)

Recorded after implementation so the design matches what shipped.

### Backend (commit `9d8e1998`)
- Migration: `0008_forms_deleted_at` adds the nullable `deleted_at` column; no backfill.
- `submission_count` is computed via the reverse manager (`obj.form_form_data.count()`), not a queryset annotation. This is an intentional N+1 over a ≤10-parent page plus its few children — acceptable per Q-5; revisit with `annotate(Count(...))` if pages grow heavy.
- `ListFormSerializer` adds `parent_name` (`obj.parent.name`) so the flattened monitoring view (D-4) can show the parent without a second request.
- `reset_forms` management command switched from `form.delete()` to `form.hard_delete()` — a ripple of the manager swap caught by `tests_reset_forms` (the soft-delete would have collided on PK at re-seed).
- Tests: `tests_manage_form_archive.py` (12) and `tests_manage_form_list_filters.py` (10). Full `v1_forms` (164) and `v1_mobile` (107) suites green; flake8 clean.

### Frontend (commit `df2a8b8a`)
- **Permission gating delta (D-10 / D-11)**: the design specifies the FE gates **Delete permanently** on `form_delete`. The frontend CASL model is coarse — it only exposes `can("manage", "form-builder")`, with **no granular `form_delete` signal** ([ability.js](../../frontend/src/components/can/ability.js)). The button is therefore FE-gated on **`is_superuser` + `submission_count === 0`**. The **backend remains authoritative** (`destroy` requires `form_delete`, D-11), so a non-superuser with the `form_delete` role can still delete via the API — they just won't see the button. **Follow-up**: expose `can_form_delete` per role in the login/user response and add it to `ability.js` to fully honor D-11 in the UI. Other actions (Publish/Archive/Duplicate) are not FE-gated beyond page access; a missing backend permission surfaces as an error toast.
- **Expand-by-default**: registration rows with monitoring children are expanded on load via controlled `expandedRowKeys` (recomputed whenever the list reloads); users can still collapse individual rows. Not in the original design — added on request.
- **Conditional expand icon**: a custom `expandable.expandIcon` renders the `+`/`−` toggle only for rows that actually have children, and a fixed-width spacer otherwise (keeps the Name column aligned).
- **Tabs glitch fix**: AntD renders a tab-overflow "more" node (`.ant-tabs-nav-operations`) whose `ResizeObserver` flickered the `-hidden` class with our two-tab bar. Hidden via a scoped rule in `style.scss` (two fixed tabs never overflow).
- Pagination envelope is the project-standard `{ current, total, total_page, data }`.

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan | | |
| Tech Lead | | | |
| Product | | | |
