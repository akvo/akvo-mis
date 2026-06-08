# Feature Design Document: Align Question Model with Editor Payload

**Task ID**: FB-002A
**Author**: Iwan
**Date**: 2026-06-08
**Status**: In Progress

---

## 1. Context & Problem Statement

```
This task covers two related changes that together ensure the backend
Question model stores exactly what akvo-react-form-editor sends:

--- Part 1: Remove administration=2 question type ---

QuestionTypes.administration = 2 was a first-class question type in the backend.
After initial removal (branch feature/229), all references were replaced with
QuestionTypes.cascade but with broken side-effects:
- akvo-react-form (web renderer) gets type="cascade" → wrong widget rendered
  (expects "administration" to render the admin hierarchy selector)
- form_seeder crashes on JSON files with "type": "administration" because
  getattr(QuestionTypes, "administration") raises AttributeError
- get_cascades() has a bug: type__in=[cascade, cascade] (duplicate) and appends
  both administrator.sqlite AND organisation.sqlite for every cascade question

--- Part 2: Extend Questions with all editor payload fields ---

akvo-react-form-editor emits question fields that the current Questions model
does not store: variableName, hiddenString, requiredDoubleEntry, disabled,
addonBefore/addonAfter, dataApiUrl. These fields pass through silently and are
lost on every save.

The akvo-form-service reference implementation stores all of these. akvo-mis must
do the same to be a complete backend for the editor.

Also: migrations 0007/0008/0009 were previously three separate incremental
migrations. This task consolidates them into a single 0007 that also adds the
new fields.

Goals:
- Remove administration=2 entirely; use cascade=7 + extra.type="administration"
  (matching akvo-form-service)
- Add all editor payload fields to Questions model
- Add description to Forms model
- All serializers return correct semantic type strings to frontend/mobile
- get_api() generates a dynamic, user-scoped administration endpoint
- Seed JSON files updated to new format
- Data migration converts existing type=2 rows
- Consolidated single migration covering all FB-002/FB-002B + new field changes
```

---

## 2. Requirements

### User Acceptance Criteria

- [ ] Web form renderer shows administration hierarchy selector (not generic cascade) for admin questions
- [ ] Mobile app correctly identifies and handles administration questions
- [ ] Form seeder runs without errors on updated JSON files
- [ ] All question fields sent by the editor are persisted and returned on GET

### Technical Acceptance Criteria

**Part 1 — Administration type removal:**
- [ ] No `QuestionTypes.administration` anywhere in codebase
- [ ] `get_type()` returns `"administration"` for cascade+extra.type=administration questions
- [ ] `get_api()` returns dynamic user-scoped endpoint for administration questions
- [ ] `get_cascades()` correctly categorises cascade questions for mobile SQLite
- [ ] Mobile view finds administration question using `extra.type` filter
- [ ] `validate_administration()` only called for administration cascade questions
- [ ] Data migration converts type=2 → type=7 + extra.type="administration"
- [ ] All seed JSON files updated to `"type": "cascade"` + `"extra": {"type": "administration"}`

**Part 2 — Extended question fields:**
- [ ] `Questions` model has `variable_name`, `hidden_string`, `required_double_entry`, `disabled`, `addon_before`, `addon_after`, `data_api_url` fields
- [ ] `Forms` model has `description` field
- [ ] `_normalize_editor_payload()` converts all camelCase editor keys to snake_case
- [ ] `_save_questions()` persists all new fields
- [ ] `duplicate_form()` copies all new fields
- [ ] `restore_from_snapshot()` restores all new fields
- [ ] `_build_schema_snapshot()` includes all new fields in the snapshot JSON
- [ ] `FormDetailQuestionSerializer` returns all new fields
- [ ] Migrations 0007/0008/0009 consolidated into a single 0007

---

## 3. Data Model Changes

### Modified: `Forms`

```python
description = models.TextField(default=None, null=True)
```

### Modified: `Questions` — new fields

