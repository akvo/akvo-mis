# Feature Design Document

## Feature: Polygon Overlap Detection

**Task ID**: GEO-007 (breakdown ref: T4)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: **Implemented 2026-09-23**, device-verified the same day — `form/lib/overlap.js`
(ratio + adaptive threshold), `form/lib/overlap-check.js` (preflight, candidate query, rule
results), the Validate button and report in `form/fields/TypeGeoDrawing.js`, and the stored
verdict read by the submit gate in `form/lib/index.js`. 48 unit and integration tests.
Revised 2026-09-18 by GEO-014, which supersedes D-3; **D-10** (incomplete candidate set →
refuse + Retry) and **D-11** (the error counts and numbers overlaps instead of naming them,
after the first device test) both added 2026-09-23
**Phase**: 3 — Overlap detection *(moved down on reviewer feedback)*
**Estimate**: 7.5h ≈ 1 day (Mobile)
**Depends on**: GEO-001, GEO-006, GEO-009, **GEO-014**

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
- [ ] ~~The error names both datapoints: `New plot for <current> overlaps with plot for
      <existing>`~~ — **superseded 2026-09-23 by D-11.** The error carries a **count and
      numbered percentages**, no names: `Overlaps 3 plots: #1 (34.0%), #2 (28.3%), #3 (22.5%)
      (limit 20%)`
- [ ] **All** simultaneous overlaps are reported, not just the first — as one numbered line,
      not one line each (D-11)
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
- [ ] **Incomplete candidate set → refuse, never pass** (D-10). Show why; offer **Retry** when
      sync can fix it. Same submit gate as "not validated" for required questions

### Technical Acceptance Criteria

- [ ] Overlap ratio = `intersection_area / min(new_area, existing_area)`
- [ ] Threshold is **derived from the accuracy of both polygons** and clamped by
      `extra.geoConfig.overlapThreshold` (default **20 %**) as its **ceiling** — GEO-014 D-5
- [ ] When either polygon has no measured accuracy, the threshold falls back to
      `overlapThreshold` — i.e. exactly today's behaviour
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

### D-3: Threshold is a percentage of the *smaller* polygon, ~~default 20 %~~ **capped at the authored value**

**Decision (revised 2026-09-18 by GEO-014 D-5)**: the ratio is still
`intersection / min(areaA, areaB)`. The threshold it is compared against is no longer the flat
authored percentage:

```
combined  = accA + accB                             // metres, conservative sum
computed  = combined / sqrt(min(areaA, areaB))
threshold = clamp(computed, overlapThresholdFloor, overlapThreshold)
```

**Rationale**: The source documents conflict — 20 % in one, 5 % in two others. 20 % carries the
documented reasoning: it allows minor boundary touching from GPS drift while blocking
significant overlap. Two genuinely adjacent plots will always show a sliver of intersection.

> **Why that reasoning does not survive contact with arithmetic.** Spurious overlap from GPS
> error is a band of width ≈ accuracy along a shared edge, so the noise ratio is ≈
> `accuracy / √area` — it *shrinks* as plots grow. A single percentage is therefore wrong in
> both directions, and only happens to be right near 1 ha:
>
> | Plot area | Noise ratio at 30 m combined | Flat 20 % means |
> |---|---|---|
> | 0,01 ha | 300 % | every small plot false-positives |
> | 0,1 ha | 95 % | still far too strict |
> | 1 ha | 30 % | roughly right — the one size it fits |
> | 10 ha | 9,5 % | **2 ha of real encroachment passes** |
> | 50 ha | 4,2 % | **10 ha of real encroachment passes** |
>
> Treating the authored number as a **ceiling** rather than the threshold keeps one property
> worth stating plainly: **the adaptive rule can never be more permissive than today.** It
> tightens where accuracy permits and falls back to the authored value everywhere else, so no
> existing programme's configuration changes meaning and there is no regression path.
>
> The clamp is not optional: without a ceiling a 0,01 ha plot computes 300 % and *no overlap can
> ever fail*. Fail-open is the exact failure GEO-005 §2 exists to prevent.

**Impact**: 20 % is inherited from a farm-plot context and has **not** been measured against our
terrain. It is configurable per question for exactly this reason — and as a ceiling it now
degrades gracefully when the measurement is better than the guess.

**No upstream change.** `overlapThreshold` keeps its name, type, `20` default and GEO-009 panel;
only its documented meaning moves from "overlap tolerated" to "most overlap ever tolerated".

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

