# Feature Design Document

## Feature: Polygon Capture — Walk the Boundary (GPS)

**Task ID**: GEO-004 (breakdown ref: T12)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: **Implemented and device-verified 2026-09-21** (foreground recording). Superseded in
part by GEO-014 (D-1 and §3/§4/§7). Deviations from the criteria below are deliberate and
recorded in D-4, D-5, D-8 and D-9. Background recording (+7h) is **not** included.
**Phase**: 2 — GPS capture
**Estimate**: 10.5h ≈ 1.5 days, **+7h ≈ 1 day** for background recording
**Depends on**: GEO-001, **GEO-014 (T13 — backend validators must be deployed first)**
**Reads**: GEO-014 (per-vertex accuracy) — several decisions below were reversed there

---

## 1. Context & Problem Statement

```
Currently:
- GEO-001 ships tap-to-draw only, which requires a visible basemap — and therefore
  connectivity — to be usable in the field.
- Kobo-style capture (walk the perimeter, record points automatically) does not exist.
- GEO-001's capture screen already presents both recording modes in its ODK-style Input method
  dialog, **disabled and labelled "Coming soon"** (GEO-001 D-9). The dialog, the mode list and the
  `inputMethod` state exist; this task fills them in rather than adding new chrome.

Goal:
- The enumerator walks the plot boundary and the app records vertices from GPS.
- This is the mode that works with NO connectivity, because the shape comes from the
  enumerator's feet rather than from an image.
```

**Ordering note**: this task is what makes offline field capture genuinely possible. If phase 1
ships connected-only (GEO-001 D-3), this is the task that removes that constraint.

---

## 2. Requirements

### User Acceptance Criteria
- [x] Recording cannot start without an adequate satellite fix; the enumerator is told what is
      being waited for rather than seeing a dead button — `text-waiting-for-fix`, and Start is
      disabled until `hasSatelliteLock` passes
- [x] Points are appended automatically on an interval while walking
- [x] **The enumerator chooses the recording interval and the accuracy control from the input
      method dialog, in ODK's position and order** — D-6, D-7
- [x] Where the form sets `geoConfig.allowTapping: false`, "Placement by tapping" is unavailable
      and the row says why — GEO-014 D-4
- [x] A wait for satellite lock reports progress rather than sitting still — D-9
- [x] A "record this point" action appends a vertex on demand, for corners and markers — the
      pin button appends at the enumerator's **position** while recording, not at the map
      centre; recording from the crosshair would let a plot be mapped from the far side of a
      fence
- [x] The live GPS position is shown distinctly from recorded vertices, with its accuracy
- [x] Fixes worse than the accuracy threshold are **recorded and drawn in red**, and the
      enumerator can see which vertices are the problem while still standing on the plot —
      `.vertex-poor`, plus a separate count in the status bar
- [x] Points drawn by tapping (GEO-001) and points from GPS converge on one ordered list

> **Correction, 2026-09-18 (GEO-014 D-3).** The second criterion previously read *"fixes worse
> than the accuracy threshold are **skipped**, and the enumerator can see why the count is not
> advancing"*. Bad fixes are now kept and marked instead of dropped. The concern behind the
> original — a boundary polluted with 40 m vertices looks plausible and is wrong — is unchanged
> and is now answered by marking plus a submit gate. See D-1 below.

### Technical Acceptance Criteria
- [x] Each recorded vertex carries its accuracy as an optional third element,
      `[lat, lng, accuracy]` — GEO-014 §3. A tapped vertex keeps writing two elements