```python
variable_name = models.CharField(max_length=255, null=True, default=None)
hidden_string = models.BooleanField(default=None, null=True)
required_double_entry = models.BooleanField(default=False)
disabled = models.BooleanField(default=False, null=True)
addon_before = models.CharField(max_length=50, null=True, default=None)
addon_after = models.CharField(max_length=50, null=True, default=None)
data_api_url = models.CharField(max_length=255, null=True, default=None)
center = models.JSONField(default=None, null=True)
```

Field mapping from akvo-react-form-editor payload to backend:

| Editor (camelCase) | Backend field | DB type | akvo-form-service equivalent |
|---|---|---|---|
| `variableName` | `variable_name` | `VARCHAR(255)` | — |
| `hiddenString` | `hidden_string` | `BOOL NULL` | `hidden_string` |
| `requiredDoubleEntry` | `required_double_entry` | `BOOL` | `required_double_entry` |
| `disabled` | `disabled` | `BOOL NULL` | — |
| `addonBefore` | `addon_before` | `VARCHAR(50)` | `addonBefore` (camelCase in form-service) |
| `addonAfter` | `addon_after` | `VARCHAR(50)` | `addonAfter` (camelCase in form-service) |
| `dataApiUrl` | `data_api_url` | `VARCHAR(255)` | `data_api_url` |
| `center` | `center` | `JSONB NULL` | — |

`center` stores `[lat, lng]` for `geoshape` and `geotrace` questions — the default map center rendered by the editor and web form. Absent for all other question types. The existing `rule` JSONField already stores `{minDate, maxDate}` for `date` questions with no model change required.

All new fields are nullable with `default=None` / `default=False` — no data migration needed for existing rows.

### Modified: `Questions` — existing fields from Part 1

The `type=2` (administration) rows are migrated to `type=7` + `extra={"type":"administration"}`.
No column is dropped — the integer value `2` is simply repurposed/vacated.

### Migration Strategy — Consolidated 0007

Migrations 0007, 0008, 0009 (which previously existed as three separate files) are removed and replaced by a single `0007_question_model_alignment.py` that covers all of:

| Was in | Operations covered |
|---|---|
| Old 0007 | `Forms.status`, `Forms.published_at`, `Forms.previous_version` |
| Old 0008 | `QuestionGroup`/`Questions` `SoftDeletes` (`deleted_at`), conditional unique constraints |
| Old 0009 | `FormPublishedVersion` table, `Forms.active_version` FK |
| **New** | `Forms.description`, `Questions` extended fields (7 new columns) |

Plus a data migration operation to convert type=2 → type=7 rows:

```python
def migrate_administration_to_cascade(apps, schema_editor):
    Questions = apps.get_model("v1_forms", "Questions")
    for q in Questions.objects.filter(type=2):
        existing_extra = q.extra or {}
        q.extra = {**existing_extra, "type": "administration"}
        q.type = 7
        q.save(update_fields=["type", "extra"])
```

Uses a Python loop (not bulk_update) to safely merge `extra` without overwriting existing keys.

---

## 4. API Contract

### Type String Changes

Serializers now return semantic type strings based on `extra.type`:

| DB `type` | `extra.type` | `get_type()` returns | Meaning |
|-----------|-------------|---------------------|---------|
| 7 (cascade) | `"administration"` or absent | `"administration"` | Admin hierarchy selector |
| 7 (cascade) | `"entity"` | `"entity"` | Entity cascade dropdown |
| 7 (cascade) | other value | `"cascade"` | Generic cascading dropdown |
| any other | — | `QuestionTypes.FieldStr[type].lower()` | Normal type string |

### `get_api()` Branch Logic

```
cascade + extra.type="administration" (or null) → dynamic user-scoped endpoint:
  {
    "endpoint": "/api/v1/administration",
    "list": "children",
    "initial": <user-role-specific-admin-id>
  }

cascade + extra.type="entity" → return instance.api as-is

attachment → return instance.api as-is

all others → null
```

**Why not store the endpoint URL?** The `initial` node is user-specific (security boundary).
A district-level data collector receives `initial: <district_id>`, not `initial: 1` (root).
Storing and returning the editor's hardcoded `initial: 1` would expose the full hierarchy
to restricted users. See Decision Log D-1.

### Extended `FormDetailQuestionSerializer` Fields

