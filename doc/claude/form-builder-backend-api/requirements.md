# Requirements: Form Builder Backend API

---

## User Acceptance Criteria

| # | Criterion |
|---|---|
| U-1 | Users can create a new form via API; it is saved as a draft |
| U-2 | Users can update a draft form (name, structure, questions) |
| U-3 | Users can publish a form to make it available for data collection |
| U-4 | Users can create a monitoring form linked to a published registration form |
| U-5 | Existing submissions remain linked to the correct form version when a form is edited post-publish |
| U-6 | Users can duplicate a form (creates a new draft copy) |
| U-7 | Users can list all versions of a form |
| U-8 | Users cannot update a published form directly — editing creates a new version |

---

## Functional Requirements

### FR-1: Form Status Lifecycle

Forms follow a two-state lifecycle:

```
DRAFT → PUBLISHED
```

- All newly created forms start as `DRAFT`.
- A `DRAFT` form can be updated freely via `PUT`.
- Once `PUBLISHED`, a form cannot be directly mutated. A `PUT` on a published form triggers version-on-edit (see FR-8).
- Existing forms in the database at migration time default to `PUBLISHED` (they are already live).

### FR-2: Create Form — `POST /api/v1/forms`

- Permission: `can_form_builder` or superuser (see [form-builder-integration/design.md § Permission Flow](../form-builder-integration/design.md)).
- Accepts `FormCreateSerializer` payload (nested: form → groups → questions → options).
- Creates all nested records in one atomic transaction.
- Sets `status = DRAFT`.
- Returns `201` with created form in `FormDetailSerializer` format.
- Returns `400` on validation errors with field-level detail.
- Returns `403` if user lacks permission.

### FR-3: Get Form — `GET /api/v1/forms/{id}`

- Returns the full form structure (same shape as existing `GET /api/v1/form/{id}`).
- Includes `status` and `version` fields in the response.
- Returns `404` if not found.
- No permission restriction beyond authentication — consistent with existing read endpoints.

### FR-4: Update Form — `PUT /api/v1/forms/{id}`

- Permission: `can_form_builder` or superuser.
- **Target is DRAFT**: Full replace of nested resources (same strategy as spec #228 §FR-7). Returns `200`.
- **Target is PUBLISHED**: Triggers version-on-edit (FR-8). Returns `201` with the new version.
- Accepts same `FormCreateSerializer` payload.
- Returns `403` if user lacks permission.
- Returns `404` if form not found.

### FR-5: Delete Form — `DELETE /api/v1/forms/{id}`

- Permission: superuser only.
- Soft approach: set `status = ARCHIVED` (if added) OR hard delete if no submissions exist; reject with `409 Conflict` if submissions reference this form.
- Returns `204` on success.
- Returns `403` if not superuser.
- Returns `409` if form has existing submissions.

_Note: Archiving is preferred over hard delete. If `ARCHIVED` status is not added in this iteration, block delete when submissions exist and return a meaningful error._

### FR-6: Publish Form — `POST /api/v1/forms/{id}/publish`

- Permission: `can_form_builder` or superuser.
- Target must be `DRAFT` — returns `400` if already `PUBLISHED`.
- Sets `status = PUBLISHED`, records `published_at = now()`.
- Returns `200` with the updated form.
- Returns `404` if not found.

### FR-7: Duplicate Form — `POST /api/v1/forms/{id}/duplicate`

- Permission: `can_form_builder` or superuser.
- Creates a deep copy: new `Forms` record + all `QuestionGroup`, `Questions`, `QuestionOptions` records.
- New form has: `status = DRAFT`, `version = 1`, `name = "{original name} (Copy)"`, new `uuid`.
- All question `name` fields on the copy must be unique within the new form (they are already globally unique to the original form; the copy gets new records so no collision).
- Returns `201` with the new draft form.

### FR-8: Version-on-Edit (Published Forms)

When a `PUT` targets a `PUBLISHED` form:

1. Create a new `Forms` record with: same `name`, `type`, `parent`, `uuid` (NEW uuid), `version = original.version + 1`, `status = DRAFT`.
2. Copy the existing nested structure from the original to the new record.
3. Apply the incoming payload changes to the new draft.
4. Return `201` with the new draft form.

The original published form is **not modified**. Existing `FormData` submissions continue pointing to the original form ID. The new draft must be published separately via `POST /api/v1/forms/{newId}/publish`.

_Version linkage: the `parent` FK on `Forms` is already used for registration/monitoring relationships. A separate `previous_version` FK is needed to track version chains. See [design.md § Version Linkage](design.md)._

### FR-9: List Versions — `GET /api/v1/forms/{id}/versions`

- Returns all forms in the version chain for the given form (same logical form, all versions).
- Response: array of `{ id, version, status, published_at, name }`.
- The chain is built by following `previous_version` links.
- Returns `404` if form not found.

### FR-10: Monitoring Form Validation

When creating or updating a form with `type = monitoring` and a `parent` value:
- `parent` must reference a `PUBLISHED` form with `type = registration`.
- Returns `400` with a descriptive error if parent is not published or not a registration form.

### FR-11: Canonical Question Type — `image`

`"image"` is the canonical type string for photo questions. `QuestionTypes.image = 8` in the backend constants.

- The backend accepts only `"image"` in API payloads. `"photo"` is rejected with a validation error.
- All form seed JSON files (`example-1.json`, `short-test-form.test.json`, `short-test-form.monitoring.test.json`) use `"image"`.
- The frontend `editorToApi()` transformer can pass `"image"` directly — no alias mapping needed.

### FR-12: Cache Invalidation

`signals.py` already connects `post_save` and `post_delete` on `Forms`, `QuestionGroup`, `Questions`, `QuestionOptions` to `cache.clear()`. New write endpoints trigger these signals automatically — no changes to `signals.py` required.

---

## Non-Functional Requirements

| # | Requirement |
|---|---|
| NF-1 | All write operations (create, update, duplicate, version-on-edit) must be wrapped in `django.db.transaction.atomic` |
| NF-2 | `GET /api/v1/forms/{id}` must not break existing clients — it should return the same structure as `GET /api/v1/form/{id}` plus `status` and `version` |
| NF-3 | Existing `GET /api/v1/form/{id}` (singular, used by mobile/web form rendering) must remain unchanged |
| NF-4 | All new endpoints must have test coverage: permission checks, validation errors, and happy-path |
| NF-5 | Migration must provide `status = PUBLISHED` as the default for all pre-existing `Forms` rows |
| NF-6 | Unique constraint `(form, name)` on `QuestionGroup` and `Questions` must be honoured; serializer must reject duplicate names within a form |

---

## Out of Scope

- Frontend changes (spec #228 handles those)
- Question attribute management (chart/JMP/aggregate) via editor
- Approval instruction editing
- Form archiving UI
- Webhook/notification on publish
