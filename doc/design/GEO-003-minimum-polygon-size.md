# Feature Design Document

## Feature: Minimum Polygon Size Validation

**Task ID**: GEO-003 (breakdown ref: T7)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 1 — Capture & validity
**Estimate**: 2.25h ≈ 0.25 day (Mobile)
**Depends on**: GEO-001

---

## 1. Context & Problem Statement

```
Currently:
- No area check exists anywhere. akvo-react-form has no area calculation at all.

Goal:
- Reject polygons too small to be a real plot — the signature of an accidental double-tap
  rather than a captured boundary.
- Show the enclosed area live during capture so the enumerator can sanity-check their own work.
```

---

## 2. Requirements

### User Acceptance Criteria
- [ ] A polygon below the minimum area → clear error, submission blocked
- [ ] The enclosed area is visible during capture once ≥3 points exist
- [ ] Message states the minimum in square metres

### User Acceptance Criteria — shared validation behaviour *(added from design review)*

- [ ] This check is one entry in a **validation report**, not a standalone message — pressing
      Validate shows a green tick on success, or a list of **every** failed rule
- [ ] **Warn vs block follows the question's `required` flag**: a required question blocks
      submission on failure or when never validated; an optional one warns and lets the
      enumerator proceed
- [ ] The Validate button is hidden entirely when the question has no validation rules configured

> These behaviours are shared across all polygon validations and are specified once in
> **GEO-007 D-7 and D-8**. The area check must plug into that report structure rather than
> surfacing its own separate error.

### Technical Acceptance Criteria
- [ ] Area is **geodesic**, correct on a spheroid at plot scale
- [ ] Fixed floor of 10 m², not configurable
- [ ] `geoshape` only
- [ ] Unit-tested against known squares at several latitudes

---

## 3. Data Model Changes

**None.**

---

## 4. API Contract

**No API change.**

---

## 5. Decision Log

### D-1: Do NOT port the reference validator's area calculation

**Decision**: Use `@turf/area`.

**Rationale**: `PolygonValidator.calculateAreaInSquareMeters()` multiplies square degrees by
`111320.0 * cos(latitude)` — an **equirectangular approximation**. Our NFR-7 requires geodesic
area; planar arithmetic that treats degrees as metres is not acceptable. `@turf/area` is
geodesic and already a declared dependency in the monorepo.

**Impact**: This is one of three places the reference implementation must not be copied
verbatim. A reviewer seeing Kotlin source next to our JS should know this divergence is
deliberate.

### D-2: 10 m² is a fixed floor, not a configurable threshold

**Decision**: Hardcoded at 10 m².

**Rationale**: 10 m² is 3.2 m × 3.2 m — below any real land plot, so it only ever catches
accidents. Making it configurable invites a form that disables the check. A programme wanting a
*stricter* floor (reject anything under 100 m²) is a policy question that can be revisited; it
is not needed for phase 1.

**Impact**: ⚠️ Narrows the original request, which asked for a checkbox and configurable value.
Same caveat as GEO-002 D-1 — flag it, do not let it pass silently.

---

## 6. Type/Constant Mappings

| Rule | Value | Where it lives |
|---|---|---|
| Minimum area | `10 m²` | Constant in mobile validation module |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing datapoints unaffected — validation runs at capture

### Mobile App Impact
- [ ] Sync endpoints affected: **none**
- [ ] SQLite schema changes: **no**

---

## 8. Security Considerations

- [x] No new attack surface — pure local computation

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | A square of known side length returns the expected area **at several latitudes** — this is what catches a planar-maths regression (D-1) |
| Unit | 9 m² fails, 11 m² passes |
| Integration | Live area display updates as vertices are added |

**Hours breakdown**

| Unit | h |
|---|---|
| `@turf/area` + threshold check | 0.5 |
| Live enclosed-area display during capture | 0.5 |
| i18n message | 0.25 |
| Tests — known square at several latitudes | 1 |
| **Total** | **2.25** |

> Scheduled with GEO-002 the combined cost is closer to **4h than 4.75h** — they share the
> validation plumbing and the i18n pass.

---

## 10. Open Questions

- [ ] Is 10 m² right for the first real programme using this? It is inherited from a
      farm-plot context and has not been checked against our use case.

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T7)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-2.3, FR-5.B, NFR-7)

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