All new fields are added to the response so the editor can round-trip them:

```json
{
  "id": 10,
  "type": "input",
  "label": "Location",
  "variable_name": "variable_name",
  "hidden_string": true,
  "required_double_entry": true,
  "disabled": true,
  "addon_before": "area",
  "addon_after": "m2",
  "data_api_url": "https://localhost:3000"
}
```

### `_normalize_editor_payload` — Full camelCase Mapping

```python
_CAMEL_FIELDS = {
    "displayOnly":        "display_only",
    "shortLabel":         "short_label",
    "variableName":       "variable_name",
    "hiddenString":       "hidden_string",
    "requiredDoubleEntry": "required_double_entry",
    "addonBefore":        "addon_before",
    "addonAfter":         "addon_after",
    "dataApiUrl":         "data_api_url",
}
```

---

## 5. Decision Log

### D-1: Why akvo-mis Does Not Store the Administration Endpoint

**Context**: akvo-form-service stores `api.endpoint` as-is and returns it unchanged.
akvo-mis has user-scoped access control on the administration hierarchy.

**Options Considered**:
1. Store endpoint as-is (form-service approach) — client receives `initial: 1` (root)
2. Strip endpoint on save, generate dynamically at request time

**Decision**: Option 2 — dynamic generation

**Rationale**: Data collectors at sub-district level must only see their accessible nodes.
`get_api()` injects the correct `initial` based on the requesting user's role. This is
a security boundary, not just UX — a user should not be able to enumerate nodes above
their assigned level.

**Impact**: `extra.type="administration"` is the marker. `api` stores only `max_level`
if present. Full endpoint object is generated at request time.

---

### D-2: Detection in `editorToApi()` — Endpoint Pattern Matching

**Context**: `akvo-react-form-editor` emits cascade questions with a full URL endpoint:
```json
{"endpoint": "https://rtmis.akvotest.org/api/v1/administration", "initial": 1, "list": "children"}
```
The editor does not set `extra.type` — it sends a generic cascade with a configured URL.

**Decision**: Option 1 — endpoint pattern matching in `editorToApi()`

**Detection rule**: `api.endpoint` contains `/api/v1/administration` anywhere in the URL.

**`editorToApi()` transform**:
```js
const ADMIN_ENDPOINT = /\/api\/v1\/administration/;
if (q.type === "cascade" && ADMIN_ENDPOINT.test((q.api || {}).endpoint || "")) {
  const maxLevel = (q.api || {}).max_level || null;
  return {
    ...normalizeQuestion(q),
    type: "cascade",
    extra: { ...(q.extra || {}), type: "administration" },
    api: maxLevel ? { max_level: maxLevel } : null,
  };
}
```

**`apiToEditor()` roundtrip** (load form back into editor):
```js
if (!extraType || extraType === "administration") {
  const maxLevel = (q.api || {}).max_level;
  return {
    ...snakeToCamelQuestion(q),
    type: "cascade",
    api: {
      endpoint: "/api/v1/administration",
      initial: 1,
      list: "children",
      ...(maxLevel ? { max_level: maxLevel } : {}),
    },
  };
}
```

---

### D-3: `extra.type` Absent = Administration (Backward Compat)

**Context**: Old rows have `extra = null` (no marker). After migration they will have
`extra = {"type": "administration"}`. But during any overlap window, code must handle null.

**Decision**: Treat `extra.type` absent/null as equivalent to `"administration"`.

```python
extra_type = (instance.extra or {}).get("type")
is_admin = extra_type in ("administration", None)
```

This matches the akvo-form-service convention.

---

### D-4: Shared Helper Function for `get_type()`

Three serializers (`ListQuestionSerializer`, `FormDataListQuestionSerializer`,
`FormDetailQuestionSerializer`) all need the same type-resolution logic.

**Decision**: Extract a module-level `_question_type_str(instance)` helper.

```python
def _question_type_str(instance: Questions) -> str:
    if instance.type == QuestionTypes.cascade:
        extra_type = (instance.extra or {}).get("type")
        if extra_type == "entity":
            return "entity"
        return "administration"  # None or "administration"
    return QuestionTypes.FieldStr.get(instance.type, "").lower()
```

