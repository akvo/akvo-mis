# Feature Design Document

## Feature: Local Geometry Index

**Task ID**: GEO-006 (breakdown ref: T3)
**Author**: Iwan Firmawan
**Date**: 2026-09-09
**Status**: Implemented — **note added 2026-09-18 (GEO-014)**; **substantially revised 2026-09-23**
(no backfill, `coordinates` dropped, index write coupled to the datapoint transaction, repeat
index added, file-based alternatives rejected — D-4 … D-8); open questions closed 2026-09-23
(`finishDatapointSync`, reset warning out of scope)
**Phase**: 3 — Overlap detection
**Estimate**: 7h ≈ 1 day (Mobile), plus 0.5h backend for the GEO-005 narrowing (§4) — was 8h
mobile before backfill was dropped
**Depends on**: GEO-005, GEO-014 · **Blocks**: GEO-007

> **🔴 The index must carry an accuracy summary, and two paths fill it differently.**
> GEO-007's threshold is derived from the accuracy of **both** polygons (GEO-014 D-5), and for a
> candidate that number can only come from here.
>
> ```mermaid
> flowchart LR
>     A["GEO-005 sync<br/>bbox + accuracy summary<br/>computed server-side"] -->|"store as given"| C[(geometry_index)]
>     B["Local create / local edit<br/>per-vertex accuracy in datapoints.json"] -->|"compute the summary"| C
>     C --> D[GEO-007 threshold]
> ```
>
> Both paths must produce **the same shape**. If the local path forgets to derive the summary
> — the natural omission, since it is busy computing a bbox — locally captured polygons index
> with `accuracyMeasured = 0`, GEO-007 falls back to the flat authored ceiling for exactly the
> plots the enumerator just walked, every query still works, and nothing reports an error.

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

The constraint that decides the shape of this table is **peak memory, not query time** (D-7).
A bbox range query returns 5–50 survivors, and only those are parsed. Peak allocation is
therefore constant in the size of the form, not linear in it.

---

## 2. Requirements

### Technical Acceptance Criteria
- [ ] One row per geoshape **answer**: `uuid`, `datapointId`, `formId`, `questionId`,
      `repeatIndex`, `name`, `minLat` / `maxLat` / `minLon` / `maxLon`, and the accuracy summary
      `accuracyMax` / `accuracyMeasured`
- [ ] **No `coordinates` column** (D-5). GEO-007 reads coordinates from `datapoints.json` for
      the 5–50 candidates that survive the bbox filter
- [ ] The summary is **stored as given** when it arrives from GEO-005, and **computed from
      per-vertex accuracy** on local create and local edit — the same shape either way
- [ ] A locally captured polygon indexes with `accuracyMeasured = 1`. A test must assert this;
      it is the failure that degrades GEO-007 silently
- [ ] **Single-column** indexes on each bbox column (see D-1)
- [ ] The index row is written **inside the same transaction as the datapoint row** (D-6), so
      `geometry_index` is always a subset of `datapoints` — never a row whose coordinates are
      not on the device
