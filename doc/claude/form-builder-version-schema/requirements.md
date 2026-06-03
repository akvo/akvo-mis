# Requirements: Form Schema Versioning (FB-002A)

---

## Functional Requirements

### Soft-Delete (Questions and Question Groups)

**FR-1** — When a PUT request includes `allow_delete: true`, questions and question groups absent from the payload must be **soft-deleted** (sets `deleted_at` via the `SoftDeletes` mixin) instead of hard-deleted from the database.

**FR-2** — Soft-deleted questions and question groups must not appear in any API response, form editor view, or data collection form. All read paths must filter `deleted_at__isnull=True`.

**FR-3** — Soft-deleted questions must remain in the database permanently. They must not be cleaned up automatically. This ensures historical `Answers` records retain a valid FK reference and `FormPublishedVersion` snapshots remain accurate.

**FR-4** — A new question or group may reuse the name of a soft-deleted one on the same form (conditional unique constraint: `condition=Q(deleted_at__isnull=True)`).

---

### Published Version Snapshots

**FR-5** — A `FormPublishedVersion` record must be created in two situations:
  1. `POST /api/v1/manage/forms/{id}/publish` on a **draft** form — explicit draft→published transition; calls `create_published_version(activate=True)`.
  2. `PUT /api/v1/manage/forms/{id}` on a **published** form — calls `store_version_snapshot(form, data, user)`. The payload is stored as the schema. No live `QuestionGroup`/`Questions` rows are modified.

**FR-6** — `Forms.active_version` and `Forms.version` are updated **only** on:
  - First publish (draft→published): sets `active_version = new snapshot`, `version = 1`, `status = published`, `published_at = now()`.
  - Explicit `POST .../activate/{version_id}`: calls `restore_from_snapshot(form, pv)` which applies the snapshot to live rows and sets `active_version = pv`, `version = pv.version`.
  - `POST .../publish` on an already-published form: activates the latest existing snapshot (same as calling `activate(latest_version_id)`) — does NOT create a new snapshot.

  PUT on a published form creates a snapshot but does **not** change `active_version` or `Forms.version`.

**FR-7** — Published version snapshots are **immutable** once created. They must never be modified.

**FR-8** — There is no limit on the number of published versions per form.

---

### Active Version and Data Collection

**FR-9** — The web form endpoint (`GET /api/v1/form/web/{id}`) and mobile/flat form endpoint (`GET /api/v1/form/{id}`) serve from live question tables (`WebFormDetailSerializer` / `FormDataSerializer`). This is correct because the live rows always equal the active version's schema (invariant maintained by `restore_from_snapshot` and first publish). No special snapshot-routing logic is needed in these endpoints.

**FR-10** — If `form.active_version` is null (form is draft or has never been published), these endpoints must return `404`.

**FR-11** — When a new `FormData` record is created (form submission), `FormData.published_version` must be set to `form.active_version` at the time of submission.

**FR-12** — Historical submissions must be renderable using `FormData.published_version.schema`, even if the form has been edited or questions deleted since collection.

---

### Version List and Rollback

**FR-13** — `GET /api/v1/manage/forms/{id}/versions` must return all `FormPublishedVersion` records for the form, ordered by `version` ascending. Each entry includes `id`, `version`, `published_at`, `published_by`, and `is_active` (true when matching `form.active_version`).

**FR-14** — `POST /api/v1/manage/forms/{id}/activate/{version_id}` must perform a structural rollback to the specified `FormPublishedVersion` via `restore_from_snapshot(form, pv)`:
  - Pass 1: soft-delete all currently-active questions and groups absent from the snapshot.
  - Pass 2: restore rows present in the snapshot. For each group/question ID: if the row exists in the DB (active or soft-deleted), call `qs.restore()` then update fields. If the ID does not exist in the DB (editor-generated timestamp ID from a PUT snapshot), create a new row.
  - Restore `form.name` and `form.approval_instructions` from the snapshot.
  - Set `form.active_version = pv`, `form.version = pv.version`.
  
  After this call, live rows exactly match the snapshot. New submissions use that version's schema.

---

## Non-Functional Requirements

**NFR-1** — Soft-deleted rows must not break existing queries or API responses. All queryset reads on `question_group_question` and `form_question_group` must default to filtering `deleted_at__isnull=True` (handled automatically by the `SoftDeletes` default manager).

**NFR-2** — Snapshot creation during `publish` must be wrapped in `@transaction.atomic`. A failed snapshot must roll back the entire publish operation.

**NFR-3** — Backward compatibility: `FormData` records created before FB-002A have `published_version = null`. These must not cause errors in any existing data API. Treat `null` as "schema unknown" and fall back to the current live question tables.

**NFR-4** — The `activate` endpoint must validate that the specified `FormPublishedVersion` belongs to the form in the URL. A mismatch must return `404`.

**NFR-5** — `restore_from_snapshot` must batch-load existing groups and questions in 2 queries (one `QuestionGroup.objects_with_deleted.filter(form=form)`, one `Questions.objects_with_deleted.filter(question_group__form=form)`) before the two-pass loop. Per-item lookups inside the loop are prohibited. Options for all questions in the snapshot must be bulk-deleted and bulk-created rather than one per question.

---

## Out of Scope (FB-002A)

- **`published → draft` as a full revert**: Making a published form fully editable again (same as if it was never published) is not the intended use. Use the `unpublish` action instead — `unpublish` sets `status=draft`, which hides the form from data collection and allows live-row edits via draft PUT, then `publish` creates a fresh snapshot and restores `status=published`.
- **Snapshot diffing / changelog**: Showing a diff between two published versions — deferred.
- ~~**Restoring live question rows from a snapshot**~~: Implemented — `restore_from_snapshot` performs a two-pass structural restore (see FR-14).
- **Purging old soft-deleted rows**: No cleanup mechanism is planned. Rows accumulate indefinitely.
- **Mobile `generate_sqlite` update**: Using `active_version.schema` as the question source for SQLite generation is noted but can follow in a separate sub-task.
- **`allow_delete` permission restriction to superuser**: The UI layer (FB-003/FB-009) is responsible for hiding this from non-superusers.