- [x] Accuracy threshold default 15 m (ARF's default) — used to **mark** in this phase; the
      gate that blocks submission arrives in phase 3 (GEO-014 D-6). **Read from
      `extra.geoConfig.accuracyThreshold` when the form sets one — see D-5**
- [x] No path leaves a GPS watch or interval running
- [x] Reuses GEO-001's WebView map host and bridge — none of it re-paid
- [x] Enables the two disabled rows in GEO-001's Input method dialog rather than adding a new
      entry point; `addAtCenter` is already wired for "record this point"
- [ ] ⚠️ Does **not** open a second GPS watch — **not met, deliberately. See D-4.**

---

## 3. Data Model Changes

**No schema change.** `Answers.options` is a `JSONField` and the mobile geoshape answer lives
inside the `datapoints.json` blob, so neither store needs altering.

**The value shape changes.** A vertex becomes `[lat, lng]` **or** `[lat, lng, accuracy]` — the
third element is optional and permanent, and its absence means *not measured*. Full contract and
rationale in GEO-014 §3 and D-2.

> **Correction, 2026-09-18.** This section previously read *"**None.** Same `[[lat, lng], …]`
> value; the format does not record which mode produced a vertex."* Both halves are now false:
> the format gains an element, and that element is exactly what tells a GPS-walked vertex from a
> tapped one.

---

## 4. API Contract

**No new endpoints. Two existing backend validators must be relaxed first** — see GEO-014 §4.

| Location | Change |
|---|---|
| `is_coordinate_ring()` — `v1_data/serializers.py:75` | accept `len(point) in (2, 3)` |
| `bounding_box()` — `v1_mobile/geometry.py:58` | `zip(*coordinates)` unpacks two names from three |

⚠️ **This task now has a backend dependency and a release order.** A client that emits three
elements against an unpatched backend is refused with 400, and `background-task.js:379` turns
each refusal into a draft on the enumerator's handset. Backend deploys first (GEO-014 D-7).

> **Correction, 2026-09-18.** This section previously read *"**No API change.**"*

---

## 5. Decision Log

### D-1: Accuracy-gated capture, not best-effort — ~~discard~~ **record and mark**

**Decision (superseded 2026-09-18 by GEO-014 D-3)**: ~~A fix worse than the threshold is
**discarded, not appended**.~~ A fix worse than the threshold is **recorded and drawn in red**.

**Rationale**: ~~Matches ARF `TypeGeoDrawing.jsx:318`.~~ A boundary polluted with 40 m-error
vertices is worse than a shorter one — it produces a shape that looks plausible and is wrong.

> **The rationale survives; only the mechanism changed.** Marking answers that concern more
> directly than discarding does: the enumerator sees *which* vertices are bad while still on the
> plot, rather than watching a count refuse to advance and guessing why. From phase 3 a submit
> gate makes it binding (GEO-014 D-6).
>
> This is where the task stops being a verbatim port. ARF discards at
> `TypeGeoDrawing.jsx:318`; we deliberately do not, so that logic is written rather than copied
> — costed in §9. The **value format** stays compatible with ARF in both directions
> (GEO-014 D-2), so the divergence is behavioural only.

**Impact**: ~~The point count will sometimes not advance while walking. This must be *visible*, or
the enumerator will think the app has frozen.~~ **This risk is gone** — the count always
advances. The work costed for explaining a stalled counter is removed from §9; what remains is
satellite-lock gating before recording *starts*.

### D-2: Background recording is a separate increment

**Options Considered**:
1. Include background recording in this task
2. Ship foreground-only, add background as a costed increment

**Decision**: Option 2 — **+7h, tracked separately**.

**Rationale**: Background location changes the build, not just the code. It needs
`expo-dev-client`, an `expo-location` config plugin, a `TaskManager` task with
`foregroundService`, a persistent notification with a Stop action, and
`requestBackgroundPermissionsAsync` — a **second, separately grantable** Android permission.

**Impact**: ⚠️ **Expo Go cannot run any of it.** Its fixed native binary lacks the required
permissions. No SDK upgrade is needed (SDK 53 + `expo-location ~18.1.6` already support this);
what is needed is a development build. `./dc-mobile.sh` is unaffected — the container still runs
Metro; only the client on the handset changes.

**Honest assessment**: without background recording the enumerator must keep the screen awake
and the app foregrounded for an entire boundary walk, which they will not do.
**Foreground-only GPS capture is usable for a demo and frustrating in the field.**

> **Status change, 2026-09-18, revised 2026-09-21 (GEO-014 D-4).** The +7h stays outside *this*
> task, but it stops being optional for some programmes. A question with
> `geoConfig.allowTapping: false` disables tap-to-draw on mobile, making a boundary walk the only
> way to enter data — so for those forms the assessment above stops being a warning and becomes a
> blocker.
>
> | | Before | After |
> |---|---|---|
> | Phase 2 (this task) | optional | **still optional** |
> | Phase 3, `allowTapping` unset | optional | **still optional** |
> | Any phase, `allowTapping: false` | optional | **prerequisite** |
>
> The 2026-09-18 version of this note tied it to `detectOverlaps`, which made it unconditional
> across phase 3 and put 7 h into that baseline. With tapping on a key of its own it is a
> per-programme answer, so the hours move back out of the baseline into a conditional line.
>
> Do not move the +7h into this task. Budget it where it applies, and see §10.

### D-3: Where `accuracyThreshold` comes from in phase 2

**Decision**: Use ARF's built-in 15 m default. Do **not** pull the `geoConfig` work forward.

**Rationale**: `geoConfig` authoring (GEO-009) sits in phase 3 alongside overlap. Bringing it
forward only to make one number editable is not worth an upstream npm release.

> **Reaffirmed, 2026-09-18.** GEO-014 D-6 keeps this decision intact by deferring the *blocking*
> submit gate to phase 3. A hardcoded 15 m is harmless while it only decides what to colour red;
> as a submission block it would deadlock §9's four hours of field walking, where 20–40 m under
> canopy is ordinary and no knob exists yet to loosen it.

### D-4: A dedicated GPS watch during recording, after all

**Decision (found during implementation, 2026-09-18)**: the recording session opens its own
`watchPositionAsync` and removes it when recording stops. §2's criterion *"does not open a
second GPS watch"* is **not met**.

**Rationale**: the criterion rested on a premise that does not hold. `Home.js` feeds
`UserState.currentLocation`, but it watches on `buildParams.gpsInterval` — **60 seconds**. A
10-second capture interval reading that store would append the same stale fix six times in a
row, producing a boundary of duplicated points that looks like a walk and is not one.

The criterion §2 actually cares about is the one next to it — *"no path leaves a GPS watch or
interval running"* — and that is what the teardown is written against. Note that the two
criteria only make sense together if a watch exists to be torn down.

**Impact**: two watches coexist while recording. `expo-location` merges subscriptions to the
most demanding, so the cost is the accuracy level, not a doubled fix rate. Idle, nothing
changes: the accuracy strip and the live dot read `Home.js`'s fix exactly as in GEO-001.

The teardown is the risk this creates, and it is guarded in three places:
`watchPositionAsync` resolves *after* a screen may have been popped, so a `cancelled` flag
removes a subscription created after cleanup ran; the effect returns a cleanup function on
every branch, not only when a watch was opened; and clearing `recordingMode` — which is what
Stop, Save and back all do — re-runs that cleanup.

### D-5: `accuracyThreshold` is read from `geoConfig`, not hardcoded

**Decision (revises D-3, 2026-09-18)**: the threshold comes from
`extra.geoConfig.accuracyThreshold` when the form sets one, falling back to ARF's 15 m.

**Rationale**: D-3's reasoning was *"not worth an upstream npm release"* — the release being
the `akvo-react-form-editor` panel that would author the key. **That release has shipped**
(GEO-009 is Delivered as 2.0.5, and the host depends on it), so the key is already authorable
and reading it costs one line rather than a release.

It also supplies the knob D-3's own 2026-09-18 reaffirmation worried about not having: §9
budgets four hours of walking a real boundary, and under canopy 20–40 m is ordinary. With the
threshold hardcoded, every vertex of that test would render red with no way to tune it.

**Impact**: none on behaviour where no `geoConfig` is set, which is every form until one is
authored. D-3's conclusion — that phase 2 must not *block* on the threshold — is untouched;
that is GEO-014 D-6 and remains phase 3.

### D-6: The recording interval is chosen by the enumerator, matching ODK

**Decision**: `Recording interval` becomes a dropdown in the input method dialog, revealed when
**Automatic location recording** is selected — the same control, in the same place, as ODK
Collect. Options: **1 s, 5 s, 10 s, 20 s, 30 s, 1 min, 5 min, 10 min, 20 min, 30 min**.

**Default stays 10 s**, not ODK's 20 s. The number is ours and keeping it costs no transition:
the enumerator finds a dropdown where they expect one, and its starting value is not something
carried over from another app.

**Rationale**: this is the straightforward half of ODK parity — no behavioural difference to
reconcile, only a control we had not built. It also answers §10's open question *"is 10 s the
right interval, or should it vary by expected plot size?"* better than a second constant would:
the person who knows the plot size is standing on it.

**Impact**: the long end of the range is not padding. At 30 min a boundary walk records a
handful of corners, which is how a large concession gets mapped on foot without producing the
~180-vertex captures RISK-5 warns about.

### D-7: The accuracy control is ODK's, the label is not

**Decision**: a second dropdown sits where ODK puts `Accuracy requirement`, with ODK's options —
**None, 3 m, 5 m, 10 m, 15 m, 20 m** — and a default of **15 m**, ours. Its label states what it
does here: it **flags** vertices, it does not filter them.

**Rationale**: ODK's `Accuracy requirement` is a capture gate — a fix worse than it is never
recorded. That is precisely the behaviour GEO-014 D-3 reversed, on the argument that the
enumerator must see *which* vertices are bad while still standing on the plot.

So the control should be copied and the label must not be. Someone arriving from ODK would read
"Accuracy requirement: 10 meters", conclude poor fixes are being excluded, and have no reason to
check — the dialog looks exactly like the one they already know.

**A familiar label over unfamiliar behaviour is worse than no label at all**, because it removes
the prompt to look. Copying the *position* is what makes the transition easy; copying the
*sentence* is what would make it dangerous.

**Precedence — the form's value is a ceiling, not merely a default**: options looser than
`extra.geoConfig.accuracyThreshold` are not selectable, and `None` disappears entirely once a
form sets one. The enumerator may tighten what the form asked for; they may not loosen it.

Phase 2 only colours vertices, so this costs little today. It matters in phase 3, where the same
threshold **blocks submission** (GEO-014 D-6, D-9): without the ceiling, choosing `None` would
switch that gate off from inside the capture screen — the one place it must not be switchable
from.

**`None` means no marking at all**, and is valid only where the form expressed no opinion.

**Not persisted.** Both dropdowns reset to their defaults on each capture. ODK remembers the
last choice; doing the same needs a settings column and a migration, and nothing yet says an
enumerator resents re-picking once per plot. Listed in §10 rather than built.

### D-8: The watch opens while the enumerator is still choosing

**Decision (found on device, 2026-09-18)**: selecting either recording mode in the dialog opens
the GPS watch immediately, in a `standby` mode that records nothing. The satellite-lock gate is
evaluated against that watch's own fixes.

**Rationale**: the first build made the gate **circular**. Start stayed disabled until a fix
arrived; the watch only opened once `recordingMode` was set; and `recordingMode` was only set by
pressing Start. Nothing could ever satisfy the condition.

The screen fell back to `UserState.currentLocation`, which `Home.js` refreshes on
`buildParams.gpsInterval` — **60 seconds**, and not at all until location permission has been
granted. `LOCK_MAX_AGE_MS` was 30 s, *half* that cadence, so even a working GPS looked stale most
of the time. On device the button was simply dead, under a message that named no cause.

**Two fixes, both needed**: the standby watch above, and `LOCK_MAX_AGE_MS` raised to 90 s so the
fallback path cannot be stale by construction. A window shorter than the cadence feeding it is a
bug regardless of what else is fixed, and there is now a regression test pinning the relationship.

**Impact**: this is also what ODK does — it shows live accuracy while you choose a mode, for the
same reason. The watch is torn down if the dialog is cancelled, and it restarts once when Start
promotes `standby` to a real mode; `fixRef` survives that restart, so no fix is lost.

### D-9: Waiting states say what is happening

**Decision**: the wait shows a spinner and reports progress — *"Searching for satellites…"* with
no fix, then *"Improving the fix — 24 m so far…"* once one arrives.

**Rationale**: the first build showed a static *"Waiting for a GPS fix…"* with no motion and no
numbers. Nothing distinguished "acquiring normally" from "this will never work", and the only
honest description of the experience is the one it drew from field testing: stressful.

A GPS wait is the one moment on this screen where the app has information the enumerator does
not, and withholding it is what turns a 20-second wait into an unbounded one.

---

## 6. Type/Constant Mappings

| Setting | Phase 2 source | Phase 3 source |
|---|---|---|
| Accuracy threshold | Enumerator's choice, **capped by** `extra.geoConfig.accuracyThreshold`; 15 m default (D-5, D-7) — marks red only | same, and **blocks submission when `detectOverlaps` is on** (GEO-014 D-9) |
| Accuracy options | `None, 3, 5, 10, 15, 20` m — those looser than the form's value are not offered (D-7) | unchanged |
| Interval | Enumerator's choice, 10 s default (D-6) | unchanged |
| Interval options | `1, 5, 10, 20, 30` s and `1, 5, 10, 20, 30` min (D-6) | unchanged |
| Tap-to-draw | available unless `extra.geoConfig.allowTapping` is `false` (GEO-014 D-4) | unchanged |
| Vertex format | `[lat, lng, accuracy]`, third element optional (GEO-014 §3) | unchanged |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] A vertex captured before this change (`[lat, lng]`) stays valid permanently — no migration
- [x] `akvo-react-form` needs no change; a tapped vertex is byte-identical across clients
- [ ] ⚠️ Values captured by drawing and by walking are **no longer indistinguishable**

