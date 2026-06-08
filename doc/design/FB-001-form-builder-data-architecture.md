# Feature Design Document: Form Builder Data Architecture

**Task ID**: FB-001
**Author**: Deden / Iwan
**Date**: 2025-01
**Status**: Approved (Implemented in feature/229-fb-002-implement-backend-form-crud-api)

---

## 1. Context & Problem Statement

```
Currently:
- Forms are defined as JSON files in `backend/source/forms/`
- Forms are loaded via CLI command: `python manage.py form_seeder`
- No UI exists for creating or editing forms
- Forms have no draft/published lifecycle
- Version field exists but is manually incremented by seeder

Goal:
- Enable UI-driven form management via akvo-react-form-editor
- Support draft → published workflow
- Maintain version history for forms with submissions
- Preserve backward compatibility with CLI seeder and mobile sync
```

---

## 2. Requirements

### User Acceptance Criteria
- [x] Technical design document reviewed by team
- [x] Data model changes identified
- [x] Migration strategy documented

### Technical Acceptance Criteria
- [x] Form status field (draft/published) added to Forms model
- [x] Version control strategy for forms with existing submissions
- [x] JSON schema storage approach defined (editor output vs normalized)
- [x] Backward compatibility with CLI seeder maintained
- [x] Mobile sync and data submissions impact assessed
- [x] API contract for CRUD operations defined
- [x] Editor question types mapped to backend QuestionTypes

---

## 3. Data Model Changes

### New Models

#### FormPublishedVersion
Immutable snapshot of form structure at publish time. Enables historical submission rendering.

```python
class FormPublishedVersion(models.Model):
    """Immutable snapshot of a form's question structure at publish time.

    Created by POST /manage/forms/{id}/publish. Never modified after creation.
    FormData.published_version references this to enable rendering historical
    submissions against the exact schema used at collection time.
    """
    form = models.ForeignKey(Forms, on_delete=models.CASCADE, related_name="published_versions")
    version = models.IntegerField()  # Auto-incremented per form
    schema = models.JSONField()      # Full JSON snapshot of question_group[]
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(SystemUser, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ("form", "version")
        db_table = "form_published_version"
```

#### FormStatus Constant
```python
class FormStatus:
    draft = 1
    published = 2

    FieldStr = {
        draft: "draft",
        published: "published",
    }
```

### Modified Models

#### Forms Model - New Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `status` | IntegerField | `draft` (1) | Draft/published lifecycle state |
| `published_at` | DateTimeField | null | Timestamp of first publish |
| `previous_version` | ForeignKey(self) | null | Version chain (form evolution) |
| `active_version` | ForeignKey(FormPublishedVersion) | null | Currently active schema snapshot |

```python
class Forms(models.Model):
    # Existing fields
    name = models.TextField()
    version = models.IntegerField(default=1)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    approval_instructions = models.JSONField(default=None, null=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True)  # Registration↔Monitoring
    type = models.IntegerField(choices=FormTypes.FieldStr.items())

    # NEW FIELDS
    status = models.IntegerField(choices=FormStatus.FieldStr.items(), default=FormStatus.draft)
    published_at = models.DateTimeField(null=True, blank=True, default=None)
    previous_version = models.ForeignKey("self", on_delete=models.SET_NULL,
                                          related_name="next_versions", null=True)
    active_version = models.ForeignKey("FormPublishedVersion", on_delete=models.SET_NULL,
                                        related_name="active_for_forms", null=True)
```

#### QuestionGroup & Questions - Soft Delete Support

Both models now inherit `SoftDeletes` mixin with conditional unique constraints:

```python
class QuestionGroup(SoftDeletes):
    # ...existing fields...

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_form_question_group",
            )
        ]

class Questions(SoftDeletes):
    # ...existing fields...

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_form_question",
            )
        ]
```

### Migration Strategy

```python
# Migration sets status = PUBLISHED for all existing forms (they are already live)
migrations.AddField(
    model_name='forms',
    name='status',
    field=models.IntegerField(
        choices=[(1, 'draft'), (2, 'published')],
        default=2,  # PUBLISHED for existing rows
    ),
    preserve_default=False,
),

# Other new fields are nullable, no data migration needed
migrations.AddField(model_name='forms', name='published_at', ...)
migrations.AddField(model_name='forms', name='previous_version', ...)
migrations.AddField(model_name='forms', name='active_version', ...)
```

