# Feature Design Document

## Feature: Overlap Map Review Screen

**Task ID**: GEO-008 (breakdown ref: T5)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Built 2026-09-24 — all ACs met except "satellite basemap when online", which is
blocked on §10's provider question. Decisions D-5 and D-6 added; §10's colour question answered.
Earlier: note added 2026-09-18 (GEO-014); §10 questions answered 2026-09-24 (D-3, D-4)
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
- [x] Reachable from the overlap error
- [x] Current polygon in one colour, overlapping polygons in another
- [x] Viewport auto-fits all displayed polygons
- [x] **Each overlapping polygon carries its `#n` label**, matching the error text (GEO-007 D-11)
- [x] Tapping a polygon shows that datapoint's name — this screen is now the **only** place the
      name appears, which is also where it is useful
- [ ] Satellite basemap when online — **not met, and not meetable yet**: the resolver returns
      OpenStreetMap *street* tiles because no satellite provider has been chosen. Blocked on §10's
      provider question (imagery plan §12.3). Swapping the provider is a one-line change to
      `NETWORK_TILE_TEMPLATE` in `app/src/lib/map-tiles.js`
- [x] Offline: polygons still render, with a scale reference and a clear
      "imagery unavailable offline" notice
- [x] A disclaimer that satellite imagery may be outdated
- [x] Read-only — edits happen back in the form field
- [x] **Poor-accuracy vertices carry the red dot the capture screen already uses** (`.vertex-poor`
      in `map-draw.html`), on the current polygon **and** every conflicting one, against the
      question's own accuracy threshold (D-4)
- [x] A vertex with no accuracy (tapped, or entered on the webform) is never marked
- [x] The legend reads as GPS quality, never as verification — e.g. *"GPS accuracy worse than
      Xm"* — per GEO-014 §8

### Technical Acceptance Criteria
- [x] Reuses GEO-001's WebView map host and bridge — none of it re-paid
- [x] The tile source comes from **one resolver function** (see D-1) — `resolveTileSource` /
      `currentTileSource` in `app/src/lib/map-tiles.js`
- [x] The resolver's template is **injected into `map-draw.html`** like the other `{{…}}` values;
      the hardcoded `tile.openstreetmap.org` line goes. The capture screen and the detail preview
      use the same page, so they get the resolver too — there is one tile source in the app
- [x] Each entry in `runOverlapCheck`'s `conflicts` carries that candidate's **coordinates, arity
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

**Impact**: Needs the conflict's coordinates (Technical AC above). The colour clash that created
is resolved by D-5.

### D-5: Conflicting polygons are amber, not red (2026-09-24)

**Decision**: Take §10's recommendation. Current plot cyan `#00bcd4`, conflicting plots amber
`#ffb300`, and red stays exclusively `.vertex-poor`.

**Rationale**: D-4 put a red dot on the conflicting polygons as well as the current one, so red
was about to mean two things on one screen — "this corner was measured loosely" and "this is the
plot you overlap". Those two have opposite remedies: one says re-walk a stretch, the other says go
and talk to a neighbour. One colour carrying both is how a GPS artefact gets read as a boundary
dispute.

**Impact**: §6's table changes from the reference implementation. Cyan against amber also survives
the common case better than cyan against red: the two polygons usually occupy the same pixels.

### D-6: A tap is answered by a native panel, not a Leaflet popup (2026-09-24)

**Decision**: The page posts `polygonTapped {index}` over GEO-001's existing bridge; `index: null`
is the plot being worked on, a number is that conflict. The name is rendered by React Native.

**Rationale**: The page never receives a name at all — only `{label, coordinates}` are baked into
it — so the WebView holds no farmer identity to leak or to lose on a reload. And the panel is
ordinary React Native, which the existing test harness can assert on; a `bindPopup` would have
been verifiable on device only.

**Impact**: One new message type on the bridge, in the direction that already exists.

---

## 6. Type/Constant Mappings

| Element | Colour | Value |
|---|---|---|
| Current plot | Cyan | `#00bcd4` |
| Overlapping plots | Amber | `#ffb300` — D-5, not the reference implementation's red |
| Poor-accuracy vertex | Red | `#ec003f`, `.vertex-poor`, unchanged from the capture screen |

The hex values are stated twice, once in `map-draw.html` and once in `OverlapMapView`'s legend
styles, because the WebView and React Native share nothing. The one that must match exactly is the
red: the legend is explaining a dot the page drew.

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] The screen is new, but the Technical AC's "one tile source" is not: `map-draw.html` lost its
      hardcoded provider and gained `{{tileUrl}}`, `{{review}}`, `{{conflicts}}` and
      `{{fitBounds}}`, so the capture screen and the detail preview were both touched. Neither
      changes behaviour — `readonly` still means "cannot be edited", and the new `staticMap`
      (`readonly && !review`) is what keeps the preview from stealing a scroll gesture, exactly as
      `readonly` used to
- [x] `runOverlapCheck`'s conflicts gained a `coordinates` key. Additive; every existing consumer
      reads named keys
- [x] `map-draw.html`'s vertex markers became non-interactive when `readonly`. On the preview
      nothing changes (they had no handlers); on the review screen it is what lets a tap reach the
      polygon underneath instead of being swallowed by a corner dot

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
- [x] ~~**Red now means two things.**~~ **Resolved: conflicting polygons are amber** → D-5. Red is
      `.vertex-poor` and nothing else
- [ ] **Which online satellite provider?** Today's map draws OpenStreetMap *street* tiles, not
      satellite imagery, so the "satellite basemap when online" AC cannot be met yet. Pick the
      provider in the same vendor conversation as the offline terms (imagery plan §12.3), since
      it is the same contract. **Still open, and it is the only AC left unticked.** The seam is
      built: `NETWORK_TILE_TEMPLATE` in `app/src/lib/map-tiles.js` is the one line that changes

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
