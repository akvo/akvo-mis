# Feature Design Document

## Feature: `geoConfig` Persistence & API Tests

**Task ID**: GEO-010 (breakdown ref: T9)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 3 — Overlap detection
**Estimate**: 2.5h ≈ 0.5 day (Backend)
**Depends on**: GEO-009

---

## 1. Context & Problem Statement

```
Currently:
- `Questions.extra` is a free-form JSONField already serialized to mobile, and
  FormDetailQuestionSerializer already lists `extra` among its fields.
- So geoConfig SHOULD round-trip with no model change — but nothing proves it does.

Goal:
- Prove that geoConfig survives create -> publish -> mobile fetch unchanged, and reject
  nonsensical values at the API boundary.
```

**The failure this guards against is silent.** If `extra` is filtered anywhere in the publish
path, mobile receives defaults, every threshold the designer set is ignored, and **nothing
reports an error**. The form looks configured and behaves as though it is not.

---

## 2. Requirements

### Technical Acceptance Criteria
- [ ] `extra.geoConfig` survives form create → publish → mobile fetch, byte-identical
- [ ] Out-of-range values rejected: negative area, threshold outside 0–100, non-numeric
- [ ] `geoConfig` is carried into the `FormPublishedVersion` snapshot, not dropped
- [ ] No model change required — confirm, do not assume

---

## 3. Data Model Changes

**None expected.** This task's first job is to *verify* that claim.

| Model | Field | Status |
|-------|-------|--------|
| `Questions` | `extra` (JSONField, `models.py:148`) | Exists, already serialized |
| `FormDetailQuestionSerializer` | lists `extra` | Exists |
| `WebFormDetailSerializer` | serves web **and** mobile | Exists |

If publish-path filtering is found, a fix is in scope here.

---

## 4. API Contract

**No new endpoints.** Existing:

| Method | URL | Assertion |
|--------|-----|-----------|
| POST | `/api/v1/form` | `extra.geoConfig` persisted as sent |
| GET | `/api/v1/form/{id}` | Builder sees the same values back |
| GET | mobile form detail | `extra.geoConfig` present and unchanged |

---

## 5. Decision Log

### D-1: Validate at the API boundary, not only in the builder UI

**Decision**: Reject nonsensical `geoConfig` values server-side.

**Rationale**: The builder UI is one client. Form JSON can also arrive via import or a direct API
call, and a threshold of `-5` or `500` would silently produce nonsense validation on device.

### D-2: Malformed config falls back to defaults, it does not disable validation

**Decision**: A bad value means "use the default", never "skip the check".

**Rationale**: Failing open is the worst outcome for a validation feature — it looks like it
worked. This is enforced on the device too, but the API should not have let it through.

---

## 6. Type/Constant Mappings

| Key | Type | Valid range |
|---|---|---|
| `accuracyThreshold` | number | > 0 |
| `detectOverlaps` | boolean | — |
| `overlapThreshold` | number | 0 < x ≤ 100 |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing forms with no `geoConfig` unaffected
- [x] Existing API consumers unaffected — validation only tightens a previously free-form subkey

### Mobile App Impact
- [ ] Sync endpoints affected: none structurally
- [x] Mobile relies on this to trust the values it reads

---

## 8. Security Considerations

- [x] Input validation added at a previously unvalidated boundary — a small improvement
- [x] No permission change: authoring config already requires form-edit rights

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Integration | Create form with `geoConfig` → fetch → identical |
| Integration | **Publish → fetch published version → `geoConfig` still present** (the silent-failure guard) |
| Integration | Mobile form endpoint returns `geoConfig` unchanged |
| Unit | Rejects negative area, threshold 0 / 101 / `"20"` |

**Hours breakdown**

| Unit | h |
|---|---|
| Round-trip tests: create → publish → mobile fetch | 1 |
| Reject nonsensical values | 0.5 |
| Verify `extra` survives the `FormPublishedVersion` snapshot | 1 |
| **Total** | **2.5** |

---

## 10. Open Questions

- [ ] Does form **import** (`FB-016-xlsform-import`) preserve `extra.geoConfig`? Out of scope
      here, but worth a follow-up if XLSForm round-tripping matters for polygon questions

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T9)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-5)
- Related: `doc/design/FB-002B-form-builder-version-schema.md`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
