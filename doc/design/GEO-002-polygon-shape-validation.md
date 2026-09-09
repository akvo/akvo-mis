# Feature Design Document

## Feature: Polygon Shape Validation

**Task ID**: GEO-002 (breakdown ref: T6)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 1 — Capture & validity
**Estimate**: 2.5h ≈ 0.5 day (Mobile)
**Depends on**: GEO-001

---

## 1. Context & Problem Statement

```
Currently:
- Nothing validates polygon geometry on ANY platform.
- akvo-react-form implements a minimum-point rule and nothing else — no self-intersection
  check, no area check.
- The Kotlin reference validator has the logic, but in Kotlin/JTS against a different
  data format.

Goal:
- A captured polygon is guaranteed to BE a polygon: parseable, ≥3 vertices, no self-crossing.
```

**Why this matters beyond tidiness**: overlap detection (GEO-007) computes intersection areas.
A self-crossing "bowtie" has mathematically ambiguous area, so garbage geometry makes the
overlap maths meaningless. This task is the precondition that makes GEO-007 trustworthy.

---

## 2. Requirements

### User Acceptance Criteria
- [ ] Fewer than 3 vertices → clear error, submission blocked
- [ ] A self-crossing boundary → clear error, submission blocked
- [ ] Unparseable value → clear error, submission blocked
- [ ] Each message identifies which question failed
- [ ] Messages appear in the enumerator's language

### User Acceptance Criteria — shared validation behaviour *(added from design review)*

- [ ] This check is one entry in a **validation report**, not a standalone message — pressing
      Validate shows a green tick on success, or a list of **every** failed rule
- [ ] **Warn vs block follows the question's `required` flag**: a required question blocks
      submission on failure or when never validated; an optional one warns and lets the
      enumerator proceed
- [ ] The Validate button is hidden entirely when the question has no validation rules configured

> These behaviours are shared across all polygon validations and are specified once in
> **GEO-007 D-7 and D-8**. The shape check must plug into that report structure rather than
> surfacing its own separate error.

### Technical Acceptance Criteria
- [ ] Checks are **fixed constants, not configurable** (see D-1)
- [ ] `geoshape` only — `geotrace` is exempt
- [ ] Runs fully offline
- [ ] Geometry maths unit-tested independently of React Native rendering

---

## 3. Data Model Changes

**None.**

---

## 4. API Contract

**No API change.**

---

## 5. Decision Log

### D-1: These checks are NOT configurable

**Options Considered**:
1. `validateShape` checkbox + `minPoints` integer in the form builder (as originally requested)
2. Always applied at fixed floors, no configuration

**Decision**: Option 2 — always on, fixed.

**Rationale**: Shape validity is not a policy choice. A 2-point "polygon" or a self-intersecting
bowtie is not a stricter standard — it is **not a polygon**. An enable-checkbox for "should this
be a valid polygon?" has no meaningful *off* state, and a stored `validateShape: false` key
could be hand-edited to silently disable validation.

**Impact**: ⚠️ **This narrows the original request**, which asked for a checkbox plus a
configurable integer. The check still ships; it is simply always on. Flag this to the requester
rather than letting it pass as delivered-as-asked.

### D-2: Minimum vertices is 3, not the reference validator's 4

**Decision**: `>= 3`.

**Rationale**: The reference validator uses `MIN_VERTICES = 4` — "3 distinct points + 1 closing
point" — because ODK geoshape strings repeat the first point at the end. **Our format (from ARF)
does not duplicate the closing point.** Copying 4 verbatim would fail every valid triangle.

### D-3: Self-intersection via `@turf/kinks`

**Decision**: Use `@turf/kinks`; do not port the reference validator's JTS `polygon.isValid`.

**Rationale**: `@turf/turf` is already a declared dependency in `frontend/package.json` and is
pure JS, so it runs in React Native. Import the **scoped submodule** (`@turf/kinks`), never the
full bundle — mobile bundle size.

---

## 6. Type/Constant Mappings

| Rule | Value | Where it lives |
|---|---|---|
| Minimum vertices | `3` | Constant in mobile validation module |
| Self-intersection | — | `@turf/kinks` |
| Parse check | — | Array shape guard |

**No `geoConfig` keys.** See GEO-009 for what *is* configurable.

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Forms without polygon questions unaffected
- [x] Existing datapoints unaffected — validation runs at capture, not retroactively

### Mobile App Impact
- [ ] Sync endpoints affected: **none**
- [ ] SQLite schema changes: **no**

---

## 8. Security Considerations

- [x] No new attack surface — pure local computation
- [x] Input is already-parsed JSON from the app's own state

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Valid triangle passes; 2-point fails; bowtie fails; unparseable fails |
| Unit | **Regression guard for D-2**: a 3-vertex triangle must PASS (catches the `MIN_VERTICES = 4` trap) |
| Integration | Error surfaces in `err-validation-text` and blocks submit |

**Hours breakdown**

| Unit | h |
|---|---|
| Parse check, min-points, `@turf/kinks` self-intersection | 0.5 |
| i18n messages | 0.5 |
| Wire into the validator | 0.5 |
| Tests with known fixtures | 1 |
| **Total** | **2.5** |

---

## 10. Open Questions

- [ ] Confirm with the requester that the always-on decision (D-1) is acceptable given the
      original ask was for a configurable checkbox

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T6)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-2, FR-5.B)
- Reference validator: `akvo/african-bamboo-odk-external-validations` → `validation/PolygonValidator.kt`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