> **Correction, 2026-09-18 (GEO-014 D-1/D-2).** The first line of this section previously read
> *"Values captured by drawing and by walking are indistinguishable"*, stated as a deliberate
> property. It is now reversed on purpose: a measured vertex carries a third element, a tapped
> one does not, and that difference is what QA and the adaptive overlap threshold both read.

### Mobile App Impact
- [x] Sync endpoints affected: **`/sync`** (submission payload) and **`/device/datapoint-list`**
      (GEO-005 geometry) — both carry the third element
- [ ] SQLite schema changes: **no** — the answer lives in the `datapoints.json` blob
- [x] **Backend must deploy first** (GEO-014 D-7)

> **Correction, 2026-09-18.** "Sync endpoints affected: **none**" was true only while the value
> format was frozen.
- [x] **Build change required for background recording**: `expo-dev-client`,
      `"developmentClient": true` on the EAS `development` profile, `expo-location` config plugin
- [x] `app/src/lib/loc.js` currently requests **foreground permission only** — needs
      `requestBackgroundPermissionsAsync` added

---

## 8. Security Considerations

- [x] Background location is requested **only when auto-record first starts**, never at launch,
      with an explanation of why
- [x] If background permission is refused, foreground recording still works — the feature
      degrades, it does not fail
- [ ] Persistent notification must not leak plot or farmer identifiers to the lock screen

