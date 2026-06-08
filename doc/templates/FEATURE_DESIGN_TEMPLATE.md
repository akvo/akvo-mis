# Feature Design Document Template

> **Purpose**: Use this template when planning new features that require data model changes, API design, or architectural decisions. Complete this document BEFORE implementation begins. Claude can read this document for context during implementation.

---

## Feature: [Feature Name]

**Task ID**: [e.g., FB-001]
**Author**: [Name]
**Date**: [YYYY-MM-DD]
**Status**: Draft | Review | Approved

---

## 1. Context & Problem Statement

Describe the current state and why this change is needed.

```
Currently:
- [What exists today]
- [Limitations or pain points]

Goal:
- [What we want to achieve]
```

---

## 2. Requirements

### User Acceptance Criteria
- [ ] [What users should be able to do]
- [ ] [Observable outcomes]

### Technical Acceptance Criteria
- [ ] [Specific technical requirements]
- [ ] [Performance requirements]
- [ ] [Compatibility requirements]

---

## 3. Data Model Changes

### New Models

```python
# Model name and purpose
class NewModel(models.Model):
    field_name = models.FieldType()  # Explanation
```

### Modified Models

| Model | Change | Reason |
|-------|--------|--------|
| `ModelName` | Add `field_name` | Purpose |

### Migration Strategy

```python
# Key migration considerations
# - Default values for existing rows
# - Data preservation
# - Rollback plan
```

---

## 4. API Contract

### Endpoints

| Method | URL | Purpose | Auth |
|--------|-----|---------|------|
| GET | `/api/v1/resource` | Description | Required |
| POST | `/api/v1/resource` | Description | Required |

### Request/Response Examples

```json
// POST /api/v1/resource
{
  "field": "value"
}

// Response 201
{
  "id": 1,
  "field": "value"
}
```

---

## 5. Decision Log

Document each significant decision with:

### D-1: [Decision Title]

**Options Considered**:
1. Option A - description
2. Option B - description

**Decision**: [Which option and why]

**Rationale**: [Detailed reasoning]

**Impact**: [What this affects]

---

## 6. Type/Constant Mappings

| Frontend/Editor | Backend Constant | DB Value |
|-----------------|------------------|----------|
| `"type_name"` | `TypeClass.name` | `1` |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [ ] Existing API consumers unaffected
- [ ] Existing data preserved
- [ ] CLI tools still work

### Mobile App Impact
- [ ] Sync endpoints affected: [list]
- [ ] SQLite schema changes: [yes/no]
- [ ] Version detection: [how mobile knows to update]

### Seeder/CLI Compatibility
- [ ] Existing seeders work
- [ ] New seeder commands needed: [list]

---

## 8. Security Considerations

- [ ] Permission model defined
- [ ] Input validation specified
- [ ] No new attack vectors introduced

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | [What to test] |
| Integration | [What to test] |
| E2E | [What to test] |

---

## 10. Open Questions

- [ ] [Unresolved question 1]
- [ ] [Unresolved question 2]

---

## 11. References

- Related tasks: [Links]
- External docs: [Links]
- Prior art: [Links]

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