### D-9: Overlap severity is a key this task must resolve — `validateOverlap` *(2026-09-21)*

**Raised by**: editor 2.0.6, which made overlap severity authorable before anything reads it.
That inversion is deliberate and is recorded in GEO-009 §2.1; this decision is the app-side half.

**The problem it fixes**: the editor's first draft of the rule table labelled overlap's severity
as fixed. Both candidate labels were defensible from *some* document and only one was right —
FR-4.4 (*"it **does** block submission via `validateAllGroups()`"*) and FR-4.7.6 make it
**block**, while GEO-012 §2.4's MAST evidence argues for warn. That is not a documentation
conflict to resolve once; it is a genuine policy difference between programmes, which is exactly
what GEO-002 D-4 invented severity keys for.

**Decision**: overlap resolves severity the same way every other rule does.

| # | Source | Value | Severity |
|---|---|---|---|
| 1 | `question.extra.geoConfig.validateOverlap` | `true` / `false` | `block` / `warn` |
| ~~2~~ | ~~Device setting `validatePolygonOverlap`~~ | — | **struck, see below** |
| 3 | *(not present)* | — | `block` |
| 4 | **Clamp**: question is not `required` | — | `warn`, per D-7 |

> **Row 2 is struck, 2026-09-21 — do not build it.** The device layer was removed from
> `resolveSeverity` the same day (GEO-002 D-4), on the argument D-4 itself made: a device-wide
> toggle is *"invisible to the programme and travels with the enumerator across every form"*,
> and is only defensible while the programme has no way to say this per question. Editor 2.0.6
> gave it one.
>
> Adding `validatePolygonOverlap` now would reintroduce exactly the layer just removed, for the
> one rule whose stakes are highest — a land dispute. The *"work this implies"* list below is
> shortened accordingly: resolve `validateOverlap` through the existing helper, and build no
> device setting.
>
> Resolution is two layers for every rule: `geoConfig` → `block`, then the `required` clamp.

Row 3 is today's behaviour, so a form authored before the app honours the key behaves
identically. Row 4 is D-7 unchanged — this decision does not alter the `required` clamp, it
places overlap under the same resolution the shape and area rules already use.

**`false` never means skip.** Detection is switched off by `detectOverlaps`, never by a severity.
The two keys stay separate because they answer different questions, and because
`enabled_geoshape_question_ids` gates on `detectOverlaps=True` as a literal-boolean JSON lookup —
a tri-valued key there would silently disable the feature for every form (GEO-009 §2.1).

**Work this implies**:
- Resolve `validateOverlap` where overlap failures are graded, reusing the helper GEO-002 D-4
  added for `validateShape` / `validateArea` rather than a second code path
- ~~A `validatePolygonOverlap` device setting~~ — **struck 2026-09-21**, see the note above.
  There is no device layer left to add it to
- `_geo_config_issues()` must validate it as a strict boolean (GEO-010 §6)

**Until then**: an author who picks *Warn only* stores a value the device ignores. The default
stores nothing, so this is a gap for programmes that opt in, not a regression for anyone else.

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

### D-10: Incomplete candidate set → refuse + Retry *(2026-09-23)*

**Question was**: refuse to validate, or validate with a visible caveat? Silently passing is not
an option.

**Decision**: **Refuse.** Never caveat-pass. Name the cause. Offer **Retry** when the cause is a
sync gap; do not offer a useless Retry for local corruption.

**What "incomplete" actually means** — three different failures that must share one refuse
branch (because each would otherwise report a confident "no overlap"):

| Cause | How the device knows | Recoverable by sync? | Retry does |
|---|---|---|---|
| **Index not ready** (upgrade / post-reset) | `config.geometryIndexReady = 0` (GEO-006 D-4) | Yes | Start / resume datapoint sync |
| **Download incomplete or interrupted** | Sync queue still has forms with `lastPage < totalPage`, or datapoint sync is in progress | Yes | Resume datapoint sync |
| **Gapped index after a "finished" sync** | Local `geometry_index` row count for the form ≠ server `geometry_total` (GEO-005) | Yes | Force a full geometry re-pull (e.g. `geometry_full=true` / clear cursor and sync again) |
| **A sync is running** | A `sync-form-datapoints` job is `ON_PROGRESS` | — | No Retry: one is already running. Copy says to validate again when it finishes |
| **Index drifted** | A candidate's answers are not on the device, breaking GEO-006 D-6's subset invariant | Yes | Resync rebuilds both sides |
| **Local SQLite failure** | Index query throws, the table is missing after migration should have created it, or the index names a candidate whose answers are not on the device | No | No Retry — message points to Reset / re-login. A second tap cannot heal a corrupt DB |

