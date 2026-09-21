# Feature Design Document

## Feature: `geoConfig` Persistence & API Tests

**Task ID**: GEO-010 (breakdown ref: T9)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Implemented — `backend/api/v1/v1_forms/tests/tests_geoconfig_persistence.py`
**Phase**: 3 — Overlap detection
**Estimate**: 2.5h ≈ 0.5 day (Backend)
**Depends on**: GEO-009

---

## 1. Context & Problem Statement

```
Currently:
- `Questions.extra` is a free-form JSONField already serialized to mobile, and
  FormDetailQuestionSerializer already lists `extra` among its fields.
- So geoConfig SHOULD round-trip with no model change — but nothing proves it does.

Goal:
- Prove that geoConfig survives create -> publish -> mobile fetch unchanged, and reject
  nonsensical values at the API boundary.
```

**The failure this guards against is silent.** If `extra` is filtered anywhere in the publish
path, mobile receives defaults, every threshold the designer set is ignored, and **nothing
reports an error**. The form looks configured and behaves as though it is not.

---

## 2. Requirements

### Technical Acceptance Criteria
- [x] `extra.geoConfig` survives form create → publish → mobile fetch, byte-identical
- [x] Out-of-range values rejected: negative area, threshold outside 0–100, non-numeric
- [x] `geoConfig` is carried into the `FormPublishedVersion` snapshot, not dropped
- [x] No model change required — **confirmed**: the persistence tests passed before any
      validation code existed, so the chain was already intact rather than assumed to be

---

## 3. Data Model Changes

**None.** Verified, not assumed — the round-trip tests were written first and passed
against unmodified code.

| Model | Field | Status |
|-------|-------|--------|
| `Questions` | `extra` (JSONField, `models.py:148`) | Exists, already serialized |
| `FormDetailQuestionSerializer` | lists `extra` | Exists |
| `WebFormDetailSerializer` | serves web **and** mobile | Exists |

No publish-path filtering was found. `extra` is carried verbatim by
`_build_schema_snapshot` (`functions.py:682`), `store_version_snapshot` and
`restore_from_snapshot` (`functions.py:549`), so no fix was needed.

---

## 4. API Contract

**No new endpoints.** Existing (the URLs below are the real ones — an earlier draft of
this section named `/api/v1/form`, which is read-only and never a write path):

| Method | URL | Assertion |
|--------|-----|-----------|
| POST | `/api/v1/manage/forms` | `extra.geoConfig` persisted as sent; nonsense rejected 400 |
| PUT | `/api/v1/manage/forms/{id}` | Same validation on edit, draft and published alike |
| POST | `/api/v1/manage/forms/{id}/publish` | `geoConfig` reaches the snapshot **and** back into live rows |
| GET | `/api/v1/manage/forms/{id}` | Builder sees the same values back |
| GET | `/api/v1/device/form/{id}` | `extra.geoConfig` present and unchanged |

**The device and the builder read different rows.** `/device/form/{id}` serializes live
`Questions` rows; a GET on a published form reads the active snapshot. A PUT on a published
form writes a *pending* snapshot only (FB-002B D-6), so until someone publishes, the builder
shows the new threshold and the device is still serving the old one. That is existing
behaviour for every question field, not a `geoConfig` bug, and there is now a test pinning it
so it stays deliberate.

---

## 5. Decision Log

### D-1: Validate at the API boundary, not only in the builder UI

**Decision**: Reject nonsensical `geoConfig` values server-side.

**Rationale**: The builder UI is one client. Form JSON can also arrive via import or a direct API
call, and a threshold of `-5` or `500` would silently produce nonsense validation on device.

### D-2: Malformed config falls back to defaults, it does not disable validation

**Decision**: A bad value means "use the default", never "skip the check".

**Rationale**: Failing open is the worst outcome for a validation feature — it looks like it
worked. This is enforced on the device too, but the API should not have let it through.

### D-3: An explicit `null` means "not set", not "invalid"

**Decision**: `{"overlapThreshold": null}` is accepted and stored; `"20"`, `-5` and `101` are
rejected.

**Rationale**: `null` is how the builder spells an unset value, and every other nullable
question field on the model behaves that way. Rejecting it would refuse payloads the editor
legitimately produces, while the values D-1 is actually aimed at — a string, a negative, an
out-of-range percentage — all still fail. An absent key and a null key mean the same thing:
use the default.

