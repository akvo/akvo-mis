# Feature Design Document

## Feature: Configurable Polygon Validation Rules

**Task ID**: GEO-012
**Author**: Iwan Firmawan
**Date**: 2026-09-17
**Status**: Deferred — **evidence gathered 2026-09-17**, direction decided, not scheduled
**Phase**: post-phase-3
**Depends on**: GEO-013 (the rule registry), GEO-002, GEO-003, GEO-007

---

## 1. Context & Problem Statement

```
Currently:
- Polygon validation is a fixed set of rules compiled into the app.
- A programme wanting its own rule has no route but a code change and an app release.

Goal (as originally framed):
- An expression a programme can author, distribute to devices, and change without shipping
  an APK — modelled on how autofield already evaluates `extra.fn.fnString`.
```

The original question was *"should we build this?"*, with a follow-up: *"or is there research
showing real use cases?"* §2 is that research. It changes the answer from "maybe later" to
**"yes, there is demand — and it is not demand for an expression language."**

---

## 2. Research: is there real demand?

### 2.1 The demand is real, documented, and currently unmet

| Evidence | What it shows |
|---|---|
| **Our own client.** `akvo/african-bamboo-odk-external-validations` — a **separate Kotlin/Room/Compose application** built solely to run polygon validations that ODK could not | Someone paid for a whole app rather than go without these checks. This is the strongest datapoint available and it is in-house |
| **ODK forum — self-intersecting geoshapes.** A user asks how to reject self-intersecting polygons at capture. The expert answer: *"I don't think there is a ready way to do this on the fly whilst acquiring the geoshape."* The asker concludes they will *"make the check at the backend itself"* | The single most-wanted geometry check is **impossible** in the dominant XLSForm ecosystem |
| **Esri Survey123 — overlap detection.** Community answer: no built-in function for polygon overlap; users are pointed at custom JavaScript | Same gap at a vendor with far more resources |
| **Esri Survey123 — polygon size.** A user needs an area-of-interest polygon constrained *"between 0 and 10 acres"* | Min **and max** area is a live ask, not a hypothetical |
| **`chrissyhroberts/ODK_Geofencing`.** A cross-platform project — ODK, KoBoToolbox, Ona, SurveyCTO, CommCare — that decomposes polygons into a grid and ships a lookup CSV, *~26 MB at 10 m resolution*, because none of those platforms can test point-in-polygon | People build 26 MB CSVs to route around this. Demand is not speculative |

**Conclusion**: the need is well attested across every comparable platform. Our phase-1 fixed
rules already deliver the two things that are hardest and least available anywhere —
self-intersection and overlap-between-submissions.

### 2.2 The demand is for named predicates, not for an expression language

This is the finding that decides the design.

- **ODK has `area()`.** A minimum-area rule is already expressible as an ordinary XLSForm
  `constraint`. The checks people *cannot* express are the geometric predicates:
  self-intersection, overlap with other submissions, containment in a boundary
- Every request found is one of a **small enumerable set**: min area, max area, inside a
  boundary, no overlap, no self-intersection, accuracy threshold. Nobody in the material
  reviewed asked for arbitrary logic — they asked for a predicate the platform lacked
- An expression language would therefore ship maximum machinery to serve the *easy* half of the
  demand, while the hard half needs purpose-built geometry code no DSL removes the need for

### 2.3 What the one vendor that built a DSL had to do

Esri **did** ship custom JavaScript in Survey123, and the restrictions are instructive:

- ES6 only; **no DOM, no frameworks, no async, no file access**
- **Available only to users inside the survey author's ArcGIS organization — not usable on
  public surveys**
- Esri's own security team *"raised concerns with implementing this feature as it can
  potentially lead to untrusted JavaScript running on a user's device or browser"*

A multi-tenant SaaS shipping author-supplied JS to enumerator devices is exactly the shape Esri
locked down hardest. We would inherit that problem with none of their platform controls.

### 2.4 Evidence that the rule should flag, not block

USAID's **MAST** programme (Mobile Applications to Secure Tenure — Tanzania, Burkina Faso,
Zambia) is the closest real-world analogue to this epic's domain. Boundary overlaps there are
*"reviewed by local committees before being validated by government land officials."*

In the flagship land-tenure deployment, an overlap is **the start of an adjudication, not a
validation error**. That is independent confirmation of GEO-002 D-4's severity model and D-7's
warn-and-surface posture: the software's job is to make the conflict visible to the humans who
resolve it, not to refuse the record.

---

## 3. Data Model Changes

**None proposed.** A catalogue rule is `extra.geoConfig` keys on the question — the channel that
already round-trips (GEO-009).