---

## 9. Testing Strategy

| Test Type | Coverage | Status |
|-----------|----------|---|
| Unit | A poor fix is **recorded and flagged**, not dropped; a tapped vertex is never flagged | ✅ `gps-vertex.test.js` |
| Unit | Accuracy written into the third element; a tapped vertex stays at two; a 0/negative/NaN reading writes **no** third element rather than `0` | ✅ 21 tests |
| Unit | Satellite lock needs *a* fix, not a good one; a stale fix is not a lock | ✅ |
| Unit | Accuracy options looser than the form's threshold are filtered out, and `None` disappears once a form sets one (D-7) | ✅ |
| Unit | Interval and accuracy option lists match ODK's, with **our** defaults selected | ✅ |
| Unit | `None` marks nothing — a null threshold must not coerce to `> 0` and redden every measured vertex | ✅ |
| Unit | `allowTapping` defaults to true and withdraws tapping only on a literal `false` (GEO-014 D-4) | ✅ |
| Unit | 🔴 `LOCK_MAX_AGE_MS` stays above `gpsInterval` — regression for the dead Start button (D-8) | ✅ |
| Unit (backend) | `allowTapping` is validated as a real boolean, like `detectOverlaps` | ✅ 12 tests |
| Manual (field) | A 30 min interval records corners, not a dense track (D-6) | ⬜ |
| Unit (backend) | `is_coordinate_ring` takes 2-, 3- and mixed-length rings, still refuses a flat point, a 0 and a non-numeric accuracy | ✅ 28 tests |
| Unit (backend) | `bounding_box` over 3-element and mixed rings | ✅ 25 tests |
| Integration | Round-trip: capture → `/sync` → `datapoint-list`, third element intact | ✅ backend half |
| Integration | A legacy 2-element answer still syncs and still validates | ✅ |
| Component | Dialog enables all three modes; Start disabled without a fix | ⚠️ **cannot run** — see below |
| Manual (field) | **Physically walk a boundary.** No substitute exists | ⬜ |
| Manual (field) | Red vertices appear at the right moment and are legible in sunlight | ⬜ |
| Manual (device) | Teardown: leave group / submit / background / kill — no watch survives | ⬜ |
| Manual (device) | Start becomes enabled outdoors, and the wait reports progress (D-8, D-9) | ✅ device-verified 2026-09-21 |

