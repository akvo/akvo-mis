# Feature Design Document

## Feature: Polygon Capture — Walk the Boundary (GPS)

**Task ID**: GEO-004 (breakdown ref: T12)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 2 — GPS capture
**Estimate**: 8h ≈ 1 day, **+7h ≈ 1 day** for background recording
**Depends on**: GEO-001

---

## 1. Context & Problem Statement

```
Currently:
- GEO-001 ships tap-to-draw only, which requires a visible basemap — and therefore
  connectivity — to be usable in the field.
- Kobo-style capture (walk the perimeter, record points automatically) does not exist.

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
- [ ] Fixes worse than the accuracy threshold are **skipped**, and the enumerator can see why
      the count is not advancing
- [ ] Points drawn by tapping (GEO-001) and points from GPS converge on one ordered list

### Technical Acceptance Criteria
- [ ] Accuracy threshold default 15 m (ARF's default)
- [ ] No path leaves a GPS watch or interval running
- [ ] Reuses GEO-001's WebView map host and bridge — none of it re-paid

---

## 3. Data Model Changes

**None.** Same `[[lat, lng], …]` value; the format does not record which mode produced a vertex.

---

## 4. API Contract

**No API change.**

---

## 5. Decision Log

### D-1: Accuracy-gated capture, not best-effort

**Decision**: A fix worse than the threshold is **discarded, not appended**.

**Rationale**: Matches ARF `TypeGeoDrawing.jsx:318`. A boundary polluted with 40 m-error vertices
is worse than a shorter one — it produces a shape that looks plausible and is wrong.

**Impact**: The point count will sometimes not advance while walking. This must be *visible*, or
the enumerator will think the app has frozen.

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

### D-3: Where `accuracyThreshold` comes from in phase 2

**Decision**: Use ARF's built-in 15 m default. Do **not** pull the `geoConfig` work forward.

**Rationale**: `geoConfig` authoring (GEO-009) sits in phase 3 alongside overlap. Bringing it
forward only to make one number editable is not worth an upstream npm release.

---

## 6. Type/Constant Mappings

| Setting | Phase 2 source | Phase 3 source |
|---|---|---|
| Accuracy threshold | Hardcoded 15 m | `extra.geoConfig.accuracyThreshold` (GEO-009) |
| Interval | Hardcoded 10 s | not configurable |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Values captured by drawing and by walking are indistinguishable

### Mobile App Impact
- [ ] Sync endpoints affected: **none**
- [ ] SQLite schema changes: **no**
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
| Unit | Accuracy filter rejects a poor fix; ordered merge of tapped + GPS points |
| Manual (field) | **Physically walk a boundary.** No substitute exists |
| Manual (device) | Teardown: leave group / submit / background / kill — no watch survives |

**Hours breakdown**

| Unit | h |
|---|---|
| Satellite-lock / fix-quality gating before recording starts | 1 |
| `watchPositionAsync` + interval capture | 1 |
| Record-on-click at current position | 0.5 |
| Live position marker + accuracy display | 0.5 |
| Lifecycle teardown (unmount, group change, submit) | 1 |
| **Field testing — physically walking a boundary** | 4 |
| **Total** | **8** |

**Background increment (+7h)**: dev-client + config plugin + EAS profile (2h), `TaskManager` +
`foregroundService` (1h), notification with Stop action (0.5h), permission flow (0.5h),
backgrounded device testing (3h).

> Over half of this task is someone walking around outside with a phone. That does not compress,
> and it is the only way to find out whether the accuracy gating behaves.

---

## 10. Open Questions

- [ ] Is background recording in scope for the first field deployment? (D-2 — it is +1 day and
      forces a development build)
- [ ] Is 10 s the right interval, or should it vary by expected plot size?

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T12)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-1.3c, FR-8, D8)
- Port source: `akvo-react-form` `TypeGeoDrawing.jsx:285-334`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