- [ ] Stays correct on: local create, local edit, sync arrival, re-sync of a changed datapoint
- [ ] **No backfill** (D-4). Existing installs upgrade by sync → reset
- [ ] GEO-007 must not validate against an index that predates the feature — readiness flag (D-4)
- [ ] `geometry_index` is truncated on reset, alongside the other tables
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
    repeatIndex: 'INTEGER DEFAULT 0',  // backend's `index`; renamed, see D-8
    name: 'VARCHAR(255)',          // for the FR-4.1 error message
    minLat: 'REAL', maxLat: 'REAL',
    minLon: 'REAL', maxLon: 'REAL',
    accuracyMax: 'REAL NULL',      // metres — GEO-014 D-10 summary
    accuracyMeasured: 'TINYINT DEFAULT 0',
    isComplete: 'TINYINT DEFAULT 0',
    createdAt: 'DATETIME',
  },
}
```

Identity of a row is `(uuid, formId, questionId, repeatIndex)`. A re-sync or a local edit
replaces by that key rather than inserting.

Rows are ~60 bytes. At the observed ceiling of 5,000 datapoints per form the whole table is
under 500 KB.

### Config Flag

```javascript
// added to the existing `config` table
geometryIndexReady: 'TINYINT DEFAULT 0',
```

See D-4.

### Migration Strategy

```
- Add table + 4 single-column bbox indexes
- Add config.geometryIndexReady, default 0
- NO backfill (D-4)
- Rollback: drop the table; overlap detection degrades to unavailable, capture still works
```

---

## 4. API Contract

**One narrowing to GEO-005** (which is already implemented): drop `geometry[].coordinates`
from `/device/datapoint-list`. `bbox` and `accuracy` stay — they are what this table stores.

This is a narrowing, not a revert. It is safe to make now because no shipped app version reads
the `geometry` field at all (`sync-datapoints.js` and `crud-datapoints.js` contain no reference
to it), and it removes a **duplicate** transfer: coordinates travel once in the list and again
in `{uuid}.json`. At 100 rows per page the page drops from roughly 430 KB to ~10 KB.

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

This is also why every "download a prebuilt file from the server" alternative fails: a
server-produced artefact cannot contain the datapoint the enumerator captured twenty minutes
ago, offline. See D-7.

### D-4: No backfill; upgrade by sync → reset, gated by a readiness flag

**Decision**: The migration creates the table and stops. Existing installs upgrade by syncing
their pending work, then resetting (Settings → Reset, which is the logout flow). The
re-download repopulates the index through the normal sync path.

**Rationale**: Backfill means parsing every stored datapoint on app start — a blocking
migration of unbounded duration on the one occasion a user is least tolerant of it. The reset
path already exists and already produces a clean device.

**The failure this opens, and the gate that closes it**: between the migration and the reset,
`geometry_index` is empty while `datapoints` is full. GEO-007 would query it, find no
candidates, and report **"no overlap"** for a plot that overlaps three existing ones. No error,
no warning. That is strictly worse than a backfill that fails loudly.

So the migration sets `config.geometryIndexReady = 0`; a completed full datapoint sync sets it
to `1`; GEO-007 refuses to validate while it is `0`, reusing the branch it must already have for
GEO-005's `complete: false`. Reset clears it back to `0` along with the rest of `config`.

**Two consequences that are easy to miss**:

1. `geometry_index` **must be added to the truncate list** in
   `app/src/components/LogoutButton.js` (a hardcoded array, not derived from `tables.js`). If it
   is not, the prescribed upgrade path wipes `datapoints` and leaves the index behind — phantom
   overlaps reported against datapoints that no longer exist.
2. Reset destroys locally created, unsynced datapoints. "Sync first" is the correct instruction
   but the confirmation dialog does not enforce it. This needs a release-note line at minimum;
   warning when unsynced work exists would be better, and is out of scope here.

### D-5: The index stores a bounding box, not coordinates

**Decision**: No `coordinates` column. GEO-007 fetches coordinates from the `datapoints.json`
column for the handful of candidates that survive the bbox filter:

```sql
SELECT json FROM datapoints WHERE id IN (…5–50 ids…)
```

**Rationale**: Storing coordinates in the index duplicates data the device already holds. At
180 vertices a polygon is ~4.3 KB of JSON text; at 5,000 per form that is ~21 MB duplicated,
and every row exceeds SQLite's per-page payload limit, so each row spills into overflow pages.
Without the column, rows are ~60 bytes and the whole table stays on ordinary leaf pages.

The cost is 5–50 `JSON.parse` calls at validation time — sub-millisecond each.

**Why this is safe only together with D-6**: if the index were filled from the list page while
`datapoints.json` arrived through a separate per-datapoint request, the two could diverge — an
index row whose coordinates are not on the device. GEO-007 would find a candidate it cannot
measure, and the natural implementation skips it silently. D-6 removes that possibility.

### D-6: The index row is written in the datapoint's transaction

**Decision**: The index write happens inside the existing `sql.withTransaction` block in
`app/src/lib/sync-datapoints.js`, beside the datapoint insert/update — not as a separate pass
over the list page.

**Rationale**: It makes `geometry_index ⊆ datapoints` an invariant rather than a hope. Commit
or roll back together; no crash window where one exists without the other.

It costs nothing extra at sync time. GEO-005 already ships `bbox` computed **server-side** in
the list response the device already fetches, so the page loop passes the geometry object
straight through into the transaction it was opening anyway: no extra HTTP request, no extra
pass, no on-device geometry maths.

Datapoints the sync skips as unchanged need no index write — their row was written in the
transaction that first stored them. Datapoints predating the feature are covered by D-4.

### D-7: No server-produced geometry file (GeoJSON, TopoJSON, or a `.sqlite` per form)

**Decision**: Rejected. The candidate set is queried from local SQLite.

**Rationale**: Three independent reasons, in order of weight.

1. **Peak memory is linear in the file, constant in the table.** turf has no I/O — every
   `@turf/*` function takes a plain JavaScript object, and there is no `turf.read()` or
   streaming equivalent. React Native has no Node streams, and `expo-file-system` hands back the
   whole file as one string. So a file must be `JSON.parse`d in full before any geometry maths
   can touch it. The cost is not the megabytes of text but the **array count**: 5,000 polygons ×
   180 vertices = 900,000 small `[lat, lng]` arrays, each a separate object with a ~40–60 byte
   header. Peak allocation lands in the 100–200 MB range, against a 128–256 MB process heap on a
   low-end Android device — an OOM, not a slowdown. The bbox query instead parses 5–50 polygons,
   which is the same cost whether the form holds 1,000 rows or 50,000.

   (`readAsStringAsync` does accept `position`/`length`, so partial reads are technically
   possible — but using them requires knowing each feature's byte offset, which means storing a
   table of offsets. That is an index, hand-rolled and unmaintained.)

2. **D-3.** A server file cannot contain unsynced local datapoints, so the local store is needed
   regardless. The file would be additional machinery, not a replacement.

3. **The download it optimises is already optimised.** GEO-005 is implemented and already
   delivers geometry, per form, with server-computed bboxes, inside the paginated list the
   device already fetches. A per-form file would be a second backend feature shipping the same
   bytes.

**On TopoJSON specifically**: its size advantage comes from shared arcs and quantization.
Independently GPS-walked plots never share arcs — two enumerators tracing a common boundary
produce two different vertex sets — so that half does not trigger. Quantization can be tuned
below GPS noise for a known extent, but it is a silent global knob feeding an overlap percentage
compared against a 5–20 % threshold. It would also add `topojson-client`; `@turf` ^7.4.0 reads
GeoJSON natively. If payload size is the concern, gzip on the existing endpoint gives more, for
nothing.

**Also rejected, same family**: a second SQLite database file. It moves the same pages to a
different file, and expo-sqlite's async calls already run off the JS thread so there is no
concurrency gain. Two connections cannot share a transaction with `datapoints` (breaking D-6);
`ATTACH` restores the join but returns to one connection, and SQLite does not guarantee atomic
commit across attached databases in WAL mode. Cascades get away with separate files because they
are read-only reference data with no transactional relationship to any local row. This table is
derived from `datapoints` and must not drift from it.

### D-8: `repeatIndex`, not `index`

**Decision**: The backend's `index` field is stored as `repeatIndex`.

**Rationale**: A datapoint can hold more than one geoshape answer — a second geoshape question,
or a geoshape inside a repeatable group. The backend already returns a **list** per datapoint
carrying both `question_id` and `index` (`v1_mobile/geometry.py`, and the field is a
`serializers.ListField` in `v1_mobile/views.py`). Without the repeat index, two instances of the
same question collide and the "one row per geoshape answer" criterion silently does not hold.

`index` is a SQLite keyword and would need quoting at every use site; `repeatIndex` avoids that
for the cost of one mapping.

This also rules out the cheaper shape that was considered and dropped: bbox columns added
directly to `datapoints` (following `05_add_locallyCreated`, `10_add_sendToWeb`), which needs no
new table, no second writer and no reset change — but affords only one bbox per datapoint.

---

## 6. Type/Constant Mappings

| Concept | Value |
|---|---|
| Indexed question type | `geoshape` only |
| Bbox source | GEO-005 response (sync), local computation (local create/edit) |
| Coordinate source at validation | `datapoints.json`, survivors only (D-5) |
| Readiness gate | `config.geometryIndexReady` — `0` blocks GEO-007 (D-4) |
| Row identity | `(uuid, formId, questionId, repeatIndex)` |

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing datapoints preserved — the index is derived, never authoritative
- [x] The index can be dropped and rebuilt at any time
- [ ] **Existing installs are not backfilled** (D-4) — they carry an empty index until reset,
      and GEO-007 is gated off for that period

### Mobile App Impact
- [x] **SQLite schema change: yes** — new table + `config.geometryIndexReady`, no backfill
- [x] Sync path modified to consume GEO-005 fields, inside the existing transaction
- [x] `LogoutButton.js` truncate list must gain `geometry_index`

### Backend Impact
- [x] GEO-005 narrowing: drop `geometry[].coordinates` (§4)

---

## 8. Security Considerations

- [x] No new data leaves the device
- [x] Index holds only what the device already stores

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Bbox computed correctly; index row created on local save |
| Unit | A locally captured polygon indexes with `accuracyMeasured = 1` |
| Unit | Two repeat instances of one geoshape question produce two rows, not one (D-8) |
| Integration | Edit a datapoint → index row updated, not duplicated |
| Integration | Sync arrival populates the index without a per-datapoint JSON fetch of its own |
| Integration | A rolled-back datapoint transaction leaves no index row (D-6) |
| Integration | `geometryIndexReady = 0` blocks validation rather than passing it (D-4) |
| Integration | Reset clears `geometry_index` — no rows survive into a fresh login (D-4) |
| Manual (device) | **Volume test**: query and storage at 1,000–5,000 polygons per form |

**Hours breakdown**

| Unit | h |
|---|---|
| Table + single-column bbox indexes in `tables.js` | 0.5 |
| Migration: table, indexes, `geometryIndexReady` — no backfill | 0.5 |
| CRUD module | 0.5 |
| Consume GEO-005's list fields inside the datapoint transaction | 1 |
| Keep index correct on local create / edit | 1 |
| Completeness + readiness gating | 0.75 |
| Add `geometry_index` to the reset truncate list | 0.25 |
| Unit tests | 1 |
| **Device testing at realistic volume** | 1.5 |
| **Total (mobile)** | **7** |

| Backend | h |
|---|---|
| Drop `geometry[].coordinates` from the list serializer + adjust the existing tests (§4) | 0.5 |

---

## 10. Open Questions

**Closed**

- ~~Where exactly does "a full datapoint sync completed" get signalled, so
  `geometryIndexReady` can be set at one place rather than several?~~ — **`finishDatapointSync(db)`**
  in `geometry-index-writer.js`, exported as `onDatapointSyncFinished` from `sync-datapoints.js`.
  Both call sites that today call `markSyncComplete()` (foreground `SyncService.js`, background
  `background-task.js`) call this helper instead. It (1) `POST /sync-complete`, (2) clears the
  sync queue, (3) sets `config.geometryIndexReady = 1` — readiness last, so a failed backend
  call leaves GEO-007 gated off. Re-setting `1` on later incremental syncs is idempotent; reset
  truncates `config` back to default `0`.

  > **Gating off is only safe if something later gates it back on — fixed 2026-09-23.**
  > Both call sites retired the sync job whether or not the finish step succeeded, and the
  > background one deleted it *first*. A failed `POST /sync-complete` therefore left the queue
  > complete, `geometryIndexReady` at `0`, and no job. The next run's quick-check sees a
  > complete queue and no new data, retires itself, and never reaches the finish step again —
  > overlap validation unavailable until a Reset, with only a Sentry line to say why.
  >
  > `completeDatapointSync(db, job)` in `sync-datapoints.js` now finishes *then* retires, and
  > throws instead of swallowing, so the caller keeps the job PENDING and `MAX_ATTEMPT` still
  > applies. The quick-check additionally asks `datapointSyncFinishPending(db)` before retiring
  > a job with nothing to download — a complete queue plus readiness `0` is exactly the
  > half-finished state, and is the only path back to it.
  >
  > The general shape is worth remembering: a flag that fails closed needs a retry path, or
  > "fails closed" becomes "fails permanently".
- ~~Should reset warn when unsynced datapoints exist?~~ — **Out of scope** for GEO-006. Release
  note only: "Sync pending submissions before Reset / logout." A confirmation that blocks reset
  when unsynced work exists can land separately.
- ~~Backfill duration on a low-end device with ~10,000 existing datapoints~~ — no backfill (D-4)
- ~~Storage per polygon at ~180 vertices~~ — coordinates are not stored in the index (D-5);
  rows are ~60 bytes. The question was really about peak memory, which D-7 settles
- ~~Datapoint volume per form~~ — observed ceiling is 1,000–5,000, which is what the volume test
  targets and what the D-7 memory arithmetic is based on

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