---

## 4. API Contract

### URL Namespaces

Two URL namespaces serve different purposes:

| Namespace | Purpose | Auth |
|-----------|---------|------|
| `/api/v1/forms` | Read-only, backward compat for mobile/web | No |
| `/api/v1/manage/forms` | Authenticated CRUD for form builder UI | Yes |

### Endpoints

| Method | URL | Purpose | Auth |
|--------|-----|---------|------|
| GET | `/api/v1/forms` | Flat list (backward compat) | No |
| GET | `/api/v1/manage/forms` | Paginated list for builder UI | Yes |
| POST | `/api/v1/manage/forms` | Create form (as draft) | Yes |
| GET | `/api/v1/manage/forms/{id}` | Get form detail | Yes |
| PUT | `/api/v1/manage/forms/{id}` | Update form in-place | Yes |
| DELETE | `/api/v1/manage/forms/{id}` | Delete form (if no submissions) | Superuser |
| POST | `/api/v1/manage/forms/{id}/publish` | Publish draft | Yes |
| POST | `/api/v1/manage/forms/{id}/unpublish` | Unpublish (status → draft) | Yes |
| POST | `/api/v1/manage/forms/{id}/duplicate` | Clone as new draft | Yes |
| GET | `/api/v1/manage/forms/{id}/versions` | List version snapshots | Yes |
| GET | `/api/v1/manage/forms/{id}/versions/{vid}` | Get specific version detail | Yes |
| POST | `/api/v1/manage/forms/{id}/activate/{vid}` | Set active version | Yes |

### Request Payload (Create/Update)

Accepts editor JSON output after frontend transformation:

```json
{
  "name": "Household Survey 2026",
  "type": "registration",
  "approval_instructions": null,
  "parent": null,
  "question_group": [
    {
      "id": null,
      "name": "Household Information",
      "label": null,
      "order": 1,
      "repeatable": false,
      "repeat_text": null,
      "question": [
        {
          "id": null,
          "order": 1,
          "label": "Head of Household Name",
          "name": "head_of_household_name",
          "type": "input",
          "meta": true,
          "required": true,
          "rule": null,
          "dependency": null,
          "dependency_rule": "AND",
          "option": []
        }
      ]
    }
  ]
}
```

### Response Format (Detail)

```json
{
  "id": 42,
  "name": "Household Survey 2026",
  "version": 1,
  "status": "draft",
  "published_at": null,
  "active_version_id": null,
  "type": 1,
  "approval_instructions": null,
  "parent": null,
  "question_group": [
    {
      "id": 1,
      "name": "Household Information",
      "question": [
        {
          "id": 10,
          "type": "input",
          "label": "Head of Household Name",
          "disable_delete": null
        },
        {
          "id": 11,
          "type": "number",
          "label": "Age",
          "disable_delete": true
        }
      ]
    }
  ]
}
```

---

## 5. Decision Log

### D-1: Always In-Place PUT (No Version-on-Edit)

**Options Considered**:
1. Version-on-edit: PUT on published form creates new draft version (new form ID)
2. Always in-place: PUT always updates same record, returns 200

**Decision**: Always in-place (option 2)

**Rationale**:
- Version-on-edit creates duplicate form records, confusing the form list
- Frontend would need to handle 200 vs 201 responses differently
- Data integrity protected by "can't delete answered questions" guard
- `FormPublishedVersion` snapshots provide full version history without new form rows

**Impact**: PUT always returns 200. Form ID never changes. Published forms store changes as new snapshots.

---

### D-2: Separate `parent` and `previous_version` Foreign Keys

**Options Considered**:
1. Reuse `parent` FK for both purposes
2. Add separate `previous_version` FK

**Decision**: Separate FK fields

**Rationale**:
- `parent`: Links monitoring form → registration form (form type relationship)
- `previous_version`: Links form → its predecessor (version evolution)
- Different semantic meanings, different query patterns

---

### D-3: Rename `photo` → `image` in QuestionTypes

**Options Considered**:
1. Keep `photo`, map `image` in transformer
2. Rename to `image` to match editor and akvo-form-service

**Decision**: Rename to `image`

