# GEO-011 — Overall QA: Manual Test Script

**Task ID**: GEO-011
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Covers**: GEO-001 … GEO-010

---

## How to use this document

Each phase can be run **independently, as it lands** — you do not need the whole epic finished
to start testing. Run the suites in order within a phase; later tests assume earlier ones passed.

Every test has an **ID**, numbered **steps**, and an **expected result**. Record PASS / FAIL /
BLOCKED with a note. A test that cannot be run because a dependency is missing is BLOCKED,
not FAIL.

> **Why this document exists.** The individual tasks each carry unit tests. What unit tests
> cannot catch here are *integration* failures — a field that renders correctly and validates
> wrongly, coordinates silently swapped, or a validation that passes because the data it should
> have compared against never arrived. §9 lists those traps explicitly. **If you only have time
> for part of this script, run §9.**

---

## 1. Preconditions

### Devices

| What | Why |
|---|---|
| A **real Android device** — mid or low range, not a flagship | Emulators misreport GPS and hide WebView performance problems |
| A **development build** (not Expo Go) — required from phase 2 onward | Expo Go cannot run background location |
| Ability to **turn the radio fully off** (aeroplane mode) | Offline behaviour is the core promise of this feature |
| Somewhere outdoors you can **walk 50–100 m** | Phase 2 cannot be tested indoors or at a desk |

### Accounts and data

- A workspace with a **published registration form** that contains a `geoshape` question
- A mobile user assigned to that form
- A form-builder account with rights to edit questions (phase 3)
- For phase 3: **at least 3 existing datapoints** with known, deliberately overlapping polygons

### Test forms to prepare

| Form | Contains | Used by |
|---|---|---|
| **F1 — Basic** | One `geoshape`, **not** required, no `geoConfig` | Phase 1 |
| **F2 — Required** | One `geoshape`, **required**, no `geoConfig` | Phase 1, §5 |
| **F3 — Configured** | One `geoshape`, required, `detectOverlaps: true`, `overlapThreshold: 20` | Phase 3 |
| **F4 — Repeat group** | A repeatable group containing a `geoshape` | Phase 3, §7 |
| **F5 — Control** | No geo questions at all | §8 regression |

---

## 2. Phase 1 · Capture (GEO-001)

### QA-101 — A geoshape question renders a map, not a text box

> This is the current broken behaviour. If it still shows a text input, GEO-001 is not wired in.

1. Open **F1** on the device
2. Navigate to the geoshape question

**Expected**: a map with drawing controls. **NOT** a plain text input.

### QA-102 — Tap to place vertices

1. Tap the map three times in a triangle
2. Observe the point count and the drawn shape

**Expected**: three vertices appear, joined as a closed shape. Count reads 3.

### QA-103 — Drag to correct a vertex

1. Long-press or drag one vertex to a new position

**Expected**: that vertex moves; the shape redraws; the count stays 3.

### QA-104 — Undo, remove, clear

1. Add two more points (count = 5)
2. Undo the last point → count = 4
3. Remove a single middle vertex → count = 3
4. Press Clear

**Expected**: clearing more than 3 points asks for confirmation before wiping.

### QA-105 — Enclosed area is shown

1. With ≥3 vertices placed, look for the area display

**Expected**: an area in m² (or ha), updating as vertices move.

### QA-106 — 🔴 Axis order — coordinates land in the right place

> **The highest-value test in phase 1.** A latitude/longitude swap does not crash; it produces
> plausible coordinates on the wrong continent, and every area and overlap result downstream is
> quietly wrong.

1. Choose a location with **clearly asymmetric** coordinates — latitude and longitude must not be
   similar numbers. Example: somewhere near latitude 9, longitude 38
2. Capture a small polygon there
3. Save and submit the datapoint
4. Open the same datapoint **on the web dashboard**

**Expected**: the polygon appears in the **same real-world place** on web as on mobile.
**FAIL if** it appears in a different country, in the ocean, or mirrored across the equator.

### QA-107 — Persistence across navigation

1. Capture 4 vertices
2. Navigate to the next question group, then back

**Expected**: all 4 vertices still there, in the same order.

### QA-108 — Save, close, resume

1. Capture a polygon, save the form as a draft
2. **Fully close the app**, reopen, resume the draft

**Expected**: the polygon is intact with no loss of precision.

### QA-109 — Empty polygon does not corrupt the draft

> Guards touchpoint 6 — an empty polygon must be `[]`, not `''`.