---

### D-5: Migration Consolidation — Single 0007

**Context**: The previous incremental approach produced three separate migrations
(0007, 0008, 0009) for the FB-002 / FB-002B work, plus the new extended fields
would need a fourth.

**Decision**: Delete 0007/0008/0009 and generate a single consolidated migration
that covers all changes at once (FB-002 fields + FB-002B soft-delete/versioning +
new extended fields).

**Rationale**: This is a pre-merge branch. No other branch depends on these migrations.
A single migration is easier to review, easier to squash, and avoids the risk of
dependency chain errors in CI. The current DB schema already has the tables created
by 0008/0009 applied — the single migration recreates them cleanly from the current
model state.

---

### D-6: `addon_before`/`addon_after` — snake_case in akvo-mis

**Context**: akvo-form-service stores these as `addonBefore`/`addonAfter` (camelCase
as column names). akvo-mis convention is snake_case for all column names.

**Decision**: Store as `addon_before`/`addon_after` in akvo-mis.

**Impact**: `_normalize_editor_payload` maps `addonBefore → addon_before`.
`form-builder-transform.js` (`apiToEditor`) maps back `addon_before → addonBefore`
for the editor.

---

### D-7: `variable_name` and `disabled` — Not in akvo-form-service

These fields appear in the akvo-react-form-editor payload but have no equivalent
in the akvo-form-service reference implementation.

**Decision**: Store them anyway — the model should accept the full editor payload
without silently dropping fields. Downstream consumers (report generators, exports)
can use them if needed.

---

## 6. Type/Constant Mappings

### Updated Table (replaces Section 6 of FB-001)

| Editor/Renderer Type | Backend Constant | DB Value | `extra.type` | Notes |
|---------------------|------------------|----------|--------------|-------|
| `administration` | `QuestionTypes.cascade` | 7 | `"administration"` | Admin hierarchy selector |
| `entity` | `QuestionTypes.cascade` | 7 | `"entity"` | Entity dropdown |
| `cascade` | `QuestionTypes.cascade` | 7 | other/absent | Generic cascade |
| `input` | `QuestionTypes.input` | 13 | — | |
| `number` | `QuestionTypes.number` | 4 | — | |
| `text` | `QuestionTypes.text` | 3 | — | |
| `date` | `QuestionTypes.date` | 9 | — | |
| `option` | `QuestionTypes.option` | 5 | — | |
| `multiple_option` | `QuestionTypes.multiple_option` | 6 | — | |
| `image` | `QuestionTypes.image` | 8 | — | |
| `geo` | `QuestionTypes.geo` | 1 | — | |
| `autofield` | `QuestionTypes.autofield` | 10 | — | |
| `attachment` | `QuestionTypes.attachment` | 11 | — | |
| `signature` | `QuestionTypes.signature` | 12 | — | |
| `geoshape` | `QuestionTypes.geoshape` | 14 | — | |
| `geotrace` | `QuestionTypes.geotrace` | 15 | — | |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [ ] Existing API consumers: `get_type()` now returns `"administration"` instead of `"cascade"` — this is a **fix**, not a break
- [ ] Existing data: migration converts type=2 → type=7+extra
- [ ] Form seeder: seed JSON files updated; no special-case code needed
- [ ] New `Questions` columns all nullable/default — no data migration needed for extended fields

### Mobile App Impact
| Aspect | Impact | Notes |
|--------|--------|-------|
| `get_cascades()` response | Fixed — no more double-append | administrator.sqlite for admin, entity_data.sqlite for entity |
| Administration question lookup | Now filtered by `extra__type="administration"` | More precise than `type=cascade` alone |
| Answer storage | Unchanged — still numeric admin ID | No change |

### Seeder/CLI Compatibility
- [ ] `form_seeder`: JSON files updated to `"type": "cascade"` + `"extra": {"type": "administration"}` — `getattr(QuestionTypes, "cascade")` works
- [ ] `form_seeder --test`: passes after migration runs

### Files to Update

