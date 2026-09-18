# Feature Design Document

## Feature: Minimum Polygon Size Validation

**Task ID**: GEO-003 (breakdown ref: T7)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Delivered 2026-09-17 — verified on a device
**Phase**: 1 — Capture & validity
**Estimate**: 2.5h ≈ 0.5 day (Mobile + Frontend)
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
- [x] A polygon below the minimum area → clear error, submission blocked
- [x] The enclosed area is visible during capture once ≥3 points exist — **already met by
      GEO-001** on both surfaces; see §9
- [x] Message states the minimum in square metres — and the *maximum* in hectares (D-5), each
      unit chosen for its magnitude

### User Acceptance Criteria — shared validation behaviour *(added from design review)*

- [ ] This check is one entry in a **validation report**, not a standalone message — pressing
      Validate shows a green tick on success, or a list of **every** failed rule
- [ ] **Warn vs block follows the question's `required` flag**: a required question blocks
      submission on failure or when never validated; an optional one warns and lets the
      enumerator proceed
- [ ] ~~The Validate button is hidden entirely when the question has no validation rules
      configured~~ — **unreachable, struck 2026-09-17.** See GEO-002 §2 for why.

> These behaviours are shared across all polygon validations and are specified once in
> **GEO-007 D-7 and D-8**. The area check must plug into that report structure rather than
> surfacing its own separate error.

> **UX workflow, `required` handling and edge cases are specified once in GEO-002 §2.1**, covering
> both phase-1 rules together because an enumerator meets them together. E-5 and E-6 there are
> this task's cases: a self-crossing polygon **skips** the area check rather than failing it,
> because a bowtie's area is ambiguous.

### Technical Acceptance Criteria
- [x] Area is correct to well under 1 % at plot scale (see D-3 — the merged helper is
      equirectangular, not geodesic, and that is now accepted)
- [x] Fixed floor of 10 m² — the **threshold** is not configurable; its **severity** is (D-4)
- [x] An **optional** upper bound, `maxAreaHa`, absent by default (D-5)
- [x] `geoshape` only
- [x] Unit-tested against known squares at several latitudes (0°, 25°, 51°)
- [x] Implemented as an entry in the rule registry required by GEO-007 D-8, to the contract
      specified in **GEO-013**

---

## 3. Data Model Changes

**None.**

---

## 4. API Contract

**No API change.**

---

## 5. Decision Log

### D-1: Do NOT port the reference validator's area calculation — ⚠️ `@turf` premise wrong, see D-3

**Decision**: Use `@turf/area`.

**Rationale**: `PolygonValidator.calculateAreaInSquareMeters()` multiplies square degrees by
`111320.0 * cos(latitude)` — an **equirectangular approximation**. Our NFR-7 requires geodesic
area; planar arithmetic that treats degrees as metres is not acceptable. `@turf/area` is
geodesic and already a declared dependency in the monorepo.

**Impact**: This is one of three places the reference implementation must not be copied
verbatim. A reviewer seeing Kotlin source next to our JS should know this divergence is
deliberate.

### D-2: 10 m² is a fixed floor, not a configurable threshold — ⚠️ partly superseded by D-4

**Decision**: Hardcoded at 10 m².

**Rationale**: 10 m² is 3.2 m × 3.2 m — below any real land plot, so it only ever catches
accidents. Making it configurable invites a form that disables the check. A programme wanting a
*stricter* floor (reject anything under 100 m²) is a policy question that can be revisited; it
is not needed for phase 1.

**Impact**: ⚠️ Narrows the original request, which asked for a checkbox and configurable value.
Same caveat as GEO-002 D-1 — flag it, do not let it pass silently.

**Outcome of that flag**: raised and answered on 2026-09-17, same answer as GEO-002 D-1. The
**threshold** stays fixed at 10 m² as this decision argues. The **checkbox** is granted as a
severity switch by D-4.

### D-4: Configurable severity, threshold stays fixed *(2026-09-17)*

