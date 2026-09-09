# Feature Design Document

## Feature: Overlap Map Review Screen

**Task ID**: GEO-008 (breakdown ref: T5)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 3 — Overlap detection
**Estimate**: 4.5h ≈ 0.5 day (Mobile)
**Depends on**: GEO-001, GEO-007

---

## 1. Context & Problem Statement

```
Currently:
- An overlap error would be text only. The enumerator learns THAT two plots conflict,
  but not WHERE or BY HOW MUCH.

Goal:
- A read-only screen showing the current polygon against the conflicting ones, so the
  conflict is inspectable rather than asserted.
```

Source acceptance criteria are explicit: *"I should be able to select overlapping plots to see
the farmer name for each and how it differs from the farmer I am working on."*

---

## 2. Requirements

### User Acceptance Criteria
- [ ] Reachable from the overlap error
- [ ] Current polygon in one colour, overlapping polygons in another
- [ ] Viewport auto-fits all displayed polygons
- [ ] Tapping a polygon shows that datapoint's name
- [ ] Satellite basemap when online
- [ ] Offline: polygons still render, with a scale reference and a clear
      "imagery unavailable offline" notice
- [ ] A disclaimer that satellite imagery may be outdated
- [ ] Read-only — edits happen back in the form field

### Technical Acceptance Criteria
- [ ] Reuses GEO-001's WebView map host and bridge — none of it re-paid
- [ ] The tile source comes from **one resolver function** (see D-1)

---

## 3. Data Model Changes

**None.**

---

## 4. API Contract

**No API change.**

---

## 5. Decision Log

### D-1: Build the tile-source seam now, even though offline imagery is deferred

**Decision**: The map's tile URL must come from **one function** taking the viewport and
returning a template. The offline notice is driven by **that function's outcome**, not by a
connectivity check.

**Rationale**: Offline satellite imagery is a separate, licensing-blocked decision. If the tile
source is hardcoded, adding imagery later is a rewrite; behind a resolver it is a configuration
change touching one module.

**Impact**: A naive `isConnected` check for the offline notice breaks the moment local tile
packs exist — the device can be offline *and* have imagery. Drive the notice from the resolver.

### D-2: Read-only

**Decision**: No editing on this screen.

**Rationale**: Two editing surfaces for one value is a synchronisation problem with no
compensating benefit. The enumerator reviews here and corrects in the field.

---

## 6. Type/Constant Mappings

| Element | Colour (reference implementation) |
|---|---|
| Current plot | Cyan |
| Overlapping plots | Red |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] New screen; nothing existing changes

### Mobile App Impact
- [ ] Sync endpoints affected: none
- [ ] SQLite schema changes: no

---

## 8. Security Considerations

- [x] Displays datapoint names the enumerator can already see in their assignment

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Resolver returns local → network → none in the right order |
| Integration | Auto-fit covers all polygons; tap returns the right name |
| Manual (device) | Offline behaviour: polygons render, notice shown, no blank crash |

**Hours breakdown**

| Unit | h |
|---|---|
| Render multiple polygons, current vs conflicting colours | 0.5 |
| Auto-fit viewport to all polygons | 0.5 |
| Tap a polygon → show datapoint name | 0.5 |
| Tile-source resolver seam + offline notice | 1 |
| Navigation from the error, scale bar, disclaimer | 0.5 |
| **Device pass** | 1.5 |
| **Total** | **4.5** |

---

## 10. Open Questions

- [ ] Offline, is a polygons-only view acceptable? Without imagery the enumerator sees *that*
      A intersects B but not the river or treeline that would settle the dispute — see
      `doc/claude/offline-satellite-imagery-plan.md`

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T5)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-6)
- Imagery decision: `doc/claude/offline-satellite-imagery-plan.md`
- Reference: `akvo/african-bamboo-odk-external-validations` → `validation/MapPreviewActivity.kt`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
