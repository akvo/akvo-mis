# Feature Design Document

## Feature: Polygon Overlap Detection

**Task ID**: GEO-007 (breakdown ref: T4)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 3 — Overlap detection *(moved down on reviewer feedback)*
**Estimate**: 7.5h ≈ 1 day (Mobile)
**Depends on**: GEO-001, GEO-006, GEO-009

---

## 1. Context & Problem Statement

```
Currently:
- Finding an overlap is a DESK JOB. A GIS analyst cleans polygons and removes overlaps AFTER
  upload — by which time the mapping team has left the area.
- Field assessment of a carbon-forestry programme reported TWO-THIRDS of plots with issues
  (overlaps, boundary mismatches), 3-4 re-walks per plot, and a 24-48h delay between upload
  and verification.

Goal:
- Move the overlap check onto the enumerator's phone, while they are still standing on the plot.
- An overlap caught in the field costs two minutes: redraw and re-validate.
  The same overlap caught at a desk costs a return visit.
```

**Why overlapping boundaries matter**: if two boundaries overlap, the same ground is counted
twice — a benefit issued twice. In carbon programmes that is a credit sold for carbon that does
not exist; in land registration, two people holding title to one plot. These programmes are
audited by an accredited third party, and duplicate geometry is exactly what such an audit
exists to catch.

**Prioritisation note**: this was moved from phase 1 to phase 3 on reviewer feedback
(*"the polygon overlap is one of the major things … I would put it much lower on the list"*).
GEO-005, GEO-006, GEO-008 and GEO-009 moved with it — they exist only to serve this capability.

---

## 2. Requirements

### User Acceptance Criteria — detection

- [ ] A new polygon overlapping an existing one by ≥ threshold → validation fails
- [ ] The error names both datapoints:
      `New plot for <current> overlaps with plot for <existing>`
- [ ] **All** simultaneous overlaps are reported, not just the first
- [ ] Below threshold → passes
- [ ] Works with the radio off
- [ ] Resolving the overlap clears the error and allows submission

### User Acceptance Criteria — the Validate button *(added from design review)*

- [ ] **The Validate button is not shown at all when the question has no validation rules
      configured.** A plain geoshape question with no `geoConfig` looks exactly as it does in
      phase 1
- [ ] When rules are configured, pressing Validate produces a **validation report**, not a
      single message:
  - Pass → a **green tick** and nothing else
  - Fail → an error state listing **every** rule that failed, each with its own message
- [ ] **If the question is marked required, the enumerator must validate before submitting.**
      An unvalidated required polygon blocks submission exactly as a failed one does
- [ ] **Warn vs block depends on `required`**:

| Question | Validation state | Behaviour |
|---|---|---|
| Required | Not validated | 🚫 **Block** submit |
| Required | Failed | 🚫 **Block** submit |
| Required | Passed | ✅ Allow |
| Not required | Failed | ⚠️ **Warn**, allow the enumerator to proceed |
| Not required | Not validated | ⚠️ Warn only |

- [ ] Re-validating after a fix replaces the previous report rather than appending to it

### Technical Acceptance Criteria

- [ ] Overlap ratio = `intersection_area / min(new_area, existing_area)`
- [ ] Threshold from `extra.geoConfig.overlapThreshold`, default **20 %**
- [ ] ≤ 500 ms against 10,000 stored plots
- [ ] `geoshape` only
- [ ] The datapoint being edited is excluded from its own check
- [ ] Candidates are **registration** datapoints (see D-6)
- [ ] The report structure supports **N rules**, not a fixed set of four (see D-8)

---

## 3. Data Model Changes

**None.** Reads GEO-006's index; stores the validation result in form state, not the database.

---

## 4. API Contract

**No API change.** Fully offline.

---

## 5. Decision Log

### D-1: Explicit "Validate now" button, not automatic validation

**Options Considered**:
1. Validate on blur / on Next / on every submit pass
2. Explicit button

**Decision**: Option 2.