**Why an in-flight sync needs its own gate.** `finishDatapointSync` clears the sync queue when
a sync completes, and the next sync writes no queue row until its first page lands — seconds
later on a field connection. In that window `hasIncomplete()` is false and readiness is still
`1` from the previous run, so validation measured the **pre-refresh** index and returned a
confident pass. The Retry button leads straight into it: it kicks a sync and invites the
enumerator to press Validate again. The gate is on `ON_PROGRESS` only — a PENDING job is one
that has not started (offline, or waiting for the next tick), and refusing then would break the
offline case this feature exists for.

**Repeat instances query the base question id.** `transformForm` renders repeat *n* with the id
`"987-1"`, while `geometry_index` stores `987` plus `repeatIndex`. Passing the suffixed id into
`WHERE questionId = ?` compares an INTEGER column against text SQLite cannot coerce, so it
matched **nothing** — every repeated polygon passed with no candidate examined. Fixed
2026-09-23; `baseQuestionId` in `overlap.js` strips the suffix, and the repeat index is still
used to read the candidate's answer.

The last of those deserves its own line: GEO-006 D-6 makes `geometry_index` a subset of
`datapoints` by writing both in one transaction, so a candidate with no answers means the two
have **drifted**. Measuring the remaining candidates and reporting "no overlap" would be a false
pass; refusing is the only safe reading. A neighbour stored with one or two vertices is a
different thing and is skipped, not refused — it encloses no area and cannot overlap anything,
so blocking this enumerator behind someone else's data quality would be wrong.

The page-level `complete: false` on early pages of a listing is **normal during sync**; it is
not itself a validation-time signal. Validation-time gates are the rows above.

**UI**:
- Pressing Validate (or hitting the submit gate) enters an **unavailable / error** state — not
  pass, not a soft warning that still records a pass
- Copy names the cause in plain language, e.g. *"Nearby plots are still downloading — retry
  sync before validating"* vs *"Plot index is damaged — reset the app and sync again"*
- **Retry** is shown only for the recoverable rows; it kicks datapoint sync and returns the
  enumerator to the form (they press Validate again when sync finishes — do not auto-pass)
- Required questions: same submit block as "not validated" (D-1 / D-7)

**Why not caveat-pass**: field users treat green as done; a recorded "pass (incomplete)" is
indistinguishable from a real pass once the submission leaves the device. That is the false
pass GEO-005 and GEO-006 D-4 exist to prevent (QA-605).

**Impact on hours**: small — one shared preflight before the bbox query, a message + optional
Retry wired to the existing datapoint-sync job. No new sync protocol.

### D-11: The error counts and numbers the overlaps; it does not name them *(2026-09-23)*

**Supersedes** the acceptance criterion `New plot for <current> overlaps with plot for
<existing>`, which came from the reference validator.

**Raised by**: the first device test. A single overlap rendered as

> Overlaps the plot for First plot - 916464 - Indonesia - Jakarta - East Jakarta - Kramat Jati -
> Cawang - wife__husband__partner,children by 28.3% (limit 20%).

Six lines, and the enumerator still cannot tell which plot is meant. The cause is structural,
not a bad test fixture: the name is `generateDataPointName` output, every `meta` answer joined
with `" - "`, so on any form with an administration cascade it is always an administrative path.
The reference validator could name plots because it held its own short `instanceName`; we do not.

**Decision**: the message carries a **count** and **numbered percentages**.

```
1 overlap    Overlaps 1 plot by 28.3% (limit 20%).
3 overlaps   Overlaps 3 plots: #1 (34.0%), #2 (28.3%), #3 (22.5%) (limit 20%).
```

**One result, not one per conflict.** Every overlap is still reported — that criterion is
unchanged — but as one sentence. Three near-identical lines said no more than one numbered line
does, and cost three times the screen on a phone.

**The numbers are positions in the conflict array, ordered worst first**, and that ordering is
part of the contract rather than an implementation detail: **GEO-008 must label its map polygons
from the same array**, or `#2` in the text and `#2` on the map are different plots. Identity
moves there, which is where it is actually usable — a name in a sentence never told the
enumerator where to walk.

