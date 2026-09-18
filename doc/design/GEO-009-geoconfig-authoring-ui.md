# Feature Design Document

## Feature: `geoConfig` Authoring UI

**Task ID**: GEO-009 (breakdown ref: T8)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Delivered — panel merged upstream (akvo/akvo-react-form-editor#76) and released as 2.0.5; host depends on it
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

> **Correction, 2026-09-18 (GEO-014).** The panel is unchanged and needs no further upstream
> release, but two of these keys now mean more than they did when it shipped.
>
> | Key | Meaning at release | Meaning now |
> |---|---|---|
> | `overlapThreshold` | the overlap ratio tolerated | the **most** overlap ever tolerated — a ceiling on a threshold derived from GPS accuracy (GEO-014 D-5) |
> | `accuracyThreshold` | fixes worse than this are discarded at capture | fixes worse than this are **recorded and marked red**, and from phase 3 block submission (GEO-014 D-3, D-6) |
> | `detectOverlaps` | enables the overlap check | additionally **disables tap-to-draw on mobile** (GEO-014 D-4) |
>
> Nothing about the fields, their types, defaults or validation ranges changes, so no programme's
> saved configuration changes meaning in a way that loosens anything: as a ceiling,
> `overlapThreshold` can only ever make detection *stricter* than it was.
>
> `detectOverlaps` growing a second effect is the one place this is arguably under-communicated
> — the checkbox label says nothing about drawing. Adding that to the help text is an upstream
> release for one string, and the app enforces it regardless.
>
> **Decided 2026-09-18: deferred, and this panel is not touched.** Recorded as known debt rather
> than an oversight, so nobody re-discovers it as a bug.
>
> One further key joins the "read but not authored" list that the 2026-09-17 correction above
> describes: **`overlapThresholdFloor`** (default `5`, GEO-014 D-8), the lower bound of the
> adaptive overlap threshold. It follows exactly the precedent set by `validateShape`,
> `validateArea` and `maxAreaHa` — free to read, an upstream release to author, and no programme
> needs to set it to get sensible behaviour. **The three-field contract this document specifies
> therefore still stands as a description of the UI.**

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

> **Correction, 2026-09-17.** Half of that is still true; half is not. `minPoints` and
> `minAreaSqm` remain unconfigurable at every layer. But `validateShape` and `validateArea`
> now exist as **severity** keys, not enable keys — see GEO-002 D-4. When present they decide
> whether a failed rule *blocks* submission or merely *warns*; the rule runs and reports either
> way, so the "no meaningful off state" argument is unaffected. The mobile app reads them from
> phase 1; a third key, `maxAreaHa` (GEO-003 D-5), is an opt-in upper bound read the same way.
> **This panel authors none of them** (GEO-002 D-5 — the key costs nothing to read and
> an upstream release to author, and no programme has asked yet). The three-field contract this
> document specifies is therefore unchanged, and stays accurate as a description of the UI.

### User Acceptance Criteria
- [x] `overlapThreshold` is revealed only when `detectOverlaps` is ticked
- [x] The overlap checkbox carries help text stating the consequence: *enabling this syncs the
      geometry of all other responses to this question onto the enumerator's device* — shipped as
      always-visible warning text rather than a tooltip, and asserted by a test on the string
      itself, not merely on the key existing
- [x] Reopening the form restores checkbox and numeric state
- [x] Values survive publish and appear unchanged in the mobile form payload

### Design-review addition: resolved as three fields

The conflict below was resolved on 2026-09-14 in favour of the three-field
reading. Shape validity, the 3-vertex minimum and the 10 m² floor stay
fixed constants in the mobile code, per GEO-002 D-1 and GEO-003 D-2 as
approved. There is no rule dropdown and no off switch.

**This does not deliver the design-review request** for selectable rules
added one at a time. GEO-002 D-1 and GEO-003 D-2 both instruct that such a
narrowing be flagged to the requester rather than passed off as
delivered-as-asked. That instruction applies here: the request was
understood, considered, and deliberately not built, because it would double
the panel and let a form ship with polygon validation disabled.

**Consequence for GEO-007.** Its acceptance criterion that the Validate
button is hidden "when the question has no validation rules configured"
cannot be satisfied by anything this task writes. A plain geoshape question
still carries all four FR-5.B floors; they are simply not authored.
GEO-007 must decide what gates that button.

### Prerequisite this document originally missed

`geoshape` was absent from `frontend/src/lib/constants.js` `QUESTION_TYPES`,
and both form-builder pages pass that object to the editor as
`limitQuestionType`. No `geoshape` question could be created in Akvo MIS, so
the panel was unreachable regardless of the upstream work. GEO-009 found
this; the type itself was added on the epic branch under #383, so it is no
longer part of this task's diff.

### Technical Acceptance Criteria
- [x] Values written as **numbers**, nested under `extra.geoConfig` — not strings, not top level
- [x] Panel appears on **`geoshape` only** — not `geo`, not `geotrace`, not any other type

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
- [x] `akvo-react-form-editor` PR + version bump + npm release — PR #76 merged; released as **2.0.5**, a patch rather than the 2.1.0 anticipated here, since the panel is additive
- [x] `frontend/package.json` bump and round-trip verification — both done: round trip verified against a running stack, and the host now depends on `^2.0.5`

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

- [x] The upstream route was available. D-1's fallback was not needed, and
      the config shape is the nested, numeric one this document specifies.
      PR #76 was squash-merged and released as 2.0.5.
- [x] A fix landed upstream after the panel merged: the geo inputs became
      controlled components rather than relying on `Form.Item initialValue`,
      which only applies on first render and left the fields blank when a
      question's `geoConfig` arrived after mount. Worth knowing because it
      is the mechanism behind the "reopening the form restores state"
      criterion in section 2.
- [ ] Nothing verifies `geoConfig` end to end on the backend yet. GEO-010.

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
