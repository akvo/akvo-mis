# FB-002A: Form Schema Versioning

## What This Is

FB-002A introduces **published version snapshots** for forms. Every time a form is published, the complete question structure is frozen into a `FormPublishedVersion` record. Form submissions store a reference to the exact version that was active at collection time.

This solves a data integrity gap introduced in FB-002: since PUT updates forms in-place, deleting a question (via `allow_delete=true`) destroys the question row, making historical answers uninterpretable. With FB-002A, the snapshot preserves every question definition forever, regardless of what happens to the live question tables.

---

## Key Concepts

| Concept | Description |
|---|---|
| `FormPublishedVersion` | Immutable JSON snapshot of a form's full question structure, created on every `POST .../publish` |
| `Forms.active_version` | FK pointing to the snapshot currently used for new data collections; null = draft |
| `deleted_at` on `Questions` / `QuestionGroup` | `SoftDeletes` mixin field: set to now() by `allow_delete=True` instead of removing the row, preserving FK integrity for historical answers |
| Version rollback | `POST /manage/forms/{id}/activate/{version_id}` changes `active_version` without touching questions |

---

## Problem Solved

```
Before FB-002A:
  Form v1 published → user submits answers for question B
  Editor deletes question B (allow_delete=true, version becomes v2)
  → Answer for B is orphaned: no question row, no label, no type

After FB-002A:
  Form v1 published → FormPublishedVersion v1 created (includes B)
  FormData.published_version = v1
  Editor deletes question B (soft-deleted, row preserved) → version v2 snapshot excludes B
  → Answer for B still rendered via FormData.published_version.schema
```

---

## Related Documents

| Document | Purpose |
|---|---|
| [design.md](design.md) | Full data model, API contract, lifecycle diagrams, decisions |
| [requirements.md](requirements.md) | Functional and non-functional requirements |
| [implementation-plan.md](implementation-plan.md) | Step-by-step task breakdown per group |

---

## Dependencies

- **FB-002** (form builder backend CRUD API) — implemented in the same branch; no separate merge gate
- **FB-003** (frontend integration) — affected by `active_version_id` in form response
- **FB-009** (permission UI) — not a blocker

## Branch / Status

Implemented in `feature/229-fb-002-implement-backend-form-crud-api` (same branch as FB-002). Groups A–E complete; Groups F and G (serving `active_version.schema` to web/mobile endpoints and stamping `FormData.published_version` on submission) are pending.
