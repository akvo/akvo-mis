# Feature Design Document: Form Schema Versioning

**Task ID**: FB-002B (previously called FB-002A in branch; renamed to avoid collision with [[FB-002A]])
**Author**: Iwan
**Date**: 2026-06-08
**Status**: Partially implemented (Groups A–E done; Groups F–G pending)

---

## 1. Context & Problem Statement

```
After FB-002, PUT always updates a form in-place. A published form's questions can be
edited and deleted freely (with allow_delete=true). The version integer on Forms increments
but there is no frozen snapshot of the question structure for any given version.

FormData currently only stores form_id. If a question is deleted after data was collected
against it, the answer records become orphaned — the question row is gone and there is no
way to reconstruct what the respondent was answering.

Before FB-002B:
  Form v1 published → user submits answers for question B
  Editor deletes question B (allow_delete=true)
  → Answer for B is orphaned: no question row, no label, no type

After FB-002B:
  Form v1 published → FormPublishedVersion v1 created (includes B)
  FormData.published_version = v1
  Editor deletes question B (soft-deleted, row preserved)
  → Answer for B still rendered via FormData.published_version.schema

Goals:
1. At publish time, freeze the form's complete question structure as a snapshot
2. FormData records reference the exact published version active at submission time
3. Form editor remains fully mutable between publishes
4. Users can choose which published version is "active" (rollback)
5. Historical submissions can be browsed and rendered per version
```

---

## 2. Requirements

### Functional Requirements

#### Soft-Delete

- **FR-1** — `allow_delete: true` on PUT: questions/groups absent from payload are soft-deleted (`deleted_at = now()`) not hard-deleted
- **FR-2** — Soft-deleted rows must not appear in any API response, editor view, or data collection form (all reads filter `deleted_at__isnull=True`)
- **FR-3** — Soft-deleted questions must remain in DB permanently (historical `Answers` FKs stay valid)
- **FR-4** — A new question/group may reuse the name of a soft-deleted one on the same form (conditional unique constraint: `condition=Q(deleted_at__isnull=True)`)

#### Published Version Snapshots

- **FR-5** — A `FormPublishedVersion` is created in two situations:
  1. `POST .../publish` on a draft form — calls `create_published_version(activate=True)`
  2. `PUT /manage/forms/{id}` on a published form — calls `store_version_snapshot(form, data, user)`
- **FR-6** — `Forms.active_version` and `Forms.version` updated ONLY on: first publish, explicit `activate`, or `POST .../publish` on already-published (activates latest snapshot)
- **FR-7** — Published version snapshots are immutable once created
- **FR-8** — No limit on published versions per form

#### Active Version and Data Collection

- **FR-9** — Web/mobile form endpoints serve from live question tables (which always equal the active version — the invariant)
- **FR-10** — If `form.active_version` is null, `GET /form/{id}` and `GET /form/web/{id}` return 404
- **FR-11** — New `FormData` records must set `published_version = form.active_version` at submission time
- **FR-12** — Historical submissions must be renderable using `FormData.published_version.schema`

#### Version List and Rollback

- **FR-13** — `GET .../versions` returns all `FormPublishedVersion` records ordered by `version` ascending; each entry includes `id`, `version`, `published_at`, `published_by`, `is_active`
- **FR-14** — `POST .../activate/{version_id}` calls `restore_from_snapshot(form, pv)`: Pass 1 soft-deletes active rows absent from snapshot; Pass 2 restores/creates snapshot rows; restores `form.name` and `form.approval_instructions`

### Non-Functional Requirements

- **NFR-1** — Soft-deleted rows must not break existing queries (SoftDeletes default manager auto-filters)
- **NFR-2** — Snapshot creation wrapped in `@transaction.atomic`
- **NFR-3** — `FormData` with `published_version=null` (pre-FB-002B submissions) treated as "schema unknown" — falls back to live question tables
- **NFR-4** — `activate` validates that the specified version belongs to the form in the URL (404 on mismatch)
- **NFR-5** — `restore_from_snapshot` must batch-load all groups/questions in 2 queries before the loop; options bulk-deleted and bulk-created