> ⚠️ **The component suite cannot run, and this predates the task.** `app/package.json` pairs
> React 19 with `react-test-renderer ^18.2.0`, so `MapDrawView.test.js` fails at import with
> `Cannot read properties of undefined (reading 'ReactCurrentOwner')` — the same breakage the
> GEO-002 commit recorded across 69 of 83 suites. The assertions here were updated to match the
> new behaviour and will pass once the pairing is fixed, but they are **not** evidence today.
>
> That is why the logic most worth testing was put in `form/lib/gps-vertex.js` rather than in
> the screen: what counts as measured, what counts as poor, and what counts as a lock are all
> exercised by a suite that does run. What is **not** covered by any automated test is the
> teardown of the watch and the interval — D-4's main risk — which rests on review and on the
> device pass below.

**Hours breakdown**

| Unit | h |
|---|---|
| Satellite-lock / fix-quality gating before recording starts | 0.5 |
| `watchPositionAsync` + interval capture | 1 |
| Record-on-click at current position | 0.5 |
| Live position marker + accuracy display | 0.5 |
| Lifecycle teardown (unmount, group change, submit) | 1 |
| Write accuracy into the vertex (GEO-014 §3) | 0.5 |
| Mark out-of-threshold vertices red on the map | 1 |
| Record-and-mark logic — written, not ported from ARF (D-1) | 1 |
| Interval + accuracy dropdowns in the input method dialog, with the ceiling filter (D-6, D-7) | 1 |
| **Field testing — physically walking a boundary** | 4 |
| **Total** | **10.5** |