**Rationale**: `validateAllGroups()` re-validates every question of every group on submit.
Automatic validation would run the geometry work repeatedly, on the JS thread, for every
polygon. A button makes the expensive path user-initiated and bounded.

**Impact**: This creates a reachable **"never validated"** state, which must be closed:
- Editing the polygon after a pass returns the field to *not yet validated*
- **Submission requires a current, passing validation** — a never-validated polygon blocks
  submit exactly as a failed one does. Without this, the button becomes an opt-out from the
  whole feature
- The submit gate reuses the **stored** result; it does not re-run the geometry

### D-2: Region/administration is NEVER a filter

**Decision**: Candidates are filtered by form and bounding box only.

**Rationale**: Ported verbatim from the reference implementation's rationale — filtering by
region produces false negatives on boundary plots and on mis-selected regions, and defeats fraud
detection. A plot re-registered under a different region label must still be caught.

### D-3: Threshold is a percentage of the *smaller* polygon, default 20 %

**Decision**: `intersection / min(areaA, areaB)`, default 20 %.

**Rationale**: The source documents conflict — 20 % in one, 5 % in two others. 20 % carries the
documented reasoning: it allows minor boundary touching from GPS drift while blocking
significant overlap. Two genuinely adjacent plots will always show a sliver of intersection.

**Impact**: 20 % is inherited from a farm-plot context and has **not** been measured against our
terrain. It is configurable per question for exactly this reason.

### D-4: `@turf` scoped submodules, not the full bundle

**Decision**: Import `@turf/area`, `@turf/intersect`, `@turf/bbox`, `@turf/kinks` individually.

**Rationale**: `@turf/turf` is already a declared dependency in `frontend/package.json` and is
pure JS, so it runs in React Native. The full bundle would bloat the mobile bundle for four
functions.

### D-5: Polygons in a repeatable group are not checked against each other

**Decision**: Checked against other datapoints; **never** against each other within the same
submission.

**Rationale**: Two repeat instances of one submission legitimately describe different parts of
one site. An overlap error in a repeatable group must identify **which repeat instance** failed.

### D-6: Candidates are already-registered plots

**Decision**: The overlap check runs against **registration** datapoints already on the device,
not against arbitrary submissions.

**Rationale**: Raised in design review — *"in general the [parent] itself is the registration, so
we only validate the data from the plot that already registered."* The registration form is what
establishes a plot's identity; monitoring submissions describe an existing plot rather than
claiming new ground.

**Impact**: Narrows the candidate set and is consistent with monitoring forms not prefilling a
polygon. Needs confirming against how the first real programme structures its forms.

### D-7: Warn vs block is driven by the question's `required` flag

**Options Considered**:
1. Always block on a failed validation
2. Block only when the question is required; otherwise warn

**Decision**: Option 2.

**Rationale**: Raised in design review — *"sometimes warn and sometimes blocked."* A required
polygon is load-bearing for the record, so a bad one must not be submitted. An optional polygon
that fails a rule is worth flagging but should not trap the enumerator in a form they are
otherwise entitled to submit.

**Impact**: The submit gate reads **two** things, not one: the stored validation result **and**
the question's `required` flag. This also closes the "never validated" hole from D-1 for the
case that matters — required questions.

### D-8: Validation rules must be extensible beyond the initial four

**Decision**: Model validation as a **list of rules**, each producing a pass/fail with its own
message, rather than four hardcoded branches.

**Rationale**: Raised in design review — different programmes will want their own checks
(*"some client will say I need a very particular validation"*), and one approach discussed was
mapping each validation to a named function so a tenant-specific rule can be added without
touching the core. The report UX already assumes a list of failures.

**Impact on this task**: Do **not** hardcode four checks in a fixed sequence. The immediate cost
is near zero — an array of rule functions instead of four `if` blocks — but retrofitting it later
means rewriting the report UI and the submit gate as well.

**Out of scope here**: per-tenant rule registration, user-authored rules, and how a rule would be
distributed to devices. Those need their own design.

---

## 6. Type/Constant Mappings