### Technical Acceptance Criteria

- [x] `QuestionGroup` and `Questions` extend `SoftDeletes` mixin (`deleted_at` field added)
- [x] Conditional `UniqueConstraint(condition=Q(deleted_at__isnull=True))` replaces `unique_together`
- [x] `FormPublishedVersion` model created
- [x] `Forms.active_version` FK added (nullable)
- [x] `FormData.published_version` FK added (nullable, backward compat)
- [x] `_build_schema_snapshot()`, `create_published_version()`, `store_version_snapshot()`, `restore_from_snapshot()` in `functions.py`
- [x] `_build_schema_snapshot()` stores lowercase type strings (`.lower()`)
- [x] `_build_schema_snapshot()` includes `variable_name` and `description` in snapshot
- [x] `restore_from_snapshot()` maps `entity`/`administration` type strings → `cascade` via `_TYPE_ALIAS`
- [x] `_form_detail_from_snapshot()` returns `variable_name` per question and `description` at form level
- [x] `FormPublishedVersionSerializer` (replaces `FormVersionSerializer`)
- [x] `GET .../versions` returns `FormPublishedVersion` records
- [x] `POST .../activate/{version_id}` calls `restore_from_snapshot`
- [x] `_to_editor_format()` applied to all `FormBuilderViewSet` responses (camelCase conversion for editor round-trip)
- [ ] `GET /form/{id}` and `GET /form/web/{id}` return 404 when `active_version` is null (Group F)
- [ ] `FormData.published_version` set on submission (Group G)

---

## 3. Data Model Changes

### Changes to `QuestionGroup` and `Questions`

Both models extend the project-standard `SoftDeletes` mixin:

```python
from utils.soft_deletes_model import SoftDeletes

class QuestionGroup(SoftDeletes):
    ...

class Questions(SoftDeletes):
    ...
```

The mixin adds `deleted_at = DateTimeField(null=True)` and provides:
- `objects` — default manager, auto-filters `deleted_at__isnull=True`
- `objects_deleted` — only deleted rows
- `objects_with_deleted` — all rows
- `.soft_delete()`, `.hard_delete()`, `.restore()`

Conditional unique constraint (replaces `unique_together`):
```python
models.UniqueConstraint(
    fields=["form", "name"],
    condition=models.Q(deleted_at__isnull=True),
    name="unique_active_form_question",
)
```

### New Model: `FormPublishedVersion`

```python
class FormPublishedVersion(models.Model):
    form = models.ForeignKey(
        Forms,
        on_delete=models.CASCADE,
        related_name="published_versions",
    )
    version = models.IntegerField()           # auto-increment per form
    schema = models.JSONField()               # complete snapshot (see below)
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        "v1_users.SystemUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="published_form_versions",
    )

    class Meta:
        unique_together = ("form", "version")
        ordering = ["form", "version"]
        db_table = "form_published_version"
```

### Changes to `Forms`

```python
active_version = models.ForeignKey(
    "FormPublishedVersion",
    on_delete=models.SET_NULL,
    related_name="active_for_forms",
    null=True,
    blank=True,
    default=None,
)
```

`Forms.version` is always synced with `create_published_version` — never incremented in `save_form`.

### Changes to `FormData`

```python
published_version = models.ForeignKey(
    "v1_forms.FormPublishedVersion",
    on_delete=models.SET_NULL,
    related_name="form_data",
    null=True,
    blank=True,
    default=None,
)
```

`null` for submissions collected before FB-002B deployment (backward compat — treated as "schema unknown").

### Migration Strategy

1. `0008_*` — adds `deleted_at DateTimeField(null=True)` to `QuestionGroup`/`Questions`; replaces constraints
2. `0009_*` — creates `FormPublishedVersion` table; adds `Forms.active_version` FK
3. `0004_*` (v1_data) — adds `FormData.published_version` FK

No data migration needed — `active_version` and `published_version` start null; existing published forms remain functional (fall back to live rows).

---

## 4. API Contract

### Schema Snapshot Format

`FormPublishedVersion.schema` is immutable once created:

