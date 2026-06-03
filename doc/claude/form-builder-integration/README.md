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
- **Publish / Unpublish**: `POST .../publish` activates the latest snapshot (or creates one on first/re-publish). `POST .../unpublish` sets the form back to draft. Both are in scope for FB-003 (`FormBuilderEdit`).
- **`image` is canonical**: Both editor and backend use `"image"`. `editorToApi()` passes it through unchanged.
- **Show form status**: `FormBuilderList` shows a status badge (Draft / Published). `FormBuilderEdit` shows an info banner when editing a published form.
- **Auto-save to localStorage**: Drafts persist locally (debounced 2 s) under a per-form key. Cleared on successful backend save.
- **Superuser always has access**: Consistent with the rest of `ability.js`.
- **FB-003B (follow-on)**: Version history drawer showing `FormPublishedVersion` list with `is_active` badge and "Set as active" rollback using `POST .../activate/{version_id}`.
