# Feature Design Document

## Feature: `geoConfig` Authoring UI

**Task ID**: GEO-009 (breakdown ref: T8)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 3 — Overlap detection
**Estimate**: 5h ≈ 1 day (Frontend — **upstream repo + host**)
**Blocks**: GEO-007

---

## 1. Context & Problem Statement

```
Currently:
- akvo-react-form #192 established `extra.geoConfig.accuracyThreshold` as a per-question
  convention, but there is NO UI to author it.
- Overlap detection needs a threshold and an enable switch, and hand-edited form JSON is
  not acceptable.

Goal:
- Three fields authorable on a geoshape question in the form builder.
```

**⚠️ This work lives in a separate repository.** The form builder is
`akvo-react-form-editor`, imported wholesale at `frontend/src/pages/form-builder/FormBuilderCreate.jsx:3`.
Most of this task is an upstream PR plus an npm release, not akvo-mis frontend work.

---

## 2. Requirements

### The complete configurable set — exactly three fields

| Control | Key | Type | Default |
|---|---|---|---|
| GPS accuracy threshold (m) — *already exists in ARF #192* | `accuracyThreshold` | number | `15` |
| ☑ Detect overlaps with other answers to this question | `detectOverlaps` | boolean | `false` |
| … overlap threshold % *(revealed only when ticked)* | `overlapThreshold` | number | `20` |

```json
"extra": {
  "geoConfig": {
    "accuracyThreshold": 15,
    "detectOverlaps": true,
    "overlapThreshold": 20
  }
}
```

### Everything else is a hardcoded floor — build no UI for it

| Rule | Value | Why no checkbox |
|---|---|---|
| Parses as a polygon | — | Nothing to validate otherwise |
| Minimum vertices | `3` | Below 3 it is not a polygon |
| No self-intersection | — | Area is ambiguous on a self-crossing ring |
| Minimum area | `10 m²` | Catches double-taps; below any real plot |

**There are deliberately no `validateShape`, `validateMinArea`, `minPoints` or `minAreaSqm`
keys.** An enable-checkbox for "should this be a valid polygon?" has no meaningful *off* state.

### User Acceptance Criteria
- [ ] `overlapThreshold` is revealed only when `detectOverlaps` is ticked
- [ ] The overlap checkbox carries help text stating the consequence: *enabling this syncs the
      geometry of all other responses to this question onto the enumerator's device*
- [ ] Reopening the form restores checkbox and numeric state
- [ ] Values survive publish and appear unchanged in the mobile form payload

### Design-review addition: rules are added incrementally, not all at once

- [ ] The author **selects which validations to apply** — they are not forced to configure all
      of them. Review described it as picking from a dropdown and adding rules one at a time:
      *"you don't have to add all the validations in one shot"*
- [ ] A geoshape question with **no rules selected** is valid, and produces no Validate button
      on mobile (GEO-007)
- [ ] The panel must accommodate **more rules over time** without redesign — see GEO-007 D-8

> ⚠️ **This reopens a decision.** GEO-002 D-1 and GEO-003 D-2 made shape and area validation
> *always-on fixed floors*, precisely because "should this be a valid polygon?" has no sensible
> *off* state. Design review instead describes them as **selectable rules with configurable
> values** — accuracy, minimum size, vertices — which is the original request.
>
> Both readings are defensible: a floor that only catches accidents versus a programme-specific
> quality bar. They are not compatible, and the difference changes this panel from three fields
> to six. **Resolve before building GEO-009.**

### Technical Acceptance Criteria
- [ ] Values written as **numbers**, nested under `extra.geoConfig` — not strings, not top level
- [ ] Panel appears on **`geoshape` only** — not `geo`, not `geotrace`, not any other type

---

## 3. Data Model Changes

**None.** `Questions.extra` is already a free-form `JSONField` (`models.py:148`), already
serialized to mobile, already round-tripped by the form builder.

---

## 4. API Contract

**No API change.** See GEO-010 for the tests proving the round trip.

---

## 5. Decision Log

