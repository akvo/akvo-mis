# Feature Design Document

## Feature: Extend the Datapoint List with Geometry & Bounding Box

**Task ID**: GEO-005 (breakdown ref: T2)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: **Implemented** — `geometry_answers` / `bounding_box` / `geometry_by_data_id` in
`v1_mobile/geometry.py`, 25 tests in `tests_mobile_datapoint_geometry.py`. Revised 2026-09-18 by
GEO-014; the per-polygon accuracy summary (D-10) is the one part **not yet built**

> **Status corrected 2026-09-21.** This still read "Draft" long after the endpoint shipped. The
> stale line was found by cross-checking each GEO document's header against the code rather than
> against the other documents — worth repeating, because a "Draft" that is really delivered is
> the one kind of staleness no reader questions.
**Phase**: 3 — Overlap detection
**Estimate**: 6h ≈ 1 day (Backend)
**Blocks**: GEO-006
**Reads**: GEO-014 — this payload is the only route by which a *candidate* polygon's accuracy
reaches the device, which is why accuracy has to be stored at all

---

## 1. Context & Problem Statement

```
Currently:
- /device/datapoint-list returns metadata only: id, form_id, name, administration_id, url,
  last_updated. No answers.
- The device then fetches {WEBDOMAIN}/datapoints/{uuid}.json PER DATAPOINT for the full
  answer set (sync-datapoints.js:158).
- So the geometry DOES already reach the device — and a skip-unchanged guard
  (sync-datapoints.js:150-155) means only the FIRST sync costs one request per datapoint.

Goal:
- Give the device the geometry and a precomputed bounding box directly on the list response,
  plus a signal telling it whether it holds the COMPLETE candidate set.
```

**Bandwidth is not the argument.** The three real concerns are below.

---

## 2. Requirements

### The case for this task

| # | Concern | Severity |
|---|---|---|
| 1 | **Partial sync yields false passes.** `datapoint_sync_queue` carries `lastPage`/`totalPage` — sync is resumable, so partially-synced states are normal. A 60 %-synced form checks against 60 % of candidates and reports *no overlap*. A missing candidate does not error, it **passes** | 🔴 Correctness |
| 2 | **No bbox means parsing every polygon on-device.** GEO-006 would parse ~180-vertex polygons across every datapoint on a low-end Android phone just to index them | 🟠 Performance |
| 3 | **`detectOverlaps` would control nothing.** Datapoints sync regardless, so the checkbox could not honour "sync the least possible" | 🟡 Requirement |

Concern 1 is the reason this task exists: **a validation feature that silently passes is worse
than one that errors.**

### Technical Acceptance Criteria
- [x] With `detectOverlaps` off, the response is **byte-identical to today**
- [ ] With it on, the device builds GEO-006's index **without fetching any per-datapoint JSON**
      and without parsing coordinates to derive bboxes
- [x] The device can distinguish a complete candidate set from a partial one
- [x] Existing pagination (`page_size=100` max) and `last_updated` cursor reused — no second
      sync loop on the device
- [x] Tenant and mobile-assignment scoping unchanged

> Two criteria above stay unticked on purpose. The **device** half — building GEO-006's index
> from this payload — belongs to GEO-006, which is unbuilt; and the accuracy summary added by
> GEO-014 D-10 is specified here but not yet served.

---

## 3. Data Model Changes

### Modified Models

| Model | Change | Reason |
|-------|--------|--------|
| `Answers` or a denormalised column | Store bbox per geoshape answer *(decision pending — see D-2)* | Avoid recomputing bbox for every request |

### Migration Strategy

```python
# If bbox is denormalised:
# - Backfill existing geoshape answers with computed bboxes
# - Null bbox is valid: means "not yet computed", device falls back to parsing
# - Rollback: drop the columns; the device path still works, more slowly
```

---

## 4. API Contract

### Endpoints

| Method | URL | Purpose | Auth |
|--------|-----|---------|------|
| GET | `/api/v1/device/datapoint-list` | **Extended**, not replaced | Required |

### Response Example

```json
// GET /device/datapoint-list?form_id=123&page=1
// Row for a form WITH detectOverlaps enabled:
{
  "id": 1,
  "form_id": 123,
  "name": "Abebe Kebede Tadesse",
  "administration_id": 45,
  "url": "https://.../datapoints/uuid.json",
  "last_updated": "2026-09-01T10:00:00Z",

  "geometry": {
    "question_id": 987,
    "coordinates": [[9.03, 38.74], [9.04, 38.74], [9.04, 38.75]],
    "bbox": { "min_lat": 9.03, "max_lat": 9.04, "min_lon": 38.74, "max_lon": 38.75 },
    "accuracy": { "max": 6.8, "measured": true }
  }
}

// Row for a form WITHOUT the flag — unchanged, no `geometry` key at all
```

**Coordinates on this endpoint are sent as two-element vertices**, and accuracy travels as a
**per-polygon summary** instead (GEO-014 D-10). GEO-007's adaptive threshold consumes
`accA + accB`, where `accA` is one number per polygon — so a candidate's 180 per-vertex readings
would be data no consumer on this path reads. The summary costs ~30 bytes per polygon where
per-vertex accuracy would cost ~720.