**The limit may be a range.** Each pair computes its own threshold from the accuracy and area of
*both* polygons (GEO-014 D-5), so two conflicts on one plot can legitimately be judged at 9.5 %
and 20 %. A uniform set prints one number; a mixed set prints `limit 9.5-20%`. Printing one of
them would misstate why the other failed.

**Also fixed here**: the report was printing blocking failures that the submit gate prints again
a few pixels below, prefixed with the question label — the overlap appeared twice on screen.
Blocking lines now drop out of the report once the gate has spoken, which is the rule
`showHint` already applied to the amber hints (GEO-002 D-8). Warnings stay, since a warn never
reaches the gate.

---

## 6. Type/Constant Mappings

| Setting | Key | Default |
|---|---|---|
| Overlap threshold **ceiling** | `extra.geoConfig.overlapThreshold` | `20` (%) |
| Overlap threshold **floor** | `extra.geoConfig.overlapThresholdFloor` | `5` (%) — authorable since editor 2.0.6 |
| Enable | `extra.geoConfig.detectOverlaps` | `false` |
| **Severity** | `extra.geoConfig.validateOverlap` | absent → `block`. **Authorable since editor 2.0.6; no reader yet — see D-9.** There is no device layer to fall through to; it was removed on 2026-09-21 (GEO-002 D-4) |
| Own polygon's accuracy | `vertex[2]`, optional third element | absent = not measured (GEO-014 §3) |
| Candidate's accuracy | `geometry.accuracy` summary from GEO-005 | `measured: false` = not measured (GEO-014 D-10) |

The two accuracy sources are deliberately different shapes. The polygon being validated is local,
so its per-vertex readings are in hand. A candidate arrives through the datapoint list, which
summarises — `accA + accB` needs one number per polygon, not 180.

`detectOverlaps` controls detection only. Whether a boundary may be traced rather than walked is
a separate key, `allowTapping` (GEO-014 D-4, revised 2026-09-21), so a polygon reaching this check
may legitimately carry no accuracy at all — the fallback branch is a normal path, not an edge case
for legacy rows. It also covers answers entered through the webform, which is not an
overlap-checked route.

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Forms without `detectOverlaps` behave exactly as phase 1
- [x] No stored data changes

### Mobile App Impact
- [ ] SQLite schema changes: none here (GEO-006 owns the index)
- [x] Depends on GEO-005's completeness signal — **must not validate against a partial set**

> **Added 2026-09-23 — two things GEO-006 now hands this task.**
>
> **1. The index has no `coordinates` column** (GEO-006 D-5). The bbox range query returns
> identifiers and bounding boxes; coordinates for the 5–50 survivors are read from the local
> `datapoints.json` in a second query keyed on their ids, then parsed. This is what keeps peak
> memory constant in the size of the form instead of linear in it — the candidate fetch is no
> longer a single query, and the hours below assume both.
>
> **2. There is a second reason to refuse to validate.** Alongside GEO-005's `complete: false`,
> `config.geometryIndexReady = 0` means the local index predates the feature and is empty while
> `datapoints` is full (GEO-006 D-4 — existing installs are not backfilled). Querying it returns
> no candidates and would report a confident **"no overlap"**. Both conditions must route into
> the same refusal branch; neither may fall through to a pass.

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
| Unit | Adaptive threshold clamps to the ceiling on a small plot, tightens below it on a large one, and never exceeds `overlapThreshold` |
| Unit | Threshold falls back to `overlapThreshold` when either polygon has no measured accuracy |
| Unit | Identical polygons → 100 %; disjoint → no candidates |
| Unit | Self-exclusion when editing an existing datapoint |
| Integration | Multiple simultaneous overlaps all reported, as one numbered line, worst first (D-11) |
| Unit | The message never contains the other datapoint's name (D-11) |
| Unit | Mixed per-pair thresholds print as a range, not as one of them (D-11) |
| Integration | A blocking failure appears once, not in both the report and the gate (D-11) |
| Integration | State machine: edit after pass → *not validated* → submit blocked |
| Integration | Incomplete set refuses validation; Retry resumes sync; SQLite failure has no Retry (D-10) |
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
| ~~Spike: verify `@turf` submodules work in React Native~~ — **moved to GEO-002 D-6**, which now adds `@turf/kinks` in phase 1 | 0 |
| bbox range query + candidate fetch from `datapoints.json` (GEO-006 D-5) | 0.75 |
| Intersection ratio vs threshold | 0.5 |
| Adaptive threshold from vertex accuracy, with clamp and fallback (GEO-014 D-5) | 1 |
| "Validate now" button, 3 states, progress | 1 |
| State reset on edit; submit gate reads stored result | 1 |
| Error assembly — multiple conflicts, repeat instance | 0.5 |
| Unit tests with known fixtures | 1.5 |
| **Perf test at 5,000 plots (observed ceiling), 10,000 as headroom** | 1.5 |
| **Total** | **7.75** |