### D-4: Validation covers the JSON import boundary too

**Decision**: The same rules run in `validate_form_definition` (`functions.py`), blocking an
import with `level: "error"` and code `invalid_geo_config`.

**Rationale**: D-1's own rationale names import as a way form JSON arrives. It reaches the
same rows through a different validator, so leaving it out would have left the hole D-1
describes half-open. XLSForm import needs nothing: its converter has no way to express
`geoConfig`, so none can arrive that way.

---

## 6. Type/Constant Mappings

| Key | Type | Valid range |
|---|---|---|
| `accuracyThreshold` | number | > 0 |
| `detectOverlaps` | boolean | — |
| `overlapThreshold` | number | 0 < x ≤ 100 |
| `overlapThresholdFloor` | number | 0 < x ≤ 100 — added 2026-09-18, GEO-014 D-8 |
| `allowTapping` | boolean | — default `true`; added 2026-09-21, GEO-014 D-4 |

> **Note, 2026-09-21 (GEO-014 D-4).** `allowTapping` joins the namespace as a boolean. Validate
> it exactly as `detectOverlaps` is validated — against the real booleans, not for truthiness.
> The same argument applies: a `"false"` string would read as *enabled* to a naive check and as
> *disabled* to nobody, which is the silent mismatch these tests exist to catch.
>
> **Note, 2026-09-18 (GEO-014).** One key is **added** to the namespace —
> `overlapThresholdFloor`, number, `0 < x ≤ 100`, default `5` (GEO-014 D-8). It follows the same
> rule as `overlapThreshold`, so `_geo_config_issues()` should validate it identically and the
> parametrised rejection cases here extend to cover it. Everything else below is unchanged.
>
> The remaining changes are downstream meaning only, with no code or range impact:
> `overlapThreshold` is now the *ceiling* of an accuracy-derived threshold (GEO-014 D-5) rather
> than the threshold itself. (An earlier version of this note also said `detectOverlaps` disables
> tap-to-draw; that coupling was removed on 2026-09-21 — see the note above.) Neither affects
> what this document validates.
>
> A separate change **does** touch the write boundary this document is about, in a different
> serializer: `is_coordinate_ring()` (`v1_data/serializers.py:75`) must accept a third,
> optional element on each vertex. That guards *answers*, not `geoConfig`, so it belongs with
> GEO-014 §4 — but it is worth knowing the two live next door to each other.

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing forms with no `geoConfig` unaffected
- [x] Existing API consumers unaffected — validation only tightens a previously free-form subkey

### Mobile App Impact
- [ ] Sync endpoints affected: none structurally
- [x] Mobile relies on this to trust the values it reads

---

## 8. Security Considerations

- [x] Input validation added at a previously unvalidated boundary — a small improvement
- [x] No permission change: authoring config already requires form-edit rights

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Integration | Create form with `geoConfig` → fetch → identical |
| Integration | **Publish → fetch published version → `geoConfig` still present** (the silent-failure guard) |
| Integration | Mobile form endpoint returns `geoConfig` unchanged |
| Unit | Rejects negative area, threshold 0 / 101 / `"20"` |

**Hours breakdown**

| Unit | h |
|---|---|
| Round-trip tests: create → publish → mobile fetch | 1 |
| Reject nonsensical values | 0.5 |
| Verify `extra` survives the `FormPublishedVersion` snapshot | 1 |
| **Total** | **2.5** |

**The test that matters most** is not in the original list: publishing a pending snapshot
copies it back over the live rows, and `enabled_geoshape_question_ids`
(`v1_mobile/geometry.py`) reads those rows to decide which questions get overlap detection at
all. A `geoConfig` lost there would switch the feature off for every published form with no
error anywhere, so that assertion runs through the gate function rather than comparing dicts.

---

## 10. Open Questions

- [x] Does form **import** preserve `extra.geoConfig`? Answered. JSON import (FB-007) does
      preserve it and now validates it (D-4). XLSForm import (FB-016) cannot carry a
      `geoConfig` in either direction — there is no cell for it — so round-tripping one
      through XLSForm remains a genuine follow-up if it is ever wanted.

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T9)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-5)
- Related: `doc/design/FB-002B-form-builder-version-schema.md`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