---

## 4. API Contract

**No API change** for the catalogue approach. This is one of its main advantages over a DSL,
which would need a distribution and versioning story for rule source.

---

## 5. Decision Log

### D-1: A **parameterised rule catalogue**, not an expression DSL

**Options Considered**:
1. `fnString` expression DSL, autofield-style
2. A catalogue of named, parameterised rules we implement and a form author configures
3. Nothing — fixed rules forever

**Decision**: Option 2, when scheduled.

**Rationale**: §2.2 — the evidenced demand is a short list of predicates, and §2.3 shows what the
DSL route costs. Option 2 also keeps every rule a **pure compiled function** (GEO-013 §8), so no
author-supplied code ever executes on an enumerator's device, and each rule's geometry is
unit-testable with fixtures rather than only observable at runtime.

**Impact**: a programme wanting something genuinely outside the catalogue still needs us. That is
an accepted limit. The catalogue can grow by one entry — one array element and one i18n key
(GEO-013 D-2) — which is a far smaller ask than a code change today.

> **Note, 2026-09-21.** The catalogue is now *visible*, not just configurable: editor 2.0.6
> renders the app's rule list in the form builder, so an author can see which rules run on a
> geoshape question instead of inferring it. The editor carries its own mirror of the registry
> (`src/lib/geo-rules.js`) with rule keys matching `app/src/form/lib/polygon-rules.js` by name,
> so a rule traces across both repositories.
>
> **The mirror is a copy, and copies drift.** Adding a rule to the app does not make it appear in
> the builder; that is a second edit in a second repository and a release. The cost is one array
> element in each, but it is two. This is the same duplication GEO-002 D-7 records for polygon
> maths across `app/` and `frontend/` — noted, not solved, and for the same reason: there is no
> shared package.

**What would reopen Option 1**: a *specific* rule request that cannot be expressed as a
parameterised predicate. Not a general wish for flexibility — a named rule with a named requester.

### D-2: The evidenced catalogue

Ordered by strength of evidence, not by build order. **None of this is scheduled.**

| Rule | Proposed keys | Evidence | Status |
|---|---|---|---|
| No self-intersection | `validateShape` | ODK forum; reference validator | ✅ built, GEO-002 |
| Minimum area | `validateArea` | Survey123 acreage thread; reference validator | ✅ built, GEO-003 |
| No overlap with other answers | `detectOverlaps`, `overlapThreshold` | Survey123; MAST | 🔜 GEO-007 — `overlapThreshold` is now a **ceiling** on an accuracy-derived threshold (GEO-014 D-5) |
| GPS accuracy threshold | `accuracyThreshold` | ARF #192 | ✅ exists — becomes a **submit gate** in phase 3 (GEO-014 D-6) |
| **Maximum** area | `maxAreaHa` | Survey123 *"between 0 and 10 acres"*; tap-at-low-zoom | ✅ **built 2026-09-17**, GEO-003 D-5 — **authorable since editor 2.0.6** |
| **Stricter** minimum area | `minAreaSqm` (with a floor of its own) | GEO-003 D-2, GEO-003 §10 | ❌ unbuilt |
| Inside a boundary / geofence | boundary reference + predicate | `ODK_Geofencing` across 5 platforms; GEO-007's "bounded collection area" question | ❌ unbuilt, **largest** — needs a boundary source, sync and storage |

The first four are phase 1–3, and maximum area joined them on 2026-09-17 — it was pulled forward
not by the Survey123 evidence but by a systems argument the research had not surfaced: an
oversized polygon poisons GEO-007's bbox pre-filter (GEO-003 D-5). That is worth noting as a
limit of §2's method — demand research finds what *users* ask for, not what the architecture
needs.

The two remaining rows are what this document would still deliver. The stricter minimum floor is
small; geofencing is not, and needs a boundary source before it needs a rule.

### D-3: The real cost is authoring, not evaluation

**Decision**: any catalogue expansion is costed as *upstream editor release + app support*, never
as app support alone.

**Rationale**: GEO-002 D-5 established that reading a `geoConfig` key is free while authoring one
costs an `akvo-react-form-editor` PR plus an npm release — measured at 2h in GEO-009, more than
the rule code. A three-rule expansion is one release, not three, so **batching matters more than
the rules' individual sizes**.

**Impact**: if `maxAreaSqm` and a stricter `minAreaSqm` are ever wanted, ship them in one editor
release with whatever else is pending.