### D-1: Extend `SettingGeo.jsx` upstream — do NOT use `QuestionCustomParams`

**Options Considered**:
1. Extend `SettingGeo.jsx` in `akvo-react-form-editor`
2. Host-supplied `customParams` (the editor's generic escape hatch — no upstream change)

**Decision**: Option 1.

**Rationale**: `SettingGeo.jsx` is already scoped to the geo types, already uses `InputNumber`,
and already authors a structured value (`center`). **`center` is the exact precedent**: authored
in `SettingGeo` → persisted by the backend → consumed by ARF `TypeGeoDrawing`.

`QuestionCustomParams` looks like a shortcut but is wrong on three counts:

| Limitation | Consequence |
|---|---|
| Writes to question **top level** (`{ ...q, [objKey]: value }`) | Produces `question.overlapThreshold`, not `extra.geoConfig.overlapThreshold` |
| **Always array-wraps**, and `type: 'input'` is a text field | `20` is stored as `["20"]` — a string in an array |
| **Not type-scoped** — a global "Custom Parameter" tab | Geo settings appear on text, number and date questions |

**Impact**: Requires an upstream PR and npm release. Option 2 remains the fallback if upstream
is blocked, at the cost of flat, array-wrapped, string-typed keys the app must unwrap.

### D-2: Question level, not form level

**Options Considered**:
1. `extra.geoConfig` on the question
2. A new `Forms.geo_config` field

**Decision**: Option 1 — question level.

**Rationale**: Form level was considered and rejected. It would require a new `Forms` field, a
migration, an addition to the **explicit** `WebFormDetailSerializer.Meta.fields` allowlist, and
a breaking change to ARF's published question-level contract. Question level costs none of those.

**Impact**: Two polygon questions in one form *could* differ. No use case requires it; this is a
consequence of the placement, not a feature.

### D-3: `geoshape` only

**Decision**: The panel does not appear on `geo` or `geotrace`.

**Rationale**: Consistent with the decision to scope all validation to `geoshape`.

**Impact**: A `geotrace` question carries no `geoConfig` and keeps ARF's built-in 15 m default.
Nothing regresses; geotrace gains no new configurability.

---

## 6. Type/Constant Mappings

| Editor | Backend | Mobile |
|---|---|---|
| `question.extra.geoConfig.*` | `Questions.extra` JSONField | read in validation module |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Absent `geoConfig` → client-side defaults apply, so an un-resynced device still validates
- [x] Existing forms unaffected

### Mobile App Impact
- [ ] SQLite schema changes: no
- [x] The mobile app must tolerate a **missing or malformed** `geoConfig` and fall back to
      defaults rather than disabling validation

### Upstream/Release
- [x] `akvo-react-form-editor` PR + version bump + npm release
- [x] `frontend/package.json` bump and round-trip verification

---

## 8. Security Considerations

- [x] No new permissions — form builders already author question config
- [ ] Reject out-of-range values (negative area, threshold outside 0–100) — see GEO-010

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit (upstream) | Each control writes the expected key, as a number, nested correctly |
| Unit (upstream) | Panel renders for `geoshape`, not for other types |
| Integration | Save → reopen → state restored |
| E2E | Author in builder → publish → value appears unchanged in the mobile payload |

**Hours breakdown**

| Unit | h |
|---|---|
| `SettingGeo`: 3 controls + conditional reveal | 1 |
| Store wiring, `geoshape`-only scoping | 0.5 |
| i18n keys in the editor | 0.5 |
| **Upstream build, test, version bump, npm release** *(process, not typing)* | 2 |
| Host integration + round-trip verification | 1 |
| **Total** | **5** |

---

## 10. Open Questions

- [ ] Is the upstream PR route available on the needed timeline? If blocked, D-1's fallback
      changes the config shape and adds an unwrapping shim in the app

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T8)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-5, FR-5.A, FR-5.B, D13)
- Upstream: `akvo-react-form-editor` `src/components/question-type/SettingGeo.jsx`
- Precedent: `akvo-react-form` #192 `extra.geoConfig.accuracyThreshold`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