**Decision**: identical mechanism to **GEO-002 D-4** — same resolver, same precedence, same
clamp. Read that decision; it is the single source of truth and is not restated here.

| Layer | Key | Type | Default | Authorable in the form builder? |
|---|---|---|---|---|
| Question | `extra.geoConfig.validateArea` | boolean | *(absent)* | No — read only, GEO-002 D-5 |
| Device | `BuildParamsState.validatePolygonArea` | TINYINT `0`/`1` | `1` | n/a — app Settings › Geolocation |

**Why the threshold is treated differently from the switch**: a severity switch cannot produce
bad data, only differently-gated data. A configurable `minAreaSqm` can — set it to `0` and the
check is silently disabled while still reporting as "configured". If a programme genuinely needs
a *stricter* floor (D-2 anticipates "reject anything under 100 m²"), that is a new key with a
minimum of its own, not a reinterpretation of this one.

**Settings label**: *"Block shapes outside the allowed size"*, default ON. Not *"Validate
polygon area"* — the rule runs either way, so that label would be wrong in the off position, and
not *"undersized"* either, since D-5 added an upper bound governed by the same switch.

**Key renamed 2026-09-17**: `validateMinArea` → `validateArea`. One severity switch governs both
bounds, so a name naming only the lower one would have been a permanent misnomer. Free to change
today because nothing authors it yet (GEO-002 D-5); expensive once real forms carry it.

**Shared with GEO-002**: the resolver, the DB migration, and the Settings section. Costed once,
in GEO-002 §9.

**A warned-past undersized polygon is not transmitted**: the web re-derives the area from the
stored answer, which `GeometryView` already does to caption its map preview. See **GEO-002 D-7**
— no payload field, no `FormData` column, no backend change.

### D-5: Maximum area is **configurable and opt-in**, never a fixed ceiling *(2026-09-17)*

**Raised during implementation**: capture is by tapping, and tapping is zoom-dependent. Four taps
at country zoom produce a 10,000 ha polygon in two seconds — the mirror image of the double-tap
the 10 m² floor exists to catch, and far easier to do by accident than its GPS-walked equivalent.

**Options Considered**:
1. A fixed ceiling, e.g. 20 ha, symmetrical with the 10 m² floor
2. `extra.geoConfig.maxAreaHa`, per question, absent by default
3. Nothing — rely on the enumerator noticing the area readout

**Decision**: Option 2.

**Rationale**: the floor and the ceiling are **not the same kind of rule**. 10 m² is defensible as
a constant because it is universal — nothing anyone captures is smaller than a doormat. There is
no equivalent universal ceiling: 20 ha is large for a smallholder plot and small for a forest
concession, a grazing area, a village boundary or a watershed. Akvo MIS is being built as a
generic data-collection platform (GEO-012 §10), so a hardcoded ceiling would make it unable to
capture precisely the features that most need a polygon. A ceiling is a policy threshold; a floor
is a floor.

Option 3 was rejected because the area readout has been on screen throughout and is exactly the
kind of number people stop seeing.

**The argument that made this worth doing now is not data quality — it is GEO-007.** Its entire
< 500 ms target rests on the bbox pre-filter cutting ~10,000 candidates to roughly 5–50. One
continent-sized bbox in the geometry index matches nearly every candidate, so every later
validation on that device degrades toward a full table scan. That surfaces in phase 3 looking
like a performance bug rather than like a bad polygon, which is the worst possible place to first
meet it.

**Contract**:

| | |
|---|---|
| Key | `extra.geoConfig.maxAreaHa` — **hectares**, not m² |
| Absent, non-numeric, or ≤ 0 | The rule does not apply. No ceiling |
| Severity | Shares `validateArea` / `validatePolygonArea` with the floor — one switch, both bounds |
| Gating | No. Mutually exclusive with `minArea`, so at most one of the two can fail |