`measured: false` means the polygon was never GPS-measured — a webform answer, or a row captured
before GEO-014. The device then falls back to the authored `overlapThreshold` (GEO-007 D-3).

Per-vertex accuracy is **still stored** and still travels on `/sync`; only this list summarises.

⚠️ `bounding_box()` at `v1_mobile/geometry.py:58` unpacks `zip(*coordinates)` into two names and
raises `ValueError` on a three-element vertex. It reads **stored** rows, which do carry three
elements, so it must be fixed regardless of what this endpoint emits (GEO-014 §4, D-7).

**Completeness signal** — returned alongside pagination so the device can gate validation:

```json
{ "current": 3, "total_page": 3, "total": 287, "complete": true }
```

---

## 5. Decision Log

### D-1: Extend the existing endpoint, do not add a new one

**Options Considered**:
1. New geometry-only endpoint
2. Extend `/device/datapoint-list`
3. Reuse the status quo, parse bboxes on-device, add a completeness check

**Decision**: Option 2.

**Rationale**: The list endpoint is already paginated at 100 and already fetched on every sync.
Adding a few fields to it is far less work than a parallel endpoint and a second sync loop, and
it lets `detectOverlaps` genuinely control payload. Option 3 is cheaper (~1h) but leaves the
on-device parsing cost and makes the checkbox meaningless.

**Impact**: Dropped this task from 3 days to 1.

### D-2: Bbox computed on write or per request?

**Decision**: **Open.** Measure before choosing.

**Rationale**: At 100 rows per page, per-request computation may be acceptable. Denormalising
costs a migration and a backfill. This should be decided with a measurement, not a preference.

### D-3: Do not widen data access

**Decision**: Reuse existing mobile-assignment and tenant scoping exactly.

**Rationale**: A new bulk field is an easy place to leak datapoints across tenants. An
enumerator must receive geometry only for datapoints they could already see.

---

## 6. Type/Constant Mappings

| Concept | Source |
|---|---|
| Gate | `Questions.extra.geoConfig.detectOverlaps === true` |
| Question type filter | `QuestionTypes.geoshape` (14) |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Additive fields only — older app builds ignore unknown keys
- [x] Forms without the flag see an unchanged response
- [x] Existing API consumers unaffected

### Mobile App Impact
- [x] Sync endpoints affected: `/device/datapoint-list`
- [ ] SQLite schema changes: none here — see GEO-006
- [x] Version detection: not needed; the device uses the fields if present

---

## 8. Security Considerations

- [x] Permission model unchanged — reuses existing assignment/tenant scoping
- [ ] **Tests must cover cross-tenant and cross-assignment isolation** for the new fields
- [x] No new attack vectors: same authentication, same queryset, more columns

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Bbox computation for known polygons — including 3-element and mixed-length vertices |
| Unit | Accuracy summary: `measured: false` when no vertex carries a reading; `max` over a mixed ring ignores the unmeasured ones |
| Integration | A legacy 2-element answer and a 3-element one appear side by side, both with a correct summary |
| Integration | Flag off → byte-identical response; flag on → geometry present |
| Integration | **Tenant/assignment scoping** — an enumerator cannot see another tenant's geometry |
| Integration | Pagination and `last_updated` cursor still behave |

**Hours breakdown**

| Unit | h |
|---|---|
| Serializer: geometry + bbox fields on the list response | 0.5 |
| Server-side bbox computation | 1 |
| Per-polygon accuracy summary (GEO-014 D-10) | 0.5 |
| Gate on `extra.geoConfig.detectOverlaps` | 0.5 |
| Completeness signal | 1 |
| Tests — tenant scoping, gating on/off, pagination | 1.5 |
| Migration, if bbox is denormalised | 1 |
| **Total** | **6** |

---

## 10. Open Questions

- [ ] D-2: bbox denormalised on write, or computed per request?
- [ ] Payload growth with ~180-vertex polygons — if pages get large, send bbox only in the list
      and fetch full coordinates lazily for the few candidates a bbox query returns.
      **Largely defused 2026-09-18 by GEO-014 D-10**: accuracy is summarised per polygon rather
      than per vertex, so this endpoint grows by ~30 bytes per row instead of ~720. The original
      concern — that ~180-vertex coordinate lists are big on their own — is unchanged, and the
      lazy-fetch option above remains the lever for it
- [ ] Which statistic the `accuracy` summary carries. `max` is conservative, but one bad vertex
      on an otherwise well-walked boundary dominates it and tightens the threshold for the whole
      polygon. Mean under-reports the opposite way. Decide with field data (GEO-014 §10)
- [ ] ⚠️ **The completeness signal is the piece most likely to be dropped as "nice to have".
      It is the reason this task exists.**

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T2)
- Current sync: `app/src/lib/sync-datapoints.js:126-175`
- Current serializer: `backend/api/v1/v1_mobile/serializers.py:23`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