Gating drops from 1h to 0.5h because D-1 removes the need to explain a stalled point count.

**Backend prerequisite (1.5h)**: **owned by GEO-014 (T13)** — relax `is_coordinate_ring`, fix
`bounding_box`, test both against 2-, 3- and mixed-length rings. **Must be deployed before this
task ships** (GEO-014 D-7); the failure mode is completed field work reverting to drafts on the
handset, not a log entry.

**Background increment (+7h)**: dev-client + config plugin + EAS profile (2h), `TaskManager` +
`foregroundService` (1h), notification with Stop action (0.5h), permission flow (0.5h),
backgrounded device testing (3h). Optional in phase 2, **prerequisite in phase 3** — see D-2.

> Over half of this task is someone walking around outside with a phone. That does not compress,
> and it is the only way to find out whether the accuracy gating behaves.

---

## 10. Open Questions

- [x] Is background recording in scope for the first field deployment? (D-2 — it is +1 day and
      forces a development build) **Answered 2026-09-18: yes, if phase 3 ships.** GEO-014 D-4
      ties tapping to `allowTapping`, so where a programme sets it to `false` a boundary walk is
      the only route into a handset and foreground-only recording stops being viable. **Revised
      2026-09-21**: conditional on that key rather than on `detectOverlaps`, so this is a
      per-programme answer, not a phase-wide one
- [x] Is 10 s the right interval, or should it vary by expected plot size? **Answered
      2026-09-18 (D-6): neither.** The enumerator picks it, as in ODK. 10 s is the default, not
      the rule, and the range runs to 30 min so a large concession can be walked corner to
      corner
- [ ] Should the two dropdown choices persist between captures? ODK remembers them; we reset
      each time (D-7). Persisting needs a settings column and a migration, so it waits for
      someone to actually ask
- [ ] Does the red marking need a matching entry in the vertex list, or is the map enough? A
      vertex buried under later ones can be hard to spot on a dense boundary

---

## 11. References

- Value format and reversed decisions: `doc/design/GEO-014-per-vertex-accuracy.md`
- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T12)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-1.3c, FR-8, D8)
- Port source: `akvo-react-form` `TypeGeoDrawing.jsx:285-334` — **partial**: the watch/interval
  half still ports verbatim; the accuracy handling at `:318` deliberately does not (D-1)

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
