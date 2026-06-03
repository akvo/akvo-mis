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

### FR-3: Get Form — `GET /api/v1/manage/forms/{id}`

- Returns the full form structure.
- **Published form**: the response is built from the **latest `FormPublishedVersion` snapshot** (not live DB rows). This reflects the last PUT's data and avoids N+1 queries for large forms.
- **Draft form**: response is built from live DB rows via `FormDetailSerializer`.
- Includes `status`, `version` (active version number), and `latest_version` (highest snapshot version number).
- Returns `404` if not found.
- Permission: `form_view` or superuser.

### FR-4: Update Form — `PUT /api/v1/manage/forms/{id}`

- Permission: `can_form_builder` or superuser.
- **Draft form**: Updates the form record and nested resources directly (in-place). Returns `200`. `version` stays unchanged.
- **Published form**: does **not** touch live `Forms`, `QuestionGroup`, `Questions`, or `QuestionOptions` rows. Instead, calls `store_version_snapshot(form, data, user)` which stores the normalized payload as a new `FormPublishedVersion` schema. Returns `200` built from the new snapshot.
- `active_version` is **not** changed by PUT on a published form. Live rows continue to reflect the currently active version until an explicit `activate()` call.
- `version` is server-managed — values in the PUT payload are ignored.
- Accepts same `FormCreateSerializer` payload (partial). If `question_group` is absent from the payload, the new snapshot inherits `question_group` from the current active version's schema.
- The view calls `_normalize_editor_payload(request.data)` before validation to translate `akvo-react-form-editor` field names (`question_groups`, `questions`, `options`, `repeatText`, `displayOnly`, `photo` type) to backend conventions.
- Returns `403` if user lacks permission.
- Returns `404` if form not found.

### FR-5: Delete Form — `DELETE /api/v1/forms/{id}`

- Permission: superuser only.
- Soft approach: set `status = ARCHIVED` (if added) OR hard delete if no submissions exist; reject with `409 Conflict` if submissions reference this form.
- Returns `204` on success.
- Returns `403` if not superuser.
- Returns `409` if form has existing submissions.

_Note: Archiving is preferred over hard delete. If `ARCHIVED` status is not added in this iteration, block delete when submissions exist and return a meaningful error._

### FR-6: Publish Form — `POST /api/v1/manage/forms/{id}/publish`

- Permission: `can_form_builder` or superuser.
- **Draft → Published transition** (primary use): calls `create_published_version(form, user, activate=True)`, which creates a `FormPublishedVersion` snapshot from the live DB rows, sets `status = PUBLISHED`, records `published_at = now()`, sets `active_version` to the new snapshot, and syncs `Forms.version`.
- **Already-published form**: activates the latest existing snapshot. Finds the latest `FormPublishedVersion` (created by any previous PUT) and calls `restore_from_snapshot(form, latest_pv)` if it is not already active. Does **not** create a new snapshot. This is the "I'm ready to go live with my pending edits" action.
- `status` and `published_at` are never changed after the first publish.
- Returns `200` with the updated form (includes `active_version_id`).
- Returns `404` if not found.

### FR-7: Duplicate Form — `POST /api/v1/forms/{id}/duplicate`

- Permission: `can_form_builder` or superuser.
- Creates a deep copy: new `Forms` record + all `QuestionGroup`, `Questions`, `QuestionOptions` records.
- New form has: `status = DRAFT`, `version = 1`, `name = "{original name} (Copy)"`, new `uuid`.
- All question `name` fields on the copy must be unique within the new form (they are already globally unique to the original form; the copy gets new records so no collision).
- Returns `201` with the new draft form.

### FR-8: Version History via Snapshots (FB-002A)

Version history is managed through `FormPublishedVersion` snapshots (see [FB-002A](../form-builder-version-schema/README.md)):

- A new `FormPublishedVersion` record is created in two situations:
  1. `POST .../publish` on a **draft** form — creates snapshot from live DB rows and activates it.
  2. `PUT /manage/forms/{id}` on a **published** form — `store_version_snapshot` stores the payload as a new snapshot without touching live rows.
- `Forms.version` equals the **active version's** version number (synced by `restore_from_snapshot` and first-publish). A separate `latest_version` field (serializer-computed) shows the highest snapshot version number. These two values can diverge when PUT has created new snapshots not yet activated.
- `Forms.active_version` points to the snapshot currently used for data collection. Live `QuestionGroup`/`Questions` rows always reflect this version exactly.
- PUT always operates in-place on the same `Forms` record; the form ID never changes.

**Invariant**: live question rows (`QuestionGroup`, `Questions`, `QuestionOptions`) always equal the active version's schema. They are only modified by `activate()` and first `publish`.

### FR-9: List Versions — `GET /api/v1/manage/forms/{id}/versions`