1. Open the geoshape question but place **no** points
2. Save as draft, close, reopen

**Expected**: the question is empty and still usable. No crash, no stray value.

### QA-110 — Datapoint name is clean

> Guards touchpoint 5.

1. Submit a datapoint from **F1**
2. Look at the datapoint's name in the submission list

**Expected**: the name contains the normal meta answers only. **FAIL if** raw coordinate arrays
appear in it.

---

## 3. Phase 1 · Shape validation (GEO-002)

> If GEO-009 has not landed, these run at their fixed floors with no configuration.

### QA-201 — Too few vertices

1. Place **2** points only
2. Attempt to submit (or press Validate if the button is present)

**Expected**: "Polygon has too few vertices. A valid shape requires at least 3 points."

### QA-202 — A valid triangle passes

> Guards the `MIN_VERTICES = 4` trap — the reference implementation counts a duplicated closing
> point, ours does not. If a 3-vertex triangle fails, the wrong constant was copied.

1. Place exactly **3** points forming a clear triangle
2. Validate

**Expected**: **passes**. No vertex-count error.

### QA-203 — Self-intersecting shape

1. Place 4 points in a **bowtie** (cross the edges)
2. Validate

**Expected**: "Polygon lines intersect or cross each other. Please redraw the shape."

### QA-204 — Messages are translated

1. Switch the app language
2. Trigger any validation error

**Expected**: the message appears in the selected language, not English.

---

## 4. Phase 1 · Area validation (GEO-003)

### QA-301 — Tiny polygon rejected

1. Zoom the map in as far as it goes
2. Place 3 points within a few metres of each other (under ~10 m²)
3. Validate

**Expected**: "Polygon area is too small. Minimum required: 10 square meters."

### QA-302 — Normal polygon accepted

1. Capture a polygon roughly the size of a small building

**Expected**: passes the area check.

### QA-303 — Area figure is credible

1. Capture a polygon over a feature whose real size you know — a football pitch, a car park,
   a building footprint
2. Compare the displayed area against the real one

**Expected**: within a sensible margin. **FAIL if** it is out by orders of magnitude — that
indicates planar rather than geodesic maths.

---

## 5. Phase 1 · Validate button and submit gating

> These behaviours are specified in GEO-007 D-7 / D-8 but are visible as soon as any validation
> exists. Re-run them in phase 3 once overlap is added.

### QA-401 — No rules configured → no Validate button

1. Open **F1** (no `geoConfig`)

**Expected**: **no Validate button** is shown. The question behaves like a plain capture field.

### QA-402 — Required question must be validated

1. Open **F2** (required, rules configured)
2. Capture a valid polygon but **do not press Validate**
3. Attempt to submit

**Expected**: submission is **blocked**. A never-validated required polygon blocks exactly as a
failed one does.

### QA-403 — Pass shows a green tick

1. Capture a valid polygon, press Validate

**Expected**: a green tick / success state. No error list.

### QA-404 — Fail shows every failed rule

1. Capture a polygon that breaks **two** rules at once — e.g. a self-intersecting *and* tiny shape
2. Press Validate

**Expected**: an error state listing **both** failures, not just the first.

### QA-405 — 🔴 Editing after a pass invalidates it

> The single most important state test. Without it, an enumerator can validate, then redraw into
> a conflict, and still submit.

1. Capture a valid polygon on **F2**, press Validate → green tick
2. **Move one vertex**
3. Attempt to submit **without** pressing Validate again

**Expected**: the field returns to *not yet validated* and submission is **blocked**.
**FAIL if** the stale green tick persists and submit is allowed.

### QA-406 — Warn vs block follows `required`

1. On **F2** (required): fail a validation → attempt submit
2. On **F1** (not required, with rules): fail a validation → attempt submit

**Expected**: required → **blocked**. Not required → **warned**, but able to proceed.

### QA-407 — Re-validating replaces the report

1. Fail validation, note the errors
2. Fix one problem, press Validate again

**Expected**: the report shows only the remaining error. Errors do **not** accumulate.

---

## 6. Phase 2 · GPS boundary walking (GEO-004)

> **Must be done outdoors.** Requires a development build.

### QA-501 — Satellite lock before recording

1. Start the app indoors or with a poor sky view
2. Attempt to start auto-record

**Expected**: recording does not start silently. The enumerator is told a fix is being waited
for. **FAIL if** the button appears dead with no explanation.

### QA-502 — Walking records points

