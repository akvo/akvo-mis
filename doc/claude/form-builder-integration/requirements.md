# Requirements: Form Builder Frontend Integration (FB-003)

**Issue**: #228
**Branch**: `feature/228-integrate-akvo-react-form-editor-in-frontend`
**Depends on**: FB-002A — backend CRUD endpoints must be deployed

---

## User Acceptance Criteria

| # | Criterion |
|---|---|
| U-1 | Form Builder is accessible from the Control Center sidebar navigation |
| U-2 | Only users with form-builder permission (and superusers) can see and access the Form Builder |
| U-3 | Users can create a new form using the visual editor |
| U-4 | Users can edit existing forms using the visual editor |
| U-5 | Save operations show a loading state on the button while the request is in flight |
| U-6 | Successful save shows a success notification |
| U-7 | Failed save shows an error notification with a message |
| U-8 | Users can preview the form while editing (built into the editor component) |
| U-9 | In-progress edits are auto-saved locally so work is not lost on accidental navigation |
| U-10 | The Form Builder list shows all forms with name, type, and status (Draft / Published) |
| U-11 | When editing a published form, users see an info banner: "Editing a published form creates a new version snapshot. Click Publish to activate it." |
| U-12 | Users can unpublish a published form (hides it from data collection, allows corrections) and re-publish it when ready |

---

## Functional Requirements

### FR-1: Permission Gate

**Already done in FB-002A** — no backend changes needed for this branch.

- `can_form_builder()` property on `UserRole` returns `True` if the role has `form_view` access.
- `can_form_builder` field exposed via `UserRoleSerializer`.

**Frontend only**:
- `ability.js` must grant `can("manage", "form-builder")` when any role has `can_form_builder: true`.
- Superusers already have `can("manage", "all")`.
- The Private route and sidebar CASL check are already wired; they activate once the ability rule is added.

### FR-2: Form Builder List (`/control-center/form-builder`)

- Fetches all forms from `GET /api/v1/manage/forms` on mount.
- Displays a table with columns: **Name**, **Type** (Registration / Monitoring), **Status** (Draft / Published), **Actions**.
- Actions: "Edit" link → `/control-center/form-builder/:formId/edit`.
- Page header: "New Form" button → `/control-center/form-builder/create`.
- Loading skeleton while fetching.
- Empty state when no forms exist.

### FR-3: Create Form (`/control-center/form-builder/create`)

- Renders `akvo-react-form-editor` component with no initial value.
- "Save" button calls `editorToApi()` on the current editor state, then `POST /api/v1/manage/forms`.
- On success: shows `message.success`, clears the localStorage draft, navigates to `/control-center/form-builder/{response.data.id}/edit`.
- On error: shows `message.error` with server message or generic fallback.
- Auto-saves to localStorage key `form-builder-draft-new` (debounced 2 s).
- On mount: restores draft from localStorage if one exists, shows a dismissible "Draft restored" alert.

### FR-4: Edit Form (`/control-center/form-builder/:formId/edit`)

- Reads `formId` from URL params.
- On mount: fetches `GET /api/v1/manage/forms/:formId`, transforms via `apiToEditor()`, sets as editor initial value.
- If `form.status === "published"`: shows an Ant Design `<Alert type="info">` banner: "Editing a published form creates a new version snapshot. Click Publish to activate it."
- "Save" button calls `editorToApi()` then `PUT /api/v1/manage/forms/:formId`.
  - Response returns `version` (active, unchanged) and `latest_version` (incremented if a snapshot was created).
  - Shows `message.success`, clears localStorage draft, stays on the same edit page.
- On error: shows `message.error`.
- Auto-saves to localStorage key `form-builder-draft-${formId}` (debounced 2 s).
- Draft restore: if localStorage draft is newer than API fetch, use draft and show "Draft restored" alert.

### FR-5: Transformer (`frontend/src/lib/form-builder-transform.js`)

- `editorToApi(editorOutput)` — converts editor JSON to backend payload:
  - Recalculates `order` (1-based) by array index for groups and questions.
  - Maps question type strings: `"entity"` → `"cascade"` (backend rejects `"entity"`; `extra.type="entity"` is preserved); all others pass through.
  - Preserves existing `id` fields; passes `null` for new items.
  - Normalizes camelCase question fields to snake_case (`displayOnly` → `display_only`).
  - Normalizes `pre: {}` → `null`.
  - Generates option `value` from `label` (snake_case) if not provided.
- `apiToEditor(apiResponse)` — converts `GET /api/v1/manage/forms/{id}` response to editor initial value:
  - Runs snake_case → camelCase on question fields (`display_only` → `displayOnly`, etc.).
  - Resolves `"cascade"` + `extra.type === "entity"` back to `"entity"`.
  - Passes through `status`, `published_at`, `version`, `latest_version` at the top level (pages use these; the editor ignores them).

### FR-6: Publish Form

- A "Publish" button is shown in `FormBuilderEdit`.
- For **draft** forms: calls `POST /api/v1/manage/forms/{id}/publish` — creates first snapshot, sets `status=published`.
- For **published** forms with a pending snapshot (`latest_version > version`): same call activates the pending snapshot (`active_version` advances to `latest_version`).
- For **published** forms with no pending changes: same call is a no-op (returns `200`).
- On success: shows `message.success("Form published")`. Updates local `status` and `version` state from response.
- On error: shows `message.error` with server message.
- Button is available for users with `form_publish` permission.

### FR-7: Unpublish / Re-publish Form

- An **"Unpublish"** button is shown in `FormBuilderEdit` for published forms (users with `form_publish` permission).
- Calls `POST /api/v1/manage/forms/{id}/unpublish`.
  - On success: shows `message.success("Form unpublished")`. Updates local `status` to `"draft"`. Info banner in FR-4 changes to reflect draft status.
  - On error: `message.error`.
- When the form is unpublished (`status === "draft"` AND `published_at` is set), the "Publish" button (FR-6) doubles as the **re-publish** action — no separate button needed.
- Re-publish creates a new snapshot from live rows and restores `status=published` without overwriting `published_at`.

---

## Non-Functional Requirements

| # | Requirement |
|---|---|
| NF-1 | Auto-save must not block the UI; localStorage writes happen after a 2 s debounce |
| NF-2 | Transformer is pure JS — no React or Ant Design imports |
| NF-3 | All code must pass `yarn lint` and `yarn prettier` in the frontend container |
| NF-4 | No `// eslint-disable-next-line` comments — fix code to satisfy rules |
| NF-5 | Single complete payload per save. No chunking, batching across requests, or partial saves. Server-side batch queries (`in_bulk`, `prefetch_related`) handle large forms. |

---

## Out of Scope for FB-003

- Version history panel (list of `FormPublishedVersion` entries with `is_active` badge) — spec FB-003B
- Version rollback UI (`POST /api/v1/manage/forms/{id}/activate/{version_id}`) — spec FB-003B
- Duplicate form UI — spec FB-003B
- Form delete UI
- Question attribute configuration (chart/JMP/aggregate)