**Why hectares in the key name**: authoring 20 ha as `200000` invites a lost zero and a 10×
error, and the unit suffix makes a wrong unit visible in stored JSON. The messages follow the
same logic and each use the unit that suits their magnitude — the floor reads *"4 m², below the
10 m² minimum"*, the ceiling *"24.3 ha, above the 20 ha maximum"*. `0.001 ha` and `200000 m²` are
both unreadable.

**Ships without an authoring UI**, exactly as GEO-002 D-5 established: reading a key is free,
authoring one costs an upstream editor release. Absent means inert, so no existing form changes
behaviour. A form can carry the key today via import.

### D-6: A self-crossing shape's area is **marked, not stated** *(2026-09-17)*

**Found on a real device.** A 17-point polygon that crossed itself displayed
`Area: 313.90 ha` beside `⚠ 1 invalid`. The validator had just refused to judge that area
because it is ambiguous (D-2's gating, GEO-002 §2.1.3) — and the status bar printed it anyway,
in the same style as a trustworthy figure.

**Why the figure cannot be trusted**: the shoelace sum is **algebraic**, not absolute. Lobes
wound in opposite directions subtract. Measured with the shipped helper, at ~2.2 km across:

| Shape | Reported area |
|---|---|
| Simple square | 495.68 ha |
| **Symmetric bowtie** | **0.00 ha** |
| Lopsided bowtie | 198.27 ha |

The device screenshot was lucky — one lobe dominated, so 313.90 ha looked plausible. Tangled
slightly differently, the same capture reports 0.00 ha, and **without gating the app would have
rejected a 300-hectare shape for being below the 10 m² minimum.** That is the concrete
justification for D-2's cascade, and until now nothing in the suite pinned it.

**Options Considered**:
1. Leave the figure as-is
2. Suppress it entirely when the ring self-intersects
3. Prefix it with `~` and colour it amber

**Decision**: Option 3, on all three surfaces — `MapDrawView`'s status bar,
`TypeGeoDrawing`'s summary, and `GeometryView`'s web caption.

**Rationale**: Option 1 lets a number lie in the one place an enumerator looks to judge their own
work. Option 2 is honest but removes the rough sense of scale they are using while they fix the
crossing — and the shape is broken anyway, so a rough figure beats none. The tilde and the colour
together say "indicative, do not quote".

**Impact**:
- `areaIsAmbiguous(results)` derives the flag from results **already computed**, so no surface
  pays for a second `kinks` pass
- A regression test in each repo pins the bowtie-reports-~0 behaviour. It is the number the whole
  gating design rests on, and it had no guard
- This does **not** change what is validated. The area check is still skipped on a self-crossing
  ring; only its presentation changed

### D-3: Accept the merged equirectangular area helper *(2026-09-17, revises D-1)*

**Problem**: GEO-001 has already shipped `polygonArea()` in `app/src/form/lib/geometry.js` — an
equirectangular projection around the polygon's mean latitude, then a shoelace sum. D-1 above
rejects *"planar arithmetic that treats degrees as metres"*, and this helper is exactly that
family of approximation. Meanwhile `@turf` is **not a dependency of `app/`** at all, only of
`frontend/` (GEO-002 D-6).

**Decision**: keep the merged helper. Amend NFR-7's "geodesic" wording to a stated accuracy
bound.

**Rationale**: D-1's real objection was to the *reference validator's* `111320 * cos(lat)`
multiplication of raw square degrees, which is meaningfully wrong. The merged helper projects
both axes to metres before the shoelace sum and corrects for meridian convergence at the mean
latitude — under 1 % error for field-sized plots, as its own comment states. A 10 m² floor is
three orders of magnitude away from the boundary where that error decides anything: the test
that matters is *9 m² fails, 11 m² passes*, and no plausible projection error flips it.

**Impact**: the phase-1 spike *"does `@turf` behave on a real device?"* (GEO-007) is no longer
on this task's critical path. The §9 latitude tests still stand, and now serve to pin the
accuracy bound rather than to prove geodesic maths.

**ponytail ceiling**: valid while plots stay well under a degree of latitude. A polygon spanning
more than that needs spherical excess — the existing code comment already says so.

**Note for a future reader**: GEO-002 D-6 adds `@turf/kinks` to `app/`, so turf *will* be on the
mobile dependency list. `@turf/area` is still deliberately not used — the helper is merged,
tested and accurate enough by three orders of magnitude for a 10 m² floor. What flips that is
area becoming an authoritative figure (a certificate, a payment), not turf merely being present.

---

## 6. Type/Constant Mappings

| Rule | Value | Where it lives |
|---|---|---|
| Minimum area | `10 m²` | Constant in mobile validation module |
| Area maths | — | `polygonArea()` in `app/src/form/lib/geometry.js` (already merged, GEO-001) |
| Severity | `block` | `extra.geoConfig.validateArea` › `validatePolygonArea` device setting › `block` |
| Maximum area | *(absent)* | `extra.geoConfig.maxAreaHa` — opt-in, no ceiling unless authored (D-5) |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing datapoints unaffected — validation runs at capture

> **Checked against GEO-014, 2026-09-18: nothing here changes.** From phase 2 a vertex may carry
> an optional third element (`[lat, lng, accuracy]`). `polygonArea` destructures `([lat, lng])`
> and `reduce((sum, [lat]) => …)`, so the extra element is dropped before any arithmetic and both
> the area figure and `maxAreaHa` behave identically. Recorded so that this does not get
> re-audited.

### Mobile App Impact
- [x] Sync endpoints affected: **none**
- [x] SQLite schema changes: the switch column shared with GEO-002, migration 11

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
| Threshold check on the merged `polygonArea()` (D-3) | 0.25 |
| ~~Live enclosed-area display during capture~~ — **already shipped by GEO-001**, see below | 0 |
| Inline area verdict on the two capture surfaces (GEO-013 D-7) | 0.25 |
| i18n message | 0.25 |
| Tests — known square at several latitudes | 1 |
| **Subtotal** | **1.75** |
| **Added by D-4** — second Settings switch + its i18n (resolver and migration already costed in GEO-002) | 0.25 |
| **Added by D-5** — `maxAreaHa` rule, hectare message, tests, web threshold plumbing | 0.5 |
| **Total** | **2.5** |

> Scheduled with GEO-002 the combined cost is about **6.5h** — up from the 4h noted before,
> because D-4 adds the shared severity resolver, the Settings section and one DB migration.
> Splitting them across sprints costs roughly 1.5h more, since both would pay for the resolver.
>
> **The live-area display is done, not partly done.** Both capture surfaces already render it:
> `TypeGeoDrawing` on the form, and `MapDrawView`'s status bar during drawing
> (`app/src/pages/MapDrawView.js:238-245`). What remains is the m² framing the error message
> uses, plus the inline failure verdict beside those existing lines (GEO-013 D-7) — no Validate
> button in phase 1.

---

## 10. Open Questions

- [ ] Is 10 m² right for the first real programme using this? It is inherited from a
      farm-plot context and has not been checked against our use case. **D-4 does not answer
      this** — it makes the check warn-able, not re-thresholdable.
- [x] Should the check be switchable, as originally requested? **Answered 2026-09-17: yes, as a
      severity switch (D-4), defaulting to ON.**
- [ ] A *stricter* per-programme floor (D-2's "reject anything under 100 m²") is still unbuilt.
      It needs a `geoConfig` key with a minimum of its own, and an authoring UI — which means an
      upstream `akvo-react-form-editor` release (GEO-002 D-5). Not phase 1. **Tracked as a
      catalogue row in GEO-012 D-2**, alongside a *maximum* area rule, for which research found
      live demand (Survey123: an area of interest constrained "between 0 and 10 acres"). GEO-012
      D-3 notes both should ship in one editor release if they ship at all.

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
