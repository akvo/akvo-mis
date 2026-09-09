# Feature Design Document

## Feature: Polygon Capture — Draw on the Map

**Task ID**: GEO-001 (breakdown ref: T1)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 1 — Capture & validity
**Estimate**: 12h ≈ 1.5 days (Mobile)

---

## 1. Context & Problem Statement

```
Currently:
- The mobile app has NO polygon field. `TypeGeo.js` captures a single lat/lng point only.
- `geoshape` questions ALREADY reach the app (same WebFormDetailSerializer as web) and fall
  through the `default:` branch of QuestionField.js:157 — rendering a plain TEXT INPUT.
- There is no map library and no geometry library in app/package.json.
- Web already captures polygons fine via akvo-react-form 2.7.9 (TypeGeoDrawing).

Goal:
- A geoshape question renders a map on mobile where the enumerator taps to place vertices.
- The stored value is byte-compatible with what web produces, so both clients are
  indistinguishable to the backend.
```

**This is the prerequisite for every other GEO task.** Nothing else on mobile can be
integrated or demoed without it.

---

## 2. Requirements

### User Acceptance Criteria
- [ ] A `geoshape` question renders a map with drawing controls, not a text box
- [ ] Tap the map to append a vertex
- [ ] Drag an existing vertex to correct it
- [ ] Undo the last vertex, remove any single vertex, clear all (confirm above 3 points)
- [ ] See live point count and, once ≥3 points, the enclosed area
- [ ] "Centre on me" recentres the map without appending a point
- [ ] Leaving and returning to the question group preserves captured points

### Technical Acceptance Criteria
- [ ] Value format is `[[lat, lng], [lat, lng], …]` — identical to ARF's
- [ ] Round-trips through `datapoints.json` and form save/resume without precision loss
- [ ] Compatible with `xlsform_export.py:102` geoshape export
- [ ] No new native module — uses the installed `react-native-webview`
- [ ] Files stay within the 200–400 line guideline (Airbnb ESLint enforced)

### Out of scope
- GPS boundary walking → **GEO-004**
- Overlap detection → **GEO-007**
- Offline satellite imagery → see `doc/claude/offline-satellite-imagery-plan.md`

---

## 3. Data Model Changes

**None.** No backend model change, no SQLite schema change.

The polygon is stored as an ordinary answer in the existing `datapoints.json` blob
(`{questionId: answer}`), exactly like any other question type.

---

## 4. API Contract

**No API change.** `geoshape` (type 14) already exists in `QuestionTypes` and is already
serialized to mobile by `WebFormDetailSerializer`.

---

## 5. Decision Log

### D-1: Map rendering approach

**Options Considered**:
1. `react-native-maps` — real native map component
2. WebView + Leaflet — reuse the installed `react-native-webview`
3. Plain SVG, no basemap

**Decision**: WebView + Leaflet.

**Rationale**: `react-native-webview` 13.13.5 is already a dependency, so no new native module
and no EAS dev-client rebuild is forced by this task. ARF's `TypeGeoDrawing` already renders
geometry with Leaflet, so `GeoGeometry`, `RecordedMarkers`, `FitBounds` and `MapClickHandler`
port into the WebView page nearly verbatim — one map implementation serving two hosts.

**Impact**: Introduces an RN↔WebView `postMessage` bridge that has **no ARF precedent** (ARF's
Leaflet runs in the same JS context). This is the single largest unknown in the task.

### ⚠️ D-1b: UNRESOLVED — is the stored value GeoJSON or ARF's array?

**Status: BLOCKING. Settle before building.**

Design review answered "the JSON will follow the GeoJSON standard — correct". But the format
this task is currently specified to produce is **ARF #192's**, and the two are not the same:

| | ARF #192 (what this doc specifies) | GeoJSON (RFC 7946) |
|---|---|---|
| Structure | `[[lat, lng], [lat, lng], …]` | `{"type":"Polygon","coordinates":[[[lng,lat], …]]}` |
| **Axis order** | **latitude first** | **longitude first** |
| Ring closure | implicit | first point **repeated** at the end |
| Wrapper | none — a bare array | typed object |

**The axis order is the dangerous part.** `[9.03, 38.74]` read as GeoJSON is longitude 9.03,
latitude 38.74 — a different continent. A silent swap does not crash; it produces plausible
coordinates in the wrong place, and every downstream area and overlap calculation is quietly
wrong.

**Options**:
1. **Keep ARF's format.** Web and mobile stay identical, no upstream change. "GeoJSON" in the
   review may simply have meant "JSON", loosely
2. **Store GeoJSON, convert at the boundary.** Clients keep ARF's array; the backend converts on
   write. Costs a conversion layer and a decision about which is canonical
3. **Change ARF upstream to emit GeoJSON.** Cleanest long-term, breaks a published contract, and
   requires an upstream release

**Recommendation**: confirm what was actually meant before writing any code. If GeoJSON is a real
requirement — likely if the data must be consumed by GIS tooling or exported for an auditor —
option 2 is the least disruptive, and the conversion belongs in **GEO-005/GEO-010**, not here.

**Whatever is chosen, add an axis-order regression test.** A fixture with clearly asymmetric
coordinates (a plot near the equator but far from the prime meridian) fails loudly on a swap;
a symmetric test fixture will not catch it.

### D-2: Port target

**Decision**: Port `TypeGeoDrawing` from **akvo-react-form #192** (commit `e7d786d`), not from
the Kotlin reference validator.