> **This happened, 2026-09-21 — editor 2.0.6.** Five keys had accumulated on the "read but not
> authored" list (`validateShape`, `validateArea`, `maxAreaHa`, `overlapThresholdFloor`,
> `allowTapping`), each deferred on its own with the same sentence. This decision is what
> resolved the standoff: none of them justified a release alone, all of them together did.
>
> The release also carried a sixth key in the opposite direction — `validateOverlap` (GEO-007
> D-9) is **authorable before it is readable**, reversing the "reading is free, authoring is
> expensive" asymmetry this decision is built on. That is not a counter-example to the rule; it
> is what the rule looks like when the cheap half has not been scheduled yet. The cost still
> landed on the release, which is why it rode along with five others rather than waiting.
>
> **The lesson for the next expansion** is narrower than "batch things". It is that the list of
> deferred keys is itself the trigger: each deferral was individually correct and collectively
> produced a panel that could not author most of what the app read. Worth checking the list, not
> just the next rule's size.
>
> **A second list behaves the same way, and it was found the same day.** Making five keys
> authorable made five *unvalidated* keys reachable: `_geo_config_issues()` checked four of nine,
> because a key that only import could write had never justified a range check on its own. The
> deferrals there were individually correct too, for the same reason and with the same collective
> result. Closed on 2026-09-21 (GEO-010 §6).
>
> So the trigger generalises: **authoring a key and validating it are two lists that must be
> closed together.** A rule added to this catalogue now costs one registry entry, one editor
> mirror entry, and one validator entry — and the third is the one with no UI to make its absence
> visible.

---

## 6. Type/Constant Mappings

Existing keys are in GEO-009 §2. Proposed keys are D-2 above, **none implemented**.

---

## 7. Compatibility & Migration

- [x] Additive by construction — a device that does not understand a new key ignores it and
      falls through to its built-in default (GEO-013 §6.3)
- [ ] A rule that ships *after* data is collected does not retroactively invalidate it. The web
      badge (GEO-002 D-7) **does** apply current rules to old geometry, so a new rule makes old
      records display a warning they were never shown at capture. Acceptable for a badge;
      **not** acceptable if it ever gates anything

---

## 8. Security Considerations

- [x] The catalogue route executes **no author-supplied code** — the property §2.3 shows Esri
      had to defend with organizational restrictions
- [ ] Parameters remain untrusted input and need range validation at the write boundary, the gap
      GEO-010 already tracks for the existing keys

---

## 9. Testing Strategy

Not specified — no scope. Any rule added inherits GEO-013 §9 unchanged, which is the point of
having settled the registry first.

---

## 10. Open Questions

- [x] **Is there a named requester for any unbuilt row in D-2?** **Answered 2026-09-17: the
      requester is Akvo itself.** This epic is not client-driven work; it is deliberate
      productisation — replicating in Akvo MIS a capability proven in the African Bamboo
      deployment, so that MIS stands as a generic remote data-collection platform rather than
      trailing ODK and Survey123 on geometry. That reframes §2: the research is not hunting for
      permission to build, it is evidence that the category is worth productising and that the
      *shape* should be a catalogue rather than a DSL.
- [ ] Which catalogue rows make the product cut, and in what order. Productisation answers
      *whether*, not *which*. D-2's evidence column is the ranking input
- [ ] The geofence rule needs a boundary source. GEO-007 raised *"a form assignment should carry
      a region"* and warned it must not be conflated with filtering by administrative label.
      That is a sync-and-storage design, much larger than a rule
- [ ] Max area and stricter min area are small enough that they may be cheaper to fold into a
      future GEO-003 revision than to track as a separate task

---

## 11. References

- GEO-013 — the registry this would extend
- GEO-007 D-8 — "validation rules must be extensible beyond the initial four"
- GEO-002 D-5 — why authoring, not reading, is the cost
- `akvo/african-bamboo-odk-external-validations` — the in-house precedent
- [ODK forum — validating intersecting geoshapes](https://forum.getodk.org/t/how-to-validate-intersecting-geoshape-in-odk-xlsform-definition/40945)
- [chrissyhroberts/ODK_Geofencing](https://github.com/chrissyhroberts/ODK_Geofencing)
- [Survey123 — overlapping polygons](https://community.esri.com/t5/arcgis-survey123-questions/survey123-spatial-analysis-overlapping-polygons/td-p/839216)
- [Survey123 — polygon size constraint](https://community.esri.com/t5/arcgis-survey123-questions/polygon-size-constraint-survey123/td-p/1011534)
- [Survey123 — custom JavaScript functions](https://doc.arcgis.com/en/survey123/desktop/create-surveys/pulldatajavascript.htm)
- [Cadasta / New America — MAST](https://www.newamerica.org/insights/mobile-application-secure-land-tenure/)

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