```json
{
  "version": 2,
  "name": "Household Survey 2026",
  "description": null,
  "approval_instructions": null,
  "question_group": [
    {
      "id": 1,
      "name": "household_info",
      "label": "Household Information",
      "order": 1,
      "repeatable": false,
      "repeat_text": null,
      "question": [
        {
          "id": 10,
          "order": 1,
          "name": "head_of_household",
          "label": "Head of Household",
          "type": "input",
          "meta": true,
          "required": true,
          "rule": null,
          "dependency": null,
          "dependency_rule": "AND",
          "api": null,
          "extra": null,
          "tooltip": null,
          "fn": null,
          "pre": null,
          "display_only": false,
          "variable_name": null,
          "option": []
        }
      ]
    }
  ]
}
```

`disable_delete` is intentionally absent — that is a live-editor concern.

**Type strings in snapshots are always lowercase** (e.g., `"input"`, `"cascade"`). `_build_schema_snapshot` applies `.lower()` to `QuestionTypes.FieldStr.get(q.type)`. `store_version_snapshot` receives types already lowercased via `editorToApi()`. Both snapshot creation paths are consistent.

### Snapshot Creation Sources

| Creator | Trigger | Source |
|---|---|---|
| `create_published_version(activate=True)` | First `POST .../publish` on draft | Live DB rows via `_build_schema_snapshot` |
| `store_version_snapshot(form, data, user)` | `PUT` on published form | Normalized PUT payload; missing fields inherited from active version's schema |

### `GET .../versions/{version_id}` Response

```json
{
  "id": 3,
  "version": 2,
  "published_at": "2026-06-03T10:00:00Z",
  "published_by": "admin@akvo.org",
  "is_active": true,
  "schema": { ... }
}
```

The `schema` field is only included in the `version_detail` action (not in the list).

### Lifecycle Diagram

```mermaid
sequenceDiagram
    participant Editor as Form Editor
    participant BE as Backend
    participant DB as Database

    Editor->>BE: POST /manage/forms (create draft)
    BE->>DB: INSERT Forms (status=draft, active_version=null)

    Editor->>BE: POST /manage/forms/{id}/publish
    BE->>DB: INSERT FormPublishedVersion (version=1, schema=snapshot)
    BE->>DB: UPDATE Forms SET active_version=pv1, version=1, status=published

    Editor->>BE: PUT /manage/forms/{id} (edit — published)
    note over BE,DB: snapshot-only path
    BE->>DB: INSERT FormPublishedVersion (version=2, schema=payload)
    note over BE,DB: active_version still = pv1; live rows unchanged

    Editor->>BE: POST /manage/forms/{id}/publish (make edits live)
    BE->>DB: restore_from_snapshot(form, pv2)
    BE->>DB: UPDATE Forms SET active_version=pv2, version=2

    Editor->>BE: POST /manage/forms/{id}/activate/{pv1.id}
    BE->>DB: restore_from_snapshot(form, pv1)
    BE->>DB: UPDATE Forms SET active_version=pv1, version=1
```

---

## 5. Decision Log

### D-1: Web/Mobile Endpoints Return 404 When `active_version` is Null

Draft forms are not accessible for data collection until published. `GET /api/v1/form/{id}` and `GET /api/v1/form/web/{id}` return 404 when `active_version` is null.

---

### D-2: Live Rows Are Always the Single Source of Truth for Data Collection

`active_version` changes only in two cases: (1) first publish, (2) explicit `activate()`. PUT on a published form creates a snapshot for history but does NOT touch `active_version` or live rows.

`POST .../publish` on an already-published form activates the latest existing snapshot (no new snapshot created) — semantics: "make my pending PUT edits live". After `activate`/`publish`, live rows exactly match the active snapshot. No special snapshot-routing logic needed in web/mobile form endpoints.

---

### D-3: `GET .../versions` Reused for `FormPublishedVersion` Records

The old `versions` action walked the `previous_version` FK chain (never populated after FB-002). After FB-002B it returns all `FormPublishedVersion` rows. `FormVersionSerializer` replaced by `FormPublishedVersionSerializer`. No new endpoint.

