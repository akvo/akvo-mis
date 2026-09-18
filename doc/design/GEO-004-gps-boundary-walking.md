# Feature Design Document

## Feature: Polygon Capture — Walk the Boundary (GPS)

**Task ID**: GEO-004 (breakdown ref: T12)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft — **revised 2026-09-18 by GEO-014**, which supersedes D-1 and §3/§4/§7
**Phase**: 2 — GPS capture
**Estimate**: 9.5h ≈ 1 day, **+7h ≈ 1 day** for background recording
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
- [ ] Recording cannot start without an adequate satellite fix; the enumerator is told what is
      being waited for rather than seeing a dead button
- [ ] Points are appended automatically on an interval while walking
- [ ] A "record this point" action appends a vertex on demand, for corners and markers
- [ ] The live GPS position is shown distinctly from recorded vertices, with its accuracy
- [ ] Fixes worse than the accuracy threshold are **recorded and drawn in red**, and the
      enumerator can see which vertices are the problem while still standing on the plot
- [ ] Points drawn by tapping (GEO-001) and points from GPS converge on one ordered list

> **Correction, 2026-09-18 (GEO-014 D-3).** The second criterion previously read *"fixes worse
> than the accuracy threshold are **skipped**, and the enumerator can see why the count is not
> advancing"*. Bad fixes are now kept and marked instead of dropped. The concern behind the
> original — a boundary polluted with 40 m vertices looks plausible and is wrong — is unchanged
> and is now answered by marking plus a submit gate. See D-1 below.

### Technical Acceptance Criteria
- [ ] Each recorded vertex carries its accuracy as an optional third element,
      `[lat, lng, accuracy]` — GEO-014 §3. A tapped vertex keeps writing two elements
- [ ] Accuracy threshold default 15 m (ARF's default) — used to **mark** in this phase; the
      gate that blocks submission arrives in phase 3 (GEO-014 D-6)
- [ ] No path leaves a GPS watch or interval running
- [ ] Reuses GEO-001's WebView map host and bridge — none of it re-paid
- [ ] Enables the two disabled rows in GEO-001's Input method dialog rather than adding a new
      entry point; `addAtCenter` is already wired for "record this point"
- [ ] Does **not** open a second GPS watch — `Home.js` already runs one into
      `UserState.currentLocation`, which GEO-001's accuracy strip reads

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

> **Status change, 2026-09-18 (GEO-014 D-4).** The +7h stays outside *this* task, but it is no
> longer optional overall. From phase 3, a question with `geoConfig.detectOverlaps = true`
> disables tap-to-draw on mobile, making a boundary walk the only way to enter data — so the
> assessment above stops being a warning and becomes a blocker.
>
> | | Before | After |
> |---|---|---|
> | Phase 2 (this task) | optional | **still optional** |
> | Phase 3 (overlap) | optional | **prerequisite** |
>
> Do not move the +7h into this task. Budget it in phase 3, and see §10.

### D-3: Where `accuracyThreshold` comes from in phase 2

**Decision**: Use ARF's built-in 15 m default. Do **not** pull the `geoConfig` work forward.

**Rationale**: `geoConfig` authoring (GEO-009) sits in phase 3 alongside overlap. Bringing it
forward only to make one number editable is not worth an upstream npm release.

> **Reaffirmed, 2026-09-18.** GEO-014 D-6 keeps this decision intact by deferring the *blocking*
> submit gate to phase 3. A hardcoded 15 m is harmless while it only decides what to colour red;
> as a submission block it would deadlock §9's four hours of field walking, where 20–40 m under
> canopy is ordinary and no knob exists yet to loosen it.

---

## 6. Type/Constant Mappings

| Setting | Phase 2 source | Phase 3 source |
|---|---|---|
| Accuracy threshold | Hardcoded 15 m — **marks red only** | `extra.geoConfig.accuracyThreshold` (GEO-009) — marks everywhere, **blocks submission only when `detectOverlaps` is on** (GEO-014 D-9) |
| Interval | Hardcoded 10 s | not configurable |
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

| Test Type | Coverage |
|-----------|----------|
| Unit | A poor fix is **recorded and flagged**, not dropped; ordered merge of tapped + GPS points |
| Unit | Accuracy written into the third element; a tapped vertex stays at two |
| Integration | Round-trip: capture → `/sync` → `datapoint-list`, third element intact |
| Integration | A legacy 2-element answer still syncs and still validates |
| Manual (field) | **Physically walk a boundary.** No substitute exists |
| Manual (field) | Red vertices appear at the right moment and are legible in sunlight |
| Manual (device) | Teardown: leave group / submit / background / kill — no watch survives |

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
| **Field testing — physically walking a boundary** | 4 |
| **Total** | **9.5** |

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
      disables tapping when `detectOverlaps` is on, so a boundary walk becomes the only route
      into a handset and foreground-only recording stops being viable
- [ ] Is 10 s the right interval, or should it vary by expected plot size?
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