1. Go outdoors with a clear sky view
2. Start auto-record and walk a perimeter of ~50 m

**Expected**: points appear on an interval; the shape follows your path.

### QA-503 — Live position is distinguishable

1. While recording, observe the map

**Expected**: the live GPS position is visually distinct from recorded vertices, and the current
accuracy is shown.

### QA-504 — Poor accuracy is skipped, visibly

1. While recording, walk somewhere with obstructed sky — beside a building, under trees
2. Watch the point count and the accuracy reading

**Expected**: the count **stops advancing** while accuracy is poor, and the accuracy display
makes it obvious why. **FAIL if** it silently appears frozen with no explanation — the enumerator
will assume the app has crashed.

### QA-505 — Record on demand

1. While walking, press "record this point" at a corner

**Expected**: a vertex is appended immediately, independent of the interval.

### QA-506 — Mixed capture

1. Record several points by walking
2. Stop, then **tap** the map to add one more
3. Save

**Expected**: both kinds of point sit in one ordered list, in the order created.

### QA-507 — 🔴 Teardown — no orphaned GPS watch

> The most likely field complaint if missed.

Test each path separately. After each, check the device's location indicator:

1. Press **Stop**
2. Navigate to a **different question group**
3. **Submit** the form
4. **Force-close** the app

**Expected**: after every one of these, the GPS watch stops. The location indicator clears.
**FAIL if** any path leaves it running.

### QA-508 — Background recording *(if in scope)*

1. Start auto-record
2. Lock the screen and walk for 2 minutes
3. Unlock and return to the form

**Expected**: a persistent notification was shown while locked; points recorded during that time
are present, in the right order, with no duplicates at the resume boundary.

### QA-509 — Background permission refused

1. Fresh install; start auto-record; **deny** the background location permission

**Expected**: foreground recording still works. The enumerator is told recording will pause when
the screen locks. **FAIL if** the feature breaks entirely.

---

## 7. Phase 3 · Configuration, sync and overlap

### QA-601 — Authoring `geoConfig` (GEO-009)

1. In the form builder, open a **geoshape** question
2. Locate the geo settings panel

**Expected**: controls for accuracy threshold, a "detect overlaps" checkbox, and — only when
that is ticked — an overlap threshold.

### QA-602 — Panel is geoshape-only

1. Open a **text**, **number** and **date** question in the builder

**Expected**: no geo settings panel on any of them.

### QA-603 — Config survives publish (GEO-010)

1. Set `detectOverlaps` on, threshold 20
2. **Publish** the form
3. Fetch the form on the device (re-sync)

**Expected**: the device receives the configured values. **FAIL if** it silently falls back to
defaults — this is the failure mode that reports nothing.

### QA-604 — Sync brings geometry (GEO-005 / GEO-006)

1. On a clean device, sync **F3**
2. Check that existing datapoints are present

**Expected**: sync completes. Geometry for existing plots is available for comparison.

### QA-605 — 🔴 Partial sync must not silently pass

> The correctness failure this whole design guards against.

1. Start a sync of a form with many datapoints
2. **Interrupt it** — aeroplane mode mid-sync
3. Capture a polygon that you **know** overlaps one of the not-yet-synced datapoints
4. Press Validate

**Expected**: the app either refuses to validate, or validates with a **clear warning** that its
data is incomplete. **FAIL if** it reports a confident "no overlap" — that is a false pass, and
it is worse than an error.

### QA-606 — Overlap detected and named

1. Capture a polygon covering ~50 % of a known existing plot
2. Press Validate

**Expected**: fails, with a message naming **both** datapoints:
`New plot for <yours> overlaps with plot for <theirs>`

### QA-607 — Threshold boundary

1. Capture a polygon overlapping an existing plot by **~10 %** → Validate
2. Capture one overlapping by **~40 %** → Validate

**Expected**: 10 % passes, 40 % fails (with the threshold at 20 %).

### QA-608 — Multiple overlaps all reported

1. Capture a polygon overlapping **two** existing plots

**Expected**: both conflicts are listed, not just the first.

### QA-609 — Editing a record does not conflict with itself

1. Open an existing submitted datapoint for editing
2. Press Validate **without changing** the polygon

**Expected**: passes. **FAIL if** it reports overlapping itself.

### QA-610 — Repeat group polygons do not conflict with each other

1. On **F4**, add two repeat instances with **deliberately overlapping** polygons
2. Validate

**Expected**: no overlap error between the two instances of the same submission. If either
overlaps a *different* datapoint, the error identifies **which repeat instance** failed.