The `@turf` spike moved out to GEO-002 (−1) and the adaptive threshold moved in (+1); those
cancel exactly, which is a coincidence rather than a plan. The remaining +0.25 over the original
7.5 is the two-query candidate fetch that GEO-006 D-5 introduces.

**On the volume figures** (recorded 2026-09-23): the busiest deployment holds **1,000–5,000
datapoints per form**, not 10,000. The larger number stays in the test as headroom, but the
5,000 case is the one that must pass — and it is the number the GEO-006 D-7 memory arithmetic
is built on.

---

## 10. Open Questions

- [x] Is 20 % right for the first real programme? Inherited, not measured. **Partly answered
      2026-09-18**: it is now a ceiling, not the threshold, so being too permissive matters much
      less — the adaptive value tightens it wherever accuracy allows. Being too *strict* on a
      sub-hectare plot is still possible and still unmeasured
- [x] `FLOOR` for the adaptive threshold → **answered 2026-09-18 (GEO-014 D-8)**:
      `geoConfig.overlapThresholdFloor`, default **5 %**, read by the app and **authorable in
      the editor since 2.0.6**.
      Worth noting *why* 5: D-3 above records that the source implementations disagreed —
      *"20 % in one, 5 % in two others"* — and resolved it by discarding the 5. With a clamp both
      numbers get a home, **20 as the ceiling and 5 as the floor**, which suggests the two
      references were answering different questions rather than one of them being wrong. The
      default is still unmeasured against our terrain, exactly as 20 is
- [x] What does the UI do when the candidate set is **incomplete** (GEO-005)? Refuse to
      validate, or validate with a visible caveat? Silently passing is not an option
      → **Answered 2026-09-23 (D-10)**: **refuse**, never caveat-pass. Distinguish causes
      (index not ready / incomplete download / count mismatch / SQLite damage). **Retry** only
      when sync can fix it; Reset for local corruption.
- [x] Does `@turf` behave on a real device? **Answered by phase 1**: GEO-002 D-6 adds
      `@turf/kinks` to `app/` and carries the spike. If it fails there, this task learns about it
      two phases early — which is the point of the relocation. `@turf/intersect` is a larger
      module than `kinks`, so a green spike de-risks but does not fully settle this one.

### Left open by the implementation

- [ ] 🔴 **Candidates are scoped to the form being filled, not to its registration parent.**
      D-6 wants registration plots, which for a monitoring form means its parent. Whether
      `forms.parentId` holds a backend form id or a local one is not settled, and guessing wrong
      scopes the bbox query to a form with no rows — which reports a confident "no overlap" for
      every plot. Same-form scoping is the conservative, well-defined behaviour shipped in
      `FormPage.js`; it is marked in the code and needs deciding before a monitoring form with
      `detectOverlaps` reaches a programme
- [ ] **D-10's third cause uses a datapoint count, not a geometry count.** The design compares
      local `geometry_index` rows against a server `geometry_total`; GEO-005 publishes no such
      field, so the shipped preflight compares local synced datapoints against the sync queue's
      `totalData`. It refuses too often rather than passing wrongly — the correct direction —
      but a form whose missing rows are all non-geoshape reports a gap it does not have
- [ ] **The performance test has not been run.** 5,000 polygons on a real low-end device,
      target < 500 ms (§9). Everything below the bbox pre-filter rests on it

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
- [x] **Per-tenant custom rules** (D-8) — needs its own design: registration, distribution to
      devices, and safe execution. Opened as **GEO-012**; researched 2026-09-17 and answered as a
      **parameterised catalogue, not an expression DSL**, so registration and safe execution fall
      away. The registry contract D-8 demands is now specified in **GEO-013**, which this task
      implements against rather than invents
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