**Rationale**:
- `akvo-react-form-editor` emits `"image"`
- `akvo-form-service` uses `image = 8` as canonical name
- Single source of truth, no mapping needed

**Impact**:
- Constant renamed: `QuestionTypes.photo` → `QuestionTypes.image`
- FieldStr: `{image: "Image"}`
- DB value unchanged (still `8`)
- `"photo"` string no longer accepted in API payloads

---

### D-4: Delete Strategy - Reject if Submissions Exist

**Options Considered**:
1. Hard delete (cascade all data)
2. Soft delete / archive status
3. Reject if submissions exist, hard delete otherwise

**Decision**: Option 3

**Rationale**:
- Cascade delete would orphan/corrupt FormData records
- Full archive adds model complexity not yet needed
- Safest: block deletion when data exists, allow for unused drafts

**Impact**: DELETE returns 409 Conflict if form has submissions

---

### D-5: JSON Schema Storage - Normalized in DB, Snapshot on Publish

**Options Considered**:
1. Store editor JSON directly (denormalized)
2. Normalize to relational tables, snapshot to JSON on publish

**Decision**: Option 2 - Normalized storage with JSON snapshots

**Rationale**:
- Normalized tables enable efficient queries, validations, reporting
- `FormPublishedVersion.schema` stores immutable JSON snapshot
- Historical submissions rendered against exact schema at collection time
- Best of both: relational power + historical preservation

**Impact**:
- Live editing modifies QuestionGroup/Questions tables (draft forms)
- Publishing creates FormPublishedVersion with full schema JSON
- Submissions link to specific published version

---

### D-6: Soft Delete for Questions/Groups with Answers

**Options Considered**:
1. Block all deletion of answered questions
2. Soft delete (preserve row, mark deleted_at)
3. Allow hard delete with cascade

**Decision**: Soft delete with `allow_delete` flag

**Rationale**:
- Maintains referential integrity (Answers still reference question)
- Questions can be "removed" from form without orphaning data
- Conditional unique constraints allow reusing names after soft delete

**Impact**:
- Questions/QuestionGroups inherit SoftDeletes mixin
- `deleted_at` field marks soft-deleted rows
- Unique constraints only apply to active (non-deleted) rows

---

### D-7: Published Form PUT Creates Snapshot Only

**Options Considered**:
1. Block editing of published forms entirely
2. Create new draft version on edit
3. Store edit as new snapshot, don't touch live rows

**Decision**: Option 3 - Snapshot-only path for published forms

**Rationale**:
- Live rows (QuestionGroup, Questions) represent active schema
- New submissions always use active schema
- Snapshots preserve "pending" edits until explicitly activated
- Admin can preview changes before affecting data collection

**Impact**:
- PUT on published form: INSERT into FormPublishedVersion, no live row changes
- `activate` endpoint applies snapshot to live rows
- `unpublish` auto-activates latest snapshot before enabling edit mode

---

### D-8: Granular Permissions for Form Builder

**Decision**: Define five granular FeatureAccessTypes now for FB-009

```python
class FeatureAccessTypes:
    form_view = 3
    form_create = 4
    form_edit = 5
    form_publish = 6
    form_delete = 7
```

**Permission Mapping**:

| Action | Permission |
|--------|------------|
| list, retrieve | form_view |
| create, duplicate | form_create |
| update | form_edit |
| publish, unpublish, activate | form_publish |
| destroy | superuser only |

---

## 6. Type/Constant Mappings

### Question Types

| Editor Type | Backend Constant | DB Value | Notes |
|-------------|------------------|----------|-------|
| `input` | `QuestionTypes.input` | 13 | Single-line text |
| `number` | `QuestionTypes.number` | 4 | Numeric input |
| `text` | `QuestionTypes.text` | 3 | Multi-line textarea |
| `date` | `QuestionTypes.date` | 9 | Date picker |
| `option` | `QuestionTypes.option` | 5 | Single choice |
| `multiple_option` | `QuestionTypes.multiple_option` | 6 | Multi choice |
| `cascade` | `QuestionTypes.cascade` | 7 | Cascading dropdown |
| `image` | `QuestionTypes.image` | 8 | Photo upload |
| `geo` | `QuestionTypes.geo` | 1 | Geolocation |
| `autofield` | `QuestionTypes.autofield` | 10 | Computed field |