---

### D-4: `allow_delete=true` → Soft-Delete, Not Hard-Delete

| `allow_delete` | Question has no answers | Question has answers |
|---|---|---|
| `false` (default) | Hard-delete (`.hard_delete()`) | Return 400 |
| `true` | Soft-delete (`deleted_at = now()`) | Soft-delete (`deleted_at = now()`) |

Soft-deleted rows: invisible to all API responses; preserved so `Answers` FKs remain valid; captured in snapshots created before deletion; not captured in new snapshots.

Rolling back to a snapshot that included a now-soft-deleted question: `active_version.schema` still contains the definition; new `Answers` can reference the soft-deleted question ID because the row still exists.

---

### D-5: `restore_from_snapshot` Handles Editor-Generated IDs

`POST .../activate/{version_id}` calls `restore_from_snapshot` — a two-pass structural restore:
- Pass 1: soft-delete active rows absent from snapshot
- Pass 2: restore snapshot rows via `objects_with_deleted`. If `restore()` returns 0 (ID not in DB — e.g., editor-generated timestamp ID from a PUT snapshot), the row is **created** instead

This ensures any snapshot can be activated regardless of whether its question IDs exist in the live tables.

---

### D-6: Live Rows = Active Version Invariant — No Snapshot Routing in Web/Mobile

`store_version_snapshot` (PUT) only adds rows to `FormPublishedVersion` — never modifies live tables. Live rows always equal the active version's schema. `web_form_details` and `form_data` endpoints read live rows as before — no special routing logic needed.

---

### D-7: Publish / Unpublish via `status` Field — `published_at` Guard

`create_published_version` uses `form.published_at is None` (not `form.status`) to detect first-ever publish. On re-publish after unpublish: only `status=published` is restored; `published_at` is NOT overwritten.

**`unpublish` (atomic)**:
1. Returns 400 if `form.status != published`
2. Auto-activates latest snapshot if unactivated PUT snapshots exist (prevents editing from stale live rows)
3. Sets `form.status = draft`

---

### D-8: `_build_schema_snapshot` — Lowercase Type Strings

`QuestionTypes.FieldStr.get(q.type)` returns PascalCase strings (e.g., `"Cascade"`, `"Text"`). The snapshot stores `QuestionTypes.FieldStr.get(q.type, "").lower()` so type strings in snapshots are always lowercase and match what the editor expects for rendering.

Without `.lower()`, `version_detail` would return `"Cascade"` and the editor would fail to render questions because it only recognises lowercase type strings.

---

### D-9: `restore_from_snapshot` — Type Alias for `entity` and `administration`

When activating a snapshot, `restore_from_snapshot` must convert snapshot type strings back to `QuestionTypes` integer constants via `getattr(QuestionTypes, type_str, None)`. But `"entity"` and `"administration"` are not attributes of `QuestionTypes` — only `"cascade"` is.

**Fix**: A local alias dict maps both to `"cascade"` before the `getattr` lookup:

```python
_TYPE_ALIAS = {"entity": "cascade", "administration": "cascade"}
raw_type = (q_data.get("type") or "").lower()
q_type = getattr(QuestionTypes, _TYPE_ALIAS.get(raw_type, raw_type), None)
if q_type is None:
    continue
```

Without this, questions with `type="entity"` or `type="administration"` in a snapshot are silently skipped during restore, leaving the form with missing questions after activation.

---

### D-10: `_form_detail_from_snapshot` — Include `variable_name` and `description`

`_form_detail_from_snapshot` builds a `FormDetailSerializer`-shaped response from the snapshot JSON for published form GET and version_detail endpoints.

Both `variable_name` (per-question) and `description` (top-level form field) must be included:
- `variable_name` is in each question dict from the snapshot
- `description` is at the top level of the snapshot schema

Without these, editing a published form would silently drop `variable_name` on every save (the editor round-trip loads the form via this function, clears the field, then saves it empty).

---

## 6. Compatibility & Migration

### Backward Compatibility