| Setting | Key | Default |
|---|---|---|
| Overlap threshold | `extra.geoConfig.overlapThreshold` | `20` (%) |
| Enable | `extra.geoConfig.detectOverlaps` | `false` |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Forms without `detectOverlaps` behave exactly as phase 1
- [x] No stored data changes

### Mobile App Impact
- [ ] SQLite schema changes: none here (GEO-006 owns the index)
- [x] Depends on GEO-005's completeness signal — **must not validate against a partial set**

---

## 8. Security Considerations

- [x] No data leaves the device
- [x] The error message exposes another datapoint's name to the enumerator — acceptable, since
      they can already see those datapoints in their assignment. **Verify this holds** if
      candidate scope ever widens

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Ratio maths at threshold boundary: 19.9 % passes, 20.1 % fails |
| Unit | Identical polygons → 100 %; disjoint → no candidates |
| Unit | Self-exclusion when editing an existing datapoint |
| Integration | Multiple simultaneous overlaps all reported |
| Integration | State machine: edit after pass → *not validated* → submit blocked |
| **Performance** | See below |

### What the performance test is

1. Seed the geometry index with ~10,000 synthetic polygons in a plausible geographic spread
2. Press "Validate now" and measure wall-clock time end to end
3. Target **< 500 ms**, on a **real low-end Android device** — an emulator will lie

It exists because the whole design rests on one assumption: the bbox pre-filter cuts 10,000
candidates to roughly 5–50 before any polygon maths runs. Three failures it catches, all
invisible to unit tests:

| Failure | Symptom |
|---|---|
| SQLite ignores the bbox indexes | Full table scan on every validate |
| Dense areas return hundreds of candidates | The pre-filter works on average but not in the worst case — **which is exactly where plots overlap** |
| `@turf/intersect` slow on ~180-vertex polygons | Fine with test triangles, slow with real captures |

**Hours breakdown**

| Unit | h |
|---|---|
| **Spike: verify `@turf` submodules work in React Native** | 1 |
| bbox range query + candidate fetch | 0.5 |
| Intersection ratio vs threshold | 0.5 |
| "Validate now" button, 3 states, progress | 1 |
| State reset on edit; submit gate reads stored result | 1 |
| Error assembly — multiple conflicts, repeat instance | 0.5 |
| Unit tests with known fixtures | 1.5 |
| **Perf test at 10,000 plots** | 1.5 |
| **Total** | **7.5** |

---

## 10. Open Questions

- [ ] Is 20 % right for the first real programme? Inherited, not measured
- [ ] What does the UI do when the candidate set is **incomplete** (GEO-005)? Refuse to
      validate, or validate with a visible caveat? Silently passing is not an option
- [ ] Does `@turf` behave on a real device? **Spike this before committing the estimate**

### Raised in design review, needing follow-up

- [ ] 🔴 **Is the stored value GeoJSON, or ARF's `[[lat, lng], …]`?** Design review answered
      "GeoJSON standard", but these are **not the same thing** — see the note below. This must be
      settled before GEO-001 is built, not after
- [ ] **Bounding overlap detection to an assigned collection area.** Review raised that a form
      assignment should carry a region — *"you draw a polygon … it would download tiles to that
      area and any records already collected in that area, so overlap detection is bounded"*.
      This is a scoping mechanism this design does not yet have. It also interacts with D-2
      (region is never a *filter*): a **collection-area boundary for sync scope** is not the same
      as **filtering candidates by administrative label**, and the distinction must stay explicit
- [ ] **Per-tenant custom rules** (D-8) — needs its own design: registration, distribution to
      devices, and safe execution
- [ ] **Lines / multi-geometry.** Review settled on *polygons only for now*, with lines
      (fences, boundaries) likely later. D-8's rule list should not assume a polygon-only shape

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T4)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-3, FR-4, D2, D3, D6, D7, D9)
- Reference: `akvo/african-bamboo-odk-external-validations` → `validation/OverlapChecker.kt`, `data/dao/PlotDao.kt`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
