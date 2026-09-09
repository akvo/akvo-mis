# Feature Design Document

## Feature: Local Geometry Index

**Task ID**: GEO-006 (breakdown ref: T3)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Draft
**Phase**: 3 — Overlap detection
**Estimate**: 8h ≈ 1 day (Mobile)
**Depends on**: GEO-005 · **Blocks**: GEO-007

---

## 1. Context & Problem Statement

```
Currently:
- Datapoint answers live in datapoints.json as a {questionId: answer} blob.
- Finding overlap candidates would mean parsing EVERY datapoint's JSON at validation time.

Goal:
- A queryable spatial index: one row per polygon answer, with indexed bounding-box columns,
  so candidate lookup is an indexed range query rather than a full parse.
```

---

## 2. Requirements

### Technical Acceptance Criteria
- [ ] One row per geoshape answer: `uuid`, `datapointId`, `formId`, `questionId`, `name`,
      coordinates, and `minLat` / `maxLat` / `minLon` / `maxLon`
- [ ] **Single-column** indexes on each bbox column (see D-1)
- [ ] Stays correct on: local create, local edit, sync arrival, re-sync of a changed datapoint
- [ ] Existing installs backfilled on migration
- [ ] Forms with no geoshape question do **no** indexing work
- [ ] Tracks whether the candidate set is complete (from GEO-005's signal)

---

## 3. Data Model Changes

### New SQLite Table

```javascript
// app/src/database/tables.js
{
  name: 'geometry_index',
  fields: {
    id: 'INTEGER PRIMARY KEY AUTOINCREMENT',
    uuid: 'VARCHAR(191)',          // datapoint uuid
    datapointId: 'INTEGER',
    formId: 'INTEGER NOT NULL',
    questionId: 'INTEGER NOT NULL',
    name: 'VARCHAR(255)',          // for the FR-4.1 error message
    coordinates: 'TEXT',           // JSON [[lat,lng],…]
    minLat: 'REAL', maxLat: 'REAL',
    minLon: 'REAL', maxLon: 'REAL',
    isComplete: 'TINYINT DEFAULT 0',
    createdAt: 'DATETIME',
  },
}
```

### Migration Strategy

```
- Add table + 4 single-column indexes
- Backfill: scan existing datapoints for geoshape answers, compute bbox locally ONCE
- Backfill is the one place on-device parsing is unavoidable; it runs once, not per validation
- Rollback: drop the table; overlap detection degrades to unavailable, capture still works
```

---

## 4. API Contract

**No API change.** Consumes GEO-005's extended list response.

---

## 5. Decision Log

### D-1: Single-column bbox indexes, not a composite

**Decision**: Four separate single-column indexes.

**Rationale**: Taken from the reference validator's `PlotEntity` comment: *"Single-column bbox
indexes allow SQLite to choose the most selective index for range conditions. **Composite
indexes are ineffective for range-only queries.**"* A composite index across the four columns
will not be used by the planner.

### D-2: Drop the reference validator's draft-lifecycle machinery

**Decision**: No `isDraft`, no `instanceName`, no `submissionUuid` matching.

**Rationale**: The reference validator needs that lifecycle because it is a **separate app** and
cannot see the host platform's submissions. Our `datapoints` table already holds local **and**
synced records offline, so both source scenarios collapse into one query. Porting the lifecycle
would be dead weight.

### D-3: Two writers, one table

**Decision**: The index is written by both the sync path and the local create/edit path.

**Rationale**: This is what makes a locally-created, never-synced datapoint a valid overlap
candidate — the requirement that the reference validator solved with its draft table.

---

## 6. Type/Constant Mappings

| Concept | Value |
|---|---|
| Indexed question type | `geoshape` only |
| Bbox source | GEO-005 response (preferred), local computation (backfill + local edits) |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing datapoints preserved — the index is derived, never authoritative
- [x] The index can be dropped and rebuilt at any time

### Mobile App Impact
- [x] **SQLite schema change: yes** — new table + migration + backfill
- [x] Sync path modified to consume GEO-005 fields

---

## 8. Security Considerations

- [x] No new data leaves the device
- [x] Index holds only what the device already stores

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Bbox computed correctly; index row created on local save |
| Integration | Edit a datapoint → index row updated, not duplicated |
| Integration | Sync arrival populates the index without a per-datapoint JSON fetch |
| Manual (device) | **Volume test**: backfill duration and storage at realistic polygon sizes |

**Hours breakdown**

| Unit | h |
|---|---|
| Table + single-column bbox indexes in `tables.js` | 0.5 |
| Migration + backfill for existing installs | 1.5 |
| CRUD module | 0.5 |
| Consume GEO-005's list fields during sync | 1 |
| Keep index correct on local create / edit | 1 |
| Completeness tracking | 0.5 |
| Unit tests | 1 |
| **Device testing at realistic volume** | 2 |
| **Total** | **8** |

---

## 10. Open Questions

- [ ] Backfill duration on a low-end device with ~10,000 existing datapoints — measure before
      shipping; a slow blocking migration on app start is a bad first impression
- [ ] Storage per polygon at ~180 vertices (GPS capture makes this routine)

---

## 11. References

- Task breakdown: `doc/claude/polygon-validation-task-breakdown.md` (T3)
- Requirements: `doc/claude/offline-polygon-validation-requirements.md` (FR-7)
- Reference: `akvo/african-bamboo-odk-external-validations` → `data/entity/PlotEntity.kt`, `data/dao/PlotDao.kt`

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