- Returns all `FormPublishedVersion` snapshots for the form, ordered by `version` ascending.
- Response: array of `{ id, version, published_at, published_by, is_active }`.
- `is_active` is `true` for the snapshot currently pointed to by `Forms.active_version`.
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

### FR-14: Publish / Unpublish a Form

A published form can be **unpublished** to hide it from data collection and
allow corrections. Re-publishing restores visibility. Uses the existing
`status` field — no new DB column.

**`publish` action** (`POST /api/v1/manage/forms/{id}/publish`) handles all
publish transitions:

1. **Draft, never published** (`published_at is None`): calls
   `create_published_version(form, user, activate=True)`. Creates snapshot
   from live rows, sets `status=published`, records `published_at=now()`.
2. **Draft, re-publish after unpublish** (`published_at` is set): calls
   `create_published_version(form, user, activate=True)`. Creates new snapshot
   from current live rows and restores `status=published`. `published_at` is
   NOT overwritten — `create_published_version` guards on
   `form.published_at is None`.
3. **Already published + pending PUT snapshots**: calls
   `restore_from_snapshot(form, latest_pv)` to activate the latest snapshot.
   No new snapshot created.
4. **Already published, nothing pending**: no-op.

**`unpublish` action** (`POST /api/v1/manage/forms/{id}/unpublish`):

1. Returns `400` if `form.status != published`.
2. If the latest `FormPublishedVersion` differs from `active_version`
   (unactivated PUT snapshots exist), calls `restore_from_snapshot(form,
   latest_pv)` to sync live rows to the latest intended state.
3. Sets `form.status = FormStatus.draft`.
4. Returns updated `FormDetailSerializer` response.

While unpublished (`status = draft`), the form is hidden from `list_form` /
`web_form_details` / `form_data` and fully editable via draft PUT.

`published_at` is set once on first-ever publish. `create_published_version`
must guard on `form.published_at is None` (not `form.status`) to prevent
overwriting it on re-publish after unpublish.

Both endpoints require `can_form_builder` or superuser (mapped to
`form_publish` access in `get_permissions()`).

### FR-13: Granular Permission Foundation (anticipates FB-009)

To allow FB-009 ("Update Permission System") to add per-operation access control without backend schema changes, the backend defines five granular `FeatureAccessTypes` now:

| Access Type | Constant | Guards |
|---|---|---|
| `form_view` | 3 | `GET /api/v1/forms/{id}`, `GET /api/v1/forms/{id}/versions` |
| `form_create` | 4 | `POST /api/v1/forms`, `POST /api/v1/forms/{id}/duplicate` |
| `form_edit` | 5 | `PUT /api/v1/forms/{id}` |
| `form_publish` | 6 | `POST /api/v1/forms/{id}/publish` |
| `form_delete` | 7 | `DELETE /api/v1/forms/{id}` (superuser gate still applies) |

Each view already enforces the correct granular type. FB-009 only needs to add a role management UI to assign these types to roles.

No migration needed between this spec and FB-009 — the DB schema already accepts any integer for the `access` field.

### FR-12: Cache Invalidation

`signals.py` already connects `post_save` and `post_delete` on `Forms`, `QuestionGroup`, `Questions`, `QuestionOptions` to `cache.clear()`. New write endpoints trigger these signals automatically — no changes to `signals.py` required.

Additionally, the `web_form_details` and `form_data` cache keys now embed `v{instance.version}` (e.g. `webform-42-1-v3`, `form-42-v3`). This means that any operation which bumps `Forms.version` (i.e. every `create_published_version` call) automatically bypasses the stale cache entry without requiring an explicit cache clear.

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
| NF-7 | `_build_schema_snapshot` (called on first publish) must use `prefetch_related` to load groups → questions → options in 3 DB queries regardless of form complexity |
| NF-8 | `GET /api/v1/manage/forms/{id}` on a published form must resolve in ≤ 3 DB queries regardless of form complexity (form row + latest snapshot + batch disable_delete check) |
| NF-9 | `save_form` (draft PUT) must batch-load existing questions and groups using `filter(id__in=all_ids).in_bulk()` before the group loop — one query for all groups, one for all questions — instead of one query per item. `QuestionOptions` for all questions must similarly be deleted in one batched `filter(question__in=questions).delete()` call. |
| NF-10 | Request payload size for a typical large form (~100 questions, ~200 options) is approximately 75–150 KB — well within Django's default `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5 MB). No frontend chunking or payload splitting is required or permitted; the backend must process the complete form as a single atomic payload. |

---

## Out of Scope

- Frontend changes (spec #228 handles those)
- Question attribute management (chart/JMP/aggregate) via editor
- Approval instruction editing
- Form archiving UI
- Webhook/notification on publish