| File | Change |
|------|--------|
| `backend/api/v1/v1_forms/models.py` | Add `Forms.description`; add 7 new fields to `Questions` |
| `backend/api/v1/v1_forms/migrations/` | Delete 0007/0008/0009; generate single `0007_question_model_alignment.py` |
| `backend/api/v1/v1_forms/migrations/0007_*` | Data migration op: type=2 → type=7 + extra.type="administration" |
| `backend/source/forms/example-1.json` | `type:"administration"` → `type:"cascade"`, add `extra:{"type":"administration"}`, remove `api.endpoint` |
| `backend/source/forms/example-2.json` | Same |
| `backend/source/forms/example-3.json` | Same |
| `backend/source/forms/example-4.json` | Same |
| `backend/source/forms/example-5.json` | Same (has `api.endpoint` only, no `max_level`) |
| `backend/source/forms/example-vis-6.json` | Same |
| `backend/source/forms/unused/1.prod.json` | Same |
| `backend/source/forms/unused/100.prod.json` | Same |
| `backend/source/forms/unused/1000.prod.json` | Same |
| `backend/source/forms/unused/1710731783596.prod.json` | Same |
| `backend/api/v1/v1_forms/serializers.py` | Add `_question_type_str()` helper; fix `get_type()` ×3, `get_api()`, `get_cascades()`; add 7 new fields to `FormDetailQuestionSerializer`; add `description` to `FormDetailSerializer` |
| `backend/api/v1/v1_forms/views.py` | Extend `_normalize_editor_payload` with full camelCase mapping |
| `backend/api/v1/v1_forms/functions.py` | Propagate new fields in `_save_questions`, `duplicate_form`, `restore_from_snapshot`, `_build_schema_snapshot`; add `description` to `save_form` |
| `backend/api/v1/v1_mobile/views.py` | Filter administration question by `extra__type` |
| `backend/api/v1/v1_jobs/validate_upload.py` | Only run `validate_administration()` for non-entity cascade |
| `frontend/src/lib/form-builder-transform.js` | Create: endpoint detection in `editorToApi()`, roundtrip in `apiToEditor()` (FB-003 branch) |

---

## 8. Security Considerations

- [x] Administration endpoint generated dynamically — user cannot see nodes above their level
- [x] `initial` node ID injected server-side per requesting user's role
- [x] `extra.type` is server-controlled — client cannot override it by sending a crafted payload
- [x] New question fields (`variable_name`, `hidden_string`, etc.) are stored verbatim — no execution, no secrets exposure risk

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | `_question_type_str()` with all `extra.type` variants |
| Unit | `get_api()` returns correct structure for admin vs entity vs generic cascade |
| Unit | `get_cascades()` returns correct SQLite sources per `extra.type` |
| Unit | `_normalize_editor_payload` converts all camelCase fields correctly |
| Unit | `save_form` persists extended fields; `GET` response includes them |
| Integration | Mobile view finds correct administration question with `extra__type` filter |
| Integration | `form_seeder --test` succeeds after seed JSON updates |
| Integration | Data migration: type=2 rows become type=7 with correct `extra` |
| Regression | All existing tests pass after migration |

---

## 10. Open Questions

- [x] Should `geoshape` and `geotrace` also be mapped from editor to backend? **Yes** — both types are in `QuestionTypes` constants and will be accepted.
- [x] Is `max_level` the only `api` subfield worth preserving for administration questions? **Yes** — strip everything else at save time; `get_api()` regenerates the full endpoint dynamically.
- [x] Should `Forms.description` also be included in the `FormPublishedVersion` snapshot schema? **Yes** — included in `_build_schema_snapshot` and restored by `restore_from_snapshot`.

---

## 11. References

- Supersedes: FB-001 Section 6 (Types NOT in Editor table — `administration | 2`)
- Parent branch: `feature/229-fb-002-implement-backend-form-crud-api`
- Reference implementation: `example/akvo-form-service/backend/akvo/core_forms/models.py`
- Related: [[FB-002]] (CRUD API), [[FB-002B]] (version schema), [[FB-003]] (Frontend transform in `form-builder-transform.js`)
- Original filename: `FB-002A-remove-administration-question-type.md` (renamed)

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan | 2026-06-08 | In Progress |
| Tech Lead | | | |
