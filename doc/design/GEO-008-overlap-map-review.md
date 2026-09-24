# Feature Design Document

## Feature: Overlap Map Review Screen

**Task ID**: GEO-008 (breakdown ref: T5)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft — **note added 2026-09-18 (GEO-014)**; §10 questions answered 2026-09-24 (D-3, D-4)
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

> **🔴 The numbering is a contract with GEO-007, added 2026-09-23 (D-11).**
> The error message now reads `Overlaps 3 plots: #1 (34.0%), #2 (28.3%), #3 (22.5%)` and carries
> **no names** — on a form with an administration cascade the generated datapoint name is an
> administrative path six lines long, which identified nothing on device.
>
> So identity moved here, and the labels must line up: **this screen labels each polygon by its
> position in `runOverlapCheck`'s `conflicts` array, which is sorted worst-overlap-first.** Sort
> the polygons any other way — by distance, by name, by arrival — and `#2` in the error is a
> different plot from `#2` on the map, which is worse than no number at all.

### User Acceptance Criteria
- [ ] Reachable from the overlap error
- [ ] Current polygon in one colour, overlapping polygons in another
- [ ] Viewport auto-fits all displayed polygons
- [ ] **Each overlapping polygon carries its `#n` label**, matching the error text (GEO-007 D-11)
- [ ] Tapping a polygon shows that datapoint's name — this screen is now the **only** place the
      name appears, which is also where it is useful
- [ ] Satellite basemap when online
- [ ] Offline: polygons still render, with a scale reference and a clear
      "imagery unavailable offline" notice
- [ ] A disclaimer that satellite imagery may be outdated
- [ ] Read-only — edits happen back in the form field
- [ ] **Poor-accuracy vertices carry the red dot the capture screen already uses** (`.vertex-poor`
      in `map-draw.html`), on the current polygon **and** every conflicting one, against the
      question's own accuracy threshold (D-4)
- [ ] A vertex with no accuracy (tapped, or entered on the webform) is never marked
- [ ] The legend reads as GPS quality, never as verification — e.g. *"GPS accuracy worse than
      Xm"* — per GEO-014 §8

### Technical Acceptance Criteria
- [ ] Reuses GEO-001's WebView map host and bridge — none of it re-paid
- [ ] The tile source comes from **one resolver function** (see D-1)
- [ ] The resolver's template is **injected into `map-draw.html`** like the other `{{…}}` values;
      the hardcoded `tile.openstreetmap.org` line goes. The capture screen and the detail preview
      use the same page, so they get the resolver too — there is one tile source in the app
- [ ] Each entry in `runOverlapCheck`'s `conflicts` carries that candidate's **coordinates, arity
      preserved** (`[lat, lng]` or `[lat, lng, acc]`). They are already in memory when the conflict
      is built; the screen must not re-read the datapoints. Additive change to GEO-007's contract

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

### D-3: Polygons-only offline is accepted for this release (2026-09-24)

**Decision**: Ship Path A of `doc/claude/offline-satellite-imagery-plan.md`. Offline imagery is
still wanted, so the integration prep in that plan's §12 runs **now**, alongside this build.

**Impact**: No dev build for this screen. Path A and Path B both run in Expo Go. Only Path B′
(a native map SDK) would need one, and B′ is gated on licensing (plan §12.2).

### D-4: Accuracy is shown as the capture screen's red vertex dot (2026-09-24)

**Decision**: Reuse the capture screen's vertex rendering unchanged, with the real threshold
passed in (the detail preview passes `0`, which turns marking off). No new visual.

**Rationale**: The enumerator already reads a red dot as "this corner was measured loosely". The
review screen keeps that meaning, and a conflict next to red dots reads as *maybe GPS noise*
rather than *definitely a real intersection*.

**Impact**: Needs the conflict's coordinates (Technical AC above). See §10 for the colour clash
with red conflicting polygons.

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
| Red accuracy dots on all polygons + conflict coordinates (D-4) | 0.5 |
| **Device pass** | 1.5 |
| **Total** | **5** |

The `file://` tile spike (imagery plan §12.1, 2h) is scoped separately. It prepares Path B and
does not ship in this screen.

---

## 10. Open Questions

- [x] ~~Offline, is a polygons-only view acceptable?~~ **Yes, for now** → D-3. Offline imagery
      prep continues in parallel: `doc/claude/offline-satellite-imagery-plan.md` §12
- [x] ~~Should this screen show the accuracy behind each polygon?~~ **Yes, with the existing red
      dot** → D-4
- [ ] **Red now means two things.** §6 draws conflicting polygons red, and D-4 draws poor
      vertices red. A red dot on a red outline is still visible, since the dot is filled and has a
      dark border, but the colour no longer means one thing. Recommendation: draw conflicting
      polygons in **amber** and keep red for "re-walk this corner". The alternative is to keep
      both red and accept the overlap in meaning.
- [ ] **Which online satellite provider?** Today's map draws OpenStreetMap *street* tiles, not
      satellite imagery, so the "satellite basemap when online" AC cannot be met yet. Pick the
      provider in the same vendor conversation as the offline terms (imagery plan §12.3), since
      it is the same contract

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