### QA-611 — Map review screen (GEO-008)

1. Trigger an overlap error
2. Open the map review

**Expected**: your polygon in one colour, conflicting ones in another; the view fits all of them;
tapping a polygon shows whose it is; the screen is read-only.

### QA-612 — Resolving the overlap

1. From an overlap error, go back and redraw the boundary clear of the conflict
2. Validate

**Expected**: passes, the error clears, submission proceeds.

---

## 8. Cross-cutting

### QA-701 — 🔴 Everything works offline

Repeat with the radio **fully off** (aeroplane mode):

1. Capture a polygon
2. Validate (shape, area, overlap)
3. Submit

**Expected**: all validation works. No "connect to the internet" prompt, no hang, no crash.
The **only** acceptable degradation is the basemap not loading.

### QA-702 — Missing basemap does not block capture

1. Offline, open the geoshape question

**Expected**: the map area may be blank or show a notice, but drawing controls still work and
capture is possible. **FAIL if** a missing basemap blocks the question entirely.

### QA-703 — Regression: forms without geo questions

1. Open **F5**, complete and submit it

**Expected**: identical behaviour to before this feature. No new errors, no new UI.

### QA-704 — Regression: pre-existing datapoints

1. Open a datapoint created **before** this feature

**Expected**: opens, edits and syncs normally.

### QA-705 — Regression: the plain `geo` point question

1. Complete a form containing an old single-point `geo` question

**Expected**: unchanged behaviour. The new polygon types must not have disturbed it.

### QA-706 — Web and mobile agree

1. Capture the same real-world boundary on **web** and on **mobile**
2. Compare both datapoints on the dashboard

**Expected**: the two polygons sit in the same place, with the same shape. This is the
cross-client contract.

---

## 9. Known traps — run these even if you run nothing else

These are the failures that pass unit tests and reach production. Each is cheap to check and
expensive to miss.

| # | Trap | Test | Why it hides |
|---|---|---|---|
| 1 | **Lat/lng swapped** | QA-106 | Does not crash. Produces plausible coordinates in the wrong place |
| 2 | **Stale validation reused** | QA-405 | The green tick looks correct; the polygon underneath changed |
| 3 | **Partial sync → false pass** | QA-605 | Reports success. Absence of candidates is indistinguishable from absence of overlap |
| 4 | **Valid triangle rejected** | QA-202 | Only appears with exactly 3 points; 4+ point test shapes never hit it |
| 5 | **Required-check wrong on empty polygon** | QA-402, QA-109 | The field renders correctly and validates wrongly |
| 6 | **Coordinates in the datapoint name** | QA-110 | Only visible in the submission list, not in the form |
| 7 | **GPS watch left running** | QA-507 | Invisible until a battery complaint arrives from the field |
| 8 | **Accuracy gating looks like a freeze** | QA-504 | Correct behaviour that reads as a bug to the enumerator |
| 9 | **Config silently defaulted** | QA-603 | Nothing reports an error; the form appears configured and is not |
| 10 | **Planar area maths** | QA-303 | Close enough near the equator to look right in testing |

---

## 10. Performance check

Not a functional test, but it must be run **on a real low-end device** before release.

1. Seed or sync a form with **~10,000 datapoints** carrying polygons
2. Capture a new polygon
3. Press Validate and **time it**

**Expected**: under **500 ms**.

**If it is slow**, the likely causes in order:
1. SQLite is not using the bbox indexes → full table scan
2. A dense area returns hundreds of candidates instead of tens — worth testing *specifically* in
   the densest part of the dataset, since that is exactly where overlaps occur
3. Intersection maths is slow on high-vertex polygons — GPS capture at 10 s intervals makes
   ~180-vertex shapes routine, so test with a *walked* polygon, not a hand-drawn triangle

---

## 11. Sign-off

| Phase | Suites | Tester | Date | Result |
|---|---|---|---|---|
| 1 — Capture & validity | §2, §3, §4, §5 | | | |
| 2 — GPS walking | §6 | | | |
| 3 — Overlap detection | §7 | | | |
| Cross-cutting | §8 | | | |
| Known traps | §9 | | | |
| Performance | §10 | | | |

---

## 12. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md`
- Requirements: `doc/claude/offline-polygon-validation-requirements.md`
- Designs: `GEO-001` … `GEO-010`
- Precedent for this document: `VIZ-011-dashboard-test-plan.md`
