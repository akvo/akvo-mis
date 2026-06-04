# Form Builder Frontend Integration (FB-003)

## Overview

This feature integrates `akvo-react-form-editor` into the frontend Control Center, giving users with form-builder permission a visual editor to create and edit forms. It consumes the real CRUD API delivered in [FB-002 / FB-002A](../form-builder-backend-api/README.md).

**GitHub Issue**: #228
**Branch**: `feature/228-integrate-akvo-react-form-editor-in-frontend`
**Depends on**: FB-002A (`feature/229-fb-002-implement-backend-form-crud-api`) — must be merged before this branch starts

---

## Problem Statement

Forms are currently defined only through backend seeders and raw JSON files. There is no in-product UI for creating or editing forms — every form change requires developer access to the backend. This blocks non-developer admins from iterating on survey design.

---

## Scope — Frontend Only

| Layer | What changes |
|---|---|
| Frontend — permissions | Add `can("manage", "form-builder")` rule to `ability.js` using the `can_form_builder` flag already in the user API |
| Frontend — pages | Implement `FormBuilderList`, `FormBuilderCreate`, `FormBuilderEdit` (currently empty scaffolds) |
| Frontend — lib | Create `form-builder-transform.js` with `editorToApi()` and `apiToEditor()` converters |

All form CRUD endpoints are provided by FB-002A. Version history and rollback UI are scoped to **FB-003B**.

### Already Implemented in FB-002A (no changes needed)

- Routes `/control-center/form-builder`, `.../create`, `.../:formId/edit` — `App.js`
- Sidebar nav item with CASL check — `sidebar/index.jsx`
- `menuFormBuilder` UI text key — `ui-text.js`
- `akvo-react-form-editor@^2.0.3` installed — `frontend/package.json`
- Backend `FeatureTypes.form_builder = 2` and five granular `FeatureAccessTypes` (`form_view=3` … `form_delete=7`) — `v1_profile/constants.py`
- `can_form_builder()` property on `UserRole` model — `v1_profile/models.py`
- `can_form_builder` field in `UserRoleSerializer` — `v1_users/serializers.py`
- Page stubs exported in `pages/index.js`

---

## Documents in This Directory

| File | Purpose |
|---|---|
| [README.md](README.md) | This file — initiative overview |
| [requirements.md](requirements.md) | User AC and functional/non-functional requirements |
| [design.md](design.md) | Architecture, design decisions, data mapping |
| [implementation-plan.md](implementation-plan.md) | Step-by-step task breakdown with file targets |

---

## Key Decisions

- **Backend API base path**: All manage endpoints are under `/api/v1/manage/forms` (not `/api/v1/forms`). Public read-only form endpoints remain under `/api/v1/forms`.
- **Snapshot-based versioning for published forms**: `PUT /api/v1/manage/forms/{id}` on a published form does NOT modify live rows. It stores the payload as a `FormPublishedVersion` snapshot. The response returns `version` (active, unchanged) and `latest_version` (incremented). The live form only updates when the user calls `POST .../publish` again, which activates the pending snapshot.
- **PUT always returns 200**: The form ID never changes. `FormBuilderEdit` stays on the same page after save.
- **Publish / Unpublish**: `POST .../publish` activates the latest snapshot (or creates one on first/re-publish). `POST .../unpublish` sets the form back to draft. Both implemented in `FormBuilderEdit`.
- **Version History Drawer**: `GET .../versions` and `POST .../activate/{version_id}` are implemented in `FormBuilderEdit` — a Drawer shows all snapshots with an "Set Active" button per non-active row. After activation the editor reloads with the restored content. (Originally scoped to FB-003B.)
- **Version Preview (editor reload pattern)**: Clicking "Preview" on a non-active version row fetches `GET /manage/forms/{id}/versions/{version_id}` (returns `FormPublishedVersionSerializer` + `schema` field), closes the drawer, and remounts the editor with the snapshot content via `apiToEditor()`. A dismissible "Previewing v{n}" banner with a "Back to saved" button restores the real saved state. Preview is purely local — no activate endpoint is called.
- **`image` is canonical**: Both editor and backend use `"image"`. `editorToApi()` passes it through unchanged.
- **Show form status**: `FormBuilderList` shows a status badge (Draft / Published). `FormBuilderEdit` shows an info banner when editing a published form.
- **Auto-save to localStorage**: Drafts persist locally (debounced 2 s) under a per-form key. Cleared on successful backend save.
- **Superuser always has access**: Consistent with the rest of `ability.js`.
- **i18n: all strings in `ui-text.js`**: Every user-visible string in form builder pages and sub-components is defined as a `formBuilder*` key. Dynamic strings use function keys (e.g. `formBuilderPreviewingBanner: (v) => ...`). Sub-components receive `text` as a prop — no direct store subscriptions.
- **Stale draft detection via `formVersion`**: The draft JSON stored in localStorage includes the form's active `version` at save time. On restore, if the stored version differs from the API version, the draft is silently discarded. This prevents stale seeder/test data from appearing in the editor when `published_at` is null. A "Load from server" button on the draft alert gives users an explicit reset path.
- **Preview remount via null-first pattern**: `WebformEditor` ignores `initialValue` prop changes after mount. Passing `null` unmounts the editor (renders `<Spin>`); the subsequent non-null value triggers a fresh mount with the new content. Used in `onPreview`, `onActivateVersion`, and `onExitPreview`.
- **Reusable sub-components**: `FormStatusTag`, `FormEditorBanners`, and `VersionHistoryDrawer` are extracted into `pages/form-builder/components/` to reduce page-level complexity and enable reuse across Create/Edit/List pages.