- `FormData` records with `published_version=null` (pre-FB-002B): treated as "schema unknown", fall back to live question tables
- Existing `Forms` with `status=published` and `active_version=null`: remain functional for data collection (live rows serve as source of truth until republished)
- All read endpoints continue to filter `deleted_at__isnull=True` via SoftDeletes default manager

### Mobile App Impact

| Aspect | Impact |
|--------|--------|
| `get_cascades()` response | No change |
| Administration question lookup | No change |
| `generate_sqlite` | Future: use `active_version.schema` as question source |

### Files Changed

| File | Change | Status |
|---|---|---|
| `v1_forms/models.py` | `QuestionGroup`/`Questions` extend `SoftDeletes`; conditional constraints; `FormPublishedVersion` model; `Forms.active_version` FK | ✅ |
| `v1_data/models.py` | `FormData.published_version` nullable FK | ✅ |
| `v1_forms/migrations/0008_*` | `deleted_at` + conditional constraints | ✅ |
| `v1_forms/migrations/0009_*` | `FormPublishedVersion` table + `Forms.active_version` | ✅ |
| `v1_data/migrations/0004_*` | `FormData.published_version` FK | ✅ |
| `v1_forms/functions.py` | `_build_schema_snapshot`, `store_version_snapshot`, `create_published_version`, `restore_from_snapshot` | ✅ |
| `v1_forms/serializers.py` | `deleted_at__isnull=True` on all querysets; `FormPublishedVersionSerializer`; `FormDetailSerializer.latest_version` | ✅ |
| `v1_forms/views.py` | `_form_detail_from_snapshot` (includes `variable_name` + `description`); `update` → `store_version_snapshot` for published; `retrieve` → latest snapshot; `publish` / `activate` / `unpublish` actions | ✅ |
| `v1_forms/views.py` | `_to_editor_format()` + `_SNAKE_TO_CAMEL_Q` — camelCase conversion applied to all `FormBuilderViewSet` responses | ✅ |
| `v1_forms/tasks.py` | `refresh_form_config()` — `clear_cache` + `generate_config` via `async_task` after publish | ✅ |
| `v1_forms/views.py` | `web_form_details` → 404 when `active_version` null | ⏳ Group F |
| `v1_data/views.py` | Set `published_version_id` on `FormData` create | ⏳ Group G |

---

## 7. Security Considerations

- [x] `FormPublishedVersion` records are immutable — no update endpoint exists
- [x] `activate` validates version belongs to the form (404 on cross-form access)
- [x] All manage endpoints require authentication (inherited from `FormBuilderViewSet`)

---

## 8. Testing Strategy

| File | Covers |
|---|---|
| `tests_manage_form_soft_delete.py` | allow_delete guard, soft vs hard delete, row preservation |
| `tests_manage_form_publish.py` | publish, duplicate, versions list, activate |
| `tests_manage_form_snapshot_put.py` | snapshot PUT; unpublish/edit/republish; published_at preservation |
| `tests_manage_form_versions.py` | GET versions/{version_id} — 10 tests |

Pending (Groups F and G):
- `test_draft_form_web_endpoint_returns_404`
- `test_published_form_web_endpoint_serves_snapshot`
- `test_form_data_records_published_version`

```bash
./dc.sh exec backend python manage.py test \
  api.v1.v1_forms.tests.tests_manage_form_soft_delete \
  api.v1.v1_forms.tests.tests_manage_form_publish \
  api.v1.v1_forms.tests.tests_manage_form_snapshot_put \
  api.v1.v1_forms.tests.tests_manage_form_versions
```

---

## 9. Open Questions

- [ ] Should `generate_sqlite` use `active_version.schema` as the question source? (Group F follow-up — noted as future sub-task)
- [ ] Snapshot diffing / changelog between two published versions — deferred

---

## 10. References

- Depends on: [[FB-002]] (must be implemented first)
- Frontend consumer: [[FB-003]]
- Branch: `feature/229-fb-002-implement-backend-form-crud-api` (same branch as FB-002)
- GitHub Issue: #229

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan | 2026-06-08 | Partially implemented |
| Tech Lead | | | |