### Types NOT in Editor (Require Special Handling)

| Backend Type | DB Value | Handling |
|--------------|----------|----------|
| `administration` | 2 | Use `settingTreeDropdownValue` in editor config |
| `attachment` | 11 | Post-editor custom UI or customParams |
| `signature` | 12 | Post-editor custom UI or customParams |

### Entity Type Mapping

`"entity"` is NOT a valid API type. Frontend must transform:

```
Editor: type="entity"
   ↓ editorToApi()
API: type="cascade", extra={"type": "entity", "name": "..."}
   ↓ apiToEditor()
Editor: type="entity"
```

### Form Types

| Value | String | Constant |
|-------|--------|----------|
| 1 | `"registration"` | `FormTypes.registration` |
| 2 | `"monitoring"` | `FormTypes.monitoring` |

API accepts both integer (1/2) and string ("registration"/"monitoring").

---

## 7. Compatibility & Migration

### Backward Compatibility

- [x] `GET /api/v1/forms` unchanged (flat list, no auth)
- [x] `GET /api/v1/form/{id}` unchanged (web/mobile form rendering)
- [x] Existing data preserved with status=PUBLISHED
- [x] All seeded forms remain accessible

### CLI Seeder Compatibility

- [x] `form_seeder` continues to work
- [x] Seeded forms created as PUBLISHED (status=2)
- [x] Version increments on re-seed (existing behavior)
- [x] New forms via UI coexist with seeded forms

### Mobile App Impact

| Aspect | Impact | Notes |
|--------|--------|-------|
| Sync endpoints | Unchanged | `/device/form/{id}` still works |
| Form filter | `status=published` only | Draft forms hidden from mobile |
| Version detection | `form.version` comparison | Same as before |
| SQLite cascades | Unchanged | Same generation process |

**Mobile Sync Flow**:
1. Mobile authenticates → receives `formsUrl[]` with version
2. Compares `api.version > local.version`
3. Re-downloads if version changed
4. Only published forms appear in assignment

### Data Submission Integrity

- FormData continues to link to Forms via form_id
- Historical submissions can be rendered using FormPublishedVersion.schema
- Active submissions always use current active_version schema
- No submission orphaning - soft delete preserves question references

---

## 8. Security Considerations

- [x] Permission model: 5 granular FeatureAccessTypes
- [x] Delete restricted to superuser only
- [x] FormBuilderAccess permission factory validates role access
- [x] Answered questions protected from deletion
- [x] Input validation via validate_form_payload()

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Form CRUD, publish/unpublish, snapshot creation |
| Unit | Soft delete behavior, answered question protection |
| Unit | Permission checks per action |
| Integration | Create → Publish → Submit → View cycle |
| Integration | Unpublish → Edit → Republish lifecycle |
| E2E | Mobile sync with UI-created forms |

Test files:
- `tests_manage_form_list.py`
- `tests_manage_form_create.py`
- `tests_manage_form_update.py`
- `tests_manage_form_soft_delete.py`
- `tests_manage_form_publish.py`
- `tests_manage_form_snapshot_put.py`
- `tests_manage_form_versions.py`
- `tests_manage_form_delete.py`

---

## 10. Implementation Files

| File | Purpose |
|------|---------|
| `v1_forms/constants.py` | FormStatus, QuestionTypes.image |
| `v1_forms/models.py` | Forms fields, FormPublishedVersion, soft delete |
| `v1_forms/functions.py` | save_form, create_published_version, restore_from_snapshot |
| `v1_forms/views.py` | FormBuilderViewSet |
| `v1_forms/serializers.py` | FormDetailSerializer, FormPublishedVersionSerializer |
| `v1_forms/urls.py` | /manage/forms routes |
| `v1_profile/constants.py` | FeatureAccessTypes |
| `utils/custom_permissions.py` | FormBuilderAccess factory |

---

## 11. References

- Feature spec: `doc/akvo-mis-initiative/01-form-builder-feature.md`
- Implementation branch: `feature/229-fb-002-implement-backend-form-crud-api`
- Related task: FB-002 (Backend API), FB-003 (Frontend Integration)
- Editor library: `akvo-react-form-editor`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan | 2025-01 | Approved |
| Tech Lead | Deden | 2025-01 | Approved |