**Rationale**: ARF is a working implementation of exactly this capture UX, in the same language,
producing the value format we must match. The Kotlin validator has no capture UI at all.

### D-3: Drawing-first ordering has an imagery dependency

**Decision**: Accept that phase 1 is effectively **connected-only** in the field.

**Rationale**: GPS walking (GEO-004) works offline because the shape comes from the enumerator's
feet. **Drawing does not — you cannot trace a boundary you cannot see.** With no tiles, an
enumerator offline sees an empty canvas with nothing to tap against.

**Impact**: Either offline imagery becomes a blocker, or drawing happens where there is
connectivity (not at the plot), or phase 1 is accepted as connected-only with true offline
capture arriving with GEO-004. **This must be stated to the product owner, not discovered in
the field.**

---

## 6. Type/Constant Mappings

| Frontend/Editor | Backend Constant | DB Value | Mobile |
|-----------------|------------------|----------|--------|
| `"geoshape"` | `QuestionTypes.geoshape` | `14` | `QUESTION_TYPES.geoshape` *(to add)* |
| `"geotrace"` | `QuestionTypes.geotrace` | `15` | `QUESTION_TYPES.geotrace` *(to add)* |

---

## 7. Compatibility & Migration

### The 7 integration touchpoints

Adding the type to `QUESTION_TYPES` alone produces a field that **renders but validates
wrongly**. All seven must land together:

| # | File | Change | Symptom if skipped |
|---|---|---|---|
| 1 | `app/src/lib/constants.js:26` | Add `geoshape`, `geotrace` | Type never matches |
| 2 | `app/src/form/components/QuestionField.js:157` | `case` → `<TypeGeoDrawing>` | Renders a plain text input |
| 3 | `app/src/form/fields/TypeGeoDrawing.js` + `fields/index.js` | New component + export | Nothing to render |
| 4 | `app/src/form/lib/index.js:364` | `case` → `Yup.array()`, mirroring `'geo'` | Falls to `default: Yup.string()` — **an array fails a string schema** |
| 5 | `app/src/form/lib/index.js:406` | Exclude polygon types from datapoint-name generation | Raw coordinates leak into the datapoint name |
| 6 | `app/src/form/lib/index.js:462` | Add the `geo`-style `'' → []` branch in `transformValue` | Empty polygon becomes `''`; breaks resume |
| 7 | `app/src/form/support/FormNavigation.js:56` and `:102` | Add polygon types to the defaultVal list | Unanswered polygon defaults to `''` not `null` — **wrong required-check** |

**Items 4 and 7 are the quiet failures** — the field looks correct on screen and validates wrongly.

### Backward Compatibility
- [x] Forms without polygon questions behave identically
- [x] Datapoints collected before this feature remain readable and syncable
- [x] Web capture unaffected

### Mobile App Impact
- [ ] Sync endpoints affected: **none**
- [ ] SQLite schema changes: **no**
- [ ] Version detection: not required — additive question-type support

---

## 8. Security Considerations

- [x] No new permissions requested (foreground location already used by `TypeGeo`)
- [x] WebView loads **local content only** — no remote code execution surface beyond the
      basemap tile requests
- [ ] Verify `originWhitelist` is restrictive and JS injection is limited to the bridge payload

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | `transformValue` for polygon types; validation schema returns `Yup.array()`; datapoint-name generation excludes polygons |
| Integration | Capture → save draft → reopen → points intact; value shape matches ARF |
| Manual (device) | Tap/drag/undo/clear on a real Android device; WebView load race; rotation |

**Hours breakdown**

| Sub-task | Unit | h |
|---|---|---|
| T1a | Bundle Leaflet as an offline asset | 0.5 |
| | Leaflet page — render polygon + vertex markers, tap, drag | 1 |
| | `postMessage` bridge, both directions | 0.5 |
| | **On-device debugging — WebView load race, message timing, Android quirks** | 4 |
| T1b | Tap-to-add | 0.5 |
| | Drag a vertex | 0.5 |
| | Undo / remove / clear + confirm | 0.5 |
| | `CoordinatePreview` (plain text port) | 0.5 |
| T1c | The 7 touchpoints | 1 |
| | Unit tests | 1 |
| | **Device pass** | 2 |
| | **Total** | **12** |

Half of this task is device debugging and testing. That is the part AI assistance does not
compress, and the part most likely to be wrong in either direction.

---

## 10. Open Questions

- [ ] 🔴 **D-1b: GeoJSON or ARF's `[[lat, lng]]`?** Blocking — settle before building
- [ ] Does phase 1 ship as connected-only (D-3), or does offline imagery come with it?
- [ ] **Basemap for phase 1 is OSM, not satellite** *(design review)*. Confirmed direction:
      *"for right now we use OpenStreetMap, the non-satellite imagery"*, and
      *"the absence of base tiles should not stop them from [capturing] polygons"* — so the map
      must degrade to a usable drawing surface rather than blocking capture
- [ ] **Tile caching is part of the sync process** *(design review)*: tiles for the assigned
      collection area are downloaded before going to the field, alongside the records. Not in
      this task's scope, but the tile-source resolver (GEO-008 D-1) is where it will land
- [ ] Does the RN↔WebView bridge drop points on a fast drag? **Prototype this first.**
- [ ] Leaflet bundled as an inline HTML string or via `expo-asset`?

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T1)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-1)
- Port source: `akvo/akvo-react-form` #192, commit `e7d786d`, `src/fields/TypeGeoDrawing.jsx`
- Imagery decision: `doc/claude/offline-satellite-imagery-plan.md`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
