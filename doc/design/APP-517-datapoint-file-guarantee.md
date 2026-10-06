# Feature Design Document

## Feature: Every Listed Datapoint Has a Current File

**Task ID**: APP-517
**Author**: Iwan Firmawan
**Date**: 2026-10-06
**Status**: Approved and implemented 2026-10-06, not yet deployed. Backend suite green on this
branch (2545 tests). Not yet run: the §9 manual checks, including the nginx `404`, which the
local dev server does not exercise
**Follows**: APP-407 §7, the server-side fix it deferred
**Related**: GEO-006 D-4 (amended 2026-10-06), GEO-007 D-10

---

## 1. Context & Problem Statement

The mobile app never reads answers from the API. It lists datapoints through
`/api/v1/device/datapoint-list`, then downloads each one's answers from
`{WEBDOMAIN}/datapoints/<uuid>.json`. If that file is missing or stale, the device cannot get
the datapoint.

```
Currently:
- The file is written only by the Django-Q task `seed_approved_data`, on the worker.
  The datapoint is listed to devices the moment its row commits, whether the task
  has run or not.
- A task that raises is recorded as failed and never re-run. Django-Q's `retry`
  re-queues only tasks a worker never acknowledged. A worker outage, a full disk or
  one bad answer leaves the datapoint listed with no file, permanently.
- The Excel bulk upload never writes the file. A superadmin upload that updates an
  existing datapoint leaves its old file in place, now stale.
- A missing file is served as `200 text/html` (nginx's SPA fallback). Nothing
  notices it.
- Regenerating files (`generate_data_json`) does not reach devices that already
  synced: the listing's cursor compares `created` / `updated`, and regenerating a
  file changes neither.

Goal:
- A datapoint is listed to devices only once its file exists and matches it.
- A file that fails to write is rewritten automatically, without an operator.
- A rewritten file reaches devices on their next ordinary sync.
- A file nobody needs any more (its datapoint was deleted) is removed.
- A file that is not there answers 404, not a web page with 200.
```

**Why it matters now.** On 2026-10-06, overlap validation (GEO-007) stayed unavailable on a
real device after Retry sync, while the emulator worked. The datapoint files on the test server
were missing or stale. Running `generate_data_json` let the **unchanged** app build validate.
The app now limits how far one bad file reaches (GEO-006 D-4, amended 2026-10-06), but only the
server can stop the files going missing.

---

## 2. Requirements

### User Acceptance Criteria
- [x] A datapoint submitted while the worker is down can be downloaded to devices as soon as it
      is saved
- [x] A datapoint created or updated by the Excel bulk upload can be downloaded to devices
- [x] After a file is rewritten, a device downloads the new copy on its next sync, without Reset
      or a full re-pull
- [x] Nobody has to remember to run `generate_data_json`

### Technical Acceptance Criteria
- [x] One method, `DatapointFile.write_file()`, is the only code that writes a datapoint file.
      Every publication path in §7 calls it
- [x] `FormData.file_generated_at` is set when that file is written, and only then
- [x] The device listing omits registration datapoints whose file is missing or older than the
      row (D-2)
- [x] The listing's cursor and `last_updated` take `file_generated_at` into account (D-5)
- [x] `geometry_total` is **not** filtered by file state (D-3)
- [x] An hourly scheduled task rewrites every file that is missing, including missing from
      disk while the row says it was written, or stale (D-4)
- [x] The same task deletes files whose datapoint no longer exists or is deleted, and clears
      the stamp of a soft-deleted row it removes a file for (D-7)
- [x] `GET /datapoints/<uuid>.json` for a file that is not on disk answers `404` (D-6)
- [x] A failed file write never fails the submission that triggered it

---

## 3. Data Model Changes

### Modified Models

| Model | Change | Reason |
|-------|--------|--------|
| `FormData` | Add `file_generated_at = DateTimeField(null=True)`, through the `DatapointFile` mixin (D-1). No index: the listing compares it with other columns and the reconciler reads every published row, so no query could use one | Records when this row's file was last written. `NULL` = never written. Older than `updated` = stale |

Monitoring (child) datapoints never get a file (`FormData.needs_file()` is false when
`form.parent` is set, and `FILE_EXEMPT` says the same to the listing), so their stamp stays
`NULL`, and nothing in this design reads it for them.

### Migration Strategy

```python
# 1. AddField, nullable, no default. Every existing row starts NULL ("not written").
# 2. No data migration: a migration must not touch the filesystem.
# 3. Backfill = the reconciler (D-4), run once at startup by run-prod.sh and then
#    hourly. Until it reaches a row, that row is hidden from the device listing.
#    Hiding is safe because the stamp is part of the cursor (D-5): when the file is
#    written, the row is listed again on the next sync.
# Rollback: drop the column, revert run-prod.sh. The files written in the meantime
# are the same files the old code writes.
```

---

## 4. API Contract

**No new endpoints.** `GET /api/v1/device/datapoint-list` changes in four ways; request and
response shapes are unchanged:

| Aspect | Today | After |
|---|---|---|
| Rows listed | Every published row | Registration rows with `file_generated_at >= COALESCE(updated, created)`, and every monitoring row (D-2) |
| Cursor (`last_synced_at`) | `created >= c OR updated >= c` | `... OR file_generated_at >= c` (D-5) |
| `last_updated` per row | `updated` or `created` | `max(updated or created, file_generated_at)` (D-5) |
| `geometry_total` | All published rows | **Unchanged**: all published rows (D-3) |

And one change outside the API, in nginx:

| Request | Today | After |
|---|---|---|
| `GET /datapoints/<uuid>.json`, file absent | `200 text/html` (the web app's `index.html`) | `404` (D-6) |

---

## 5. Decision Log

### D-1: Write the file in the request, on commit; keep only the view refresh async

**Options Considered**:
1. Keep the worker task, add retries
2. Write the file in the request, after the transaction commits

**Decision**: Option 2. The file is modelled the way `utils/draft_model.py` models drafts
*(restructured 2026-10-06; it first shipped as free functions)*:

- `utils/datapoint_file_model.py` holds the abstract `DatapointFile` model: the
  `file_generated_at` field, and `write_file()`, the only code that writes a file. It writes,
  stamps the row and never raises. The model supplies the JSON through `file_payload()` and says
  which rows get no file through `needs_file()` and `FILE_EXEMPT`. `DatapointFileQuerySetMixin`
  adds a chainable `downloadable()` for the device listing (D-2), and
  `DatapointFileManagerMixin` exposes it on the manager, the way `Draft` delegates `published()`.
  `DraftSoftDeletesManager` gained a `queryset_class` attribute so `FormData` can supply the
  combined queryset.
- `FormData(SoftDeletes, Draft, DatapointFile)` supplies the payload (what `save_to_file` used
  to build) and adds `finalize()`: `write_file` through `transaction.on_commit`, then
  `seed_approved_data` queued as the paths did before. `finalize()` stays on `FormData` because
  the task it queues is `v1_data`'s.
- `save_to_file` is gone. A public raw write beside `write_file()` would let a caller write a
  file without stamping it, and the listing would then hide that row.
- The reconcile is `reconcile_datapoint_files()` in `api/v1/v1_data/tasks.py`, beside
  `seed_approved_data`: it is a worker task, scheduled hourly. It is a batch job that touches the
  filesystem, not a query, so it does not belong on a manager.

**Amended during implementation (2026-10-06): `seed_approved_data` stays queued.** Besides the
view refresh, it sets `updated` on new submissions, which the web app shows as "updated at".
Dropping it would have been a visible change. It now rewrites the file through
`write_file()` **after** it moves `updated`, so the stamp stays current. If the worker
is down, the file written in the request still stands. Only `updated` and the view refresh wait
for the worker, and neither hides the datapoint from devices.

The stamp is the time captured **before** the answers are read. An edit that commits while the
file is being written then carries a later `updated`, so the row reads as stale and the
reconciler rewrites it. Stamping after the write would mark that file current.

The Excel bulk upload and the seeders call `write_file()` directly, not
`finalize()`, because queuing one task per row of a bulk upload would flood the
worker.

**Rationale**: writing the file is a couple of queries plus a small JSON write, measured in
milliseconds. It was async only because it shared a task with the materialized view refresh,
which is expensive. Retries would still list the datapoint before its file exists, and would
still lose it when the worker is down for a day (the 2026-09-10 incident). `on_commit` means a
rolled-back submission never writes a file.

**Impact**: a write failure is caught and logged (Sentry), the stamp stays `NULL`, and the
reconciler (D-4) retries it. The submission still succeeds: the answers are already saved, and
failing the request over the file would lose nothing and fix nothing.

### D-2: List a registration datapoint only once its current file exists

**Decision**: the device listing calls `downloadable()` (D-1), which keeps
`FILE_EXEMPT | FILE_CURRENT`: monitoring rows (`Q(form__parent__isnull=False)`), and rows with
`file_generated_at >= COALESCE(updated, created)`.

**Rationale**: a listed datapoint with no file costs the device a request that can only fail.
Today the app skips it and the next ordinary sync never lists it again. A stale file is worse:
the device stores old answers and marks them current. Not listing it until its file catches up
turns both into a short delay that heals on its own (D-5).

### D-3: `geometry_total` keeps counting datapoints that have no file yet

**Decision**: `geometry_total` stays computed from the cursor-free published set, **without**
D-2's filter.

**Rationale**: `geometry_total` is how a device knows its overlap index is incomplete
(GEO-006 D-9). A registered plot whose file is missing is still a registered plot. Filtered out
of the count, the device would hold every plot it *can* download, see a matching total, and pass
an overlap check against a set missing that plot. That is the false pass GEO-007 D-10 exists to
refuse. Left in the count, the device refuses with "gapped" until the reconciler writes the
file, then heals on the next sync.

**Impact**: the listing and `geometry_total` disagree on purpose while a file is outstanding.
The view comment must say so; it already explains why `geometry_total` and `total` differ.

### D-4: Reconcile hourly through Django-Q, not by hand

**Decision**: `generate_data_json` gains a default mode that rewrites only rows that are owed:
published, non-draft registration datapoints whose `file_generated_at` is `NULL` or older than
`updated`, **or whose UUID is missing from the `datapoints/` folder**. The folder is listed once
per run, and the same listing drives cleanup (D-7). `--all` keeps today's rewrite-everything
behaviour, and `--dry-run` prints what would be rewritten and deleted without touching
anything. An hourly Django-Q `Schedule`
row runs the owed-only mode (`api.v1.v1_data.tasks.reconcile_datapoint_files`). Migration
`0006_formdata_file_generated_at` registers it with `get_or_create`, next to the column it adds;
`main`'s `0012_schedule_tenant_purge` uses the same pattern. The worker that runs it is the
existing `qcluster` (`run_worker.sh`, `Dockerfile.worker`), so nothing new is deployed.
`run-prod.sh` also runs it once in the background at startup, which is the backfill.

**Rationale**: hourly because a datapoint owed a file is hidden from devices until it is
written, and when nothing is owed the run is one indexed query plus one directory listing.
Checking the folder, not only the stamp, matters: a stamp says the file **was** written, and a
file deleted by hand or lost with a volume afterwards is otherwise never noticed.

Django-Q rather than the cron container (`backend-cron`, `mis-cron`, `job.sh`):
- `job.sh` runs once a day (23:01), so a missing file would hide its datapoint for up to a day.
- It runs with `set -eu` behind the Excel exports, so one failed export would skip the reconcile.
- It ends by stopping the SQL proxy sidecar (`quitquitquit`), so a second crontab entry at another
  hour would run without a database.

**Impact**: no tenant context is needed. `FormData` is scoped only through `for_user`, so the
job sees every tenant's rows, as `generate_data_json` does today.

Django-Q stops a task after `Q_CLUSTER["timeout"]` (600 s). A first backfill of tens of thousands
of rows can run longer than that. That is safe: each rewrite stamps its own row, so the next
hourly run carries on from there. The startup run in `run-prod.sh` is not under that limit.

### D-5: The file stamp is part of the cursor and of `last_updated`

**Decision**: the cursor adds `Q(file_generated_at__gte=last_synced_at)`, and `last_updated`
becomes the later of `updated or created` and `file_generated_at`.

**Rationale**: without this, rewriting a file reaches no device that has already synced. The
row's `updated` has not moved, so the cursor skips it. Even under a full pull, the device's
skip-unchanged check (`syncedAt >= lastUpdated`) keeps the stale copy. Both are fixed by
treating "file rewritten" as a change. It also makes D-2's hiding safe: a row hidden at one sync
is listed at the first sync after its file is written.

**Impact**: no app change. The app already compares `last_updated` against its stored
`syncedAt`.

### D-6: A missing datapoint file answers 404 *(revised 2026-10-06)*

**Decision**: add a `404`, scoped to datapoint files only:

```nginx
location /storage/datapoints/ {
    try_files $uri =404;
}
```

`/datapoints/` already rewrites into `/storage/datapoints/`, so both URLs are covered.
`/images/`, `/attachments/` and the other storage routes keep the SPA fallback. They have other
consumers (the web app) and are not part of this analysis.

**Rationale**: the `200 text/html` is what kept this incident invisible: every consumer saw a
success for a file that was not there. After D-2, a datapoint is listed only when its current
file exists, so a 404 can only mean the file disappeared **after** it was listed. That is
exactly the case that should be loud.

The first draft held the 404 back because app builds older than the GEO-006 D-4 amendment
treat one download error as "overlap validation unavailable on every form". That cost is real,
but it is no longer permanent: the reconciler notices the missing file (D-4) and rewrites it
within the hour, the next sync downloads it with no error, and readiness flips.

**Ordering**: ship in the same release as D-2, never before. Against today's listing, the 404
would hit every datapoint whose file is missing right now, on every installed build. During the
backfill nothing 404s: unwritten rows are hidden (stamp `NULL`), not listed.

**Impact**: the device's download throws instead of skipping. It is counted as an error, the
job is retried, the amended app shows "Unable to sync", and Sentry gets the URL. The app keeps
its APP-407 guard against an HTML body, which no longer fires for this route.

### D-7: The reconciler deletes files nobody can be listed for *(2026-10-06)*

**Decision**: each reconcile run also deletes `datapoints/*.json` files whose name belongs to
no published, non-deleted registration datapoint. Only `.json` files are considered. The name
is not checked against the UUID format, because rows imported by the bulk upload or the Flow
migration may carry a UUID that isn't in canonical form. Their files must count as present,
or the reconciler would rewrite them every hour.

- **List the folder first, then query the database.** A file written after the listing is not
  in it. A file written before the listing belongs to a row that had already committed, because
  D-1 writes on commit, so the query sees that row. No grace period is needed.
- **Soft-deleted rows lose their stamp with their file.** `file_generated_at` is set to `NULL`
  through `objects_deleted`, so `restore()` brings the row back as owed and the reconciler
  rewrites it. Without this, a restored row would look current with no file behind it.
- **Pending edits keep the original's file.** A pending edit shares its UUID with the published
  original (`FormData.objects.filter(uuid=..., is_pending=False)` in `v1_data/views.py`), and the
  original is in the published set.
- **Guard:** if the query returns no rows, or the run would delete **more than half** of the
  files in the folder, delete nothing and log an error, unless `--force` is passed. A run
  pointed at the wrong database must not empty the folder. *(Amended during implementation:
  the empty-set check alone was not enough. A test run uses a test database of a few rows
  against the shared storage folder, which locally holds the developer's real files and in CI
  holds the files of other parallel test workers. Every one of those looks orphaned.)* A
  genuine mass deletion, such as purging a large workspace, needs one `--force` run.

**Rationale**: the file holds the datapoint's answers and stays reachable by anyone who has its
UUID. Deleting a datapoint should take its answers off the web. This also covers datapoints
removed with a purged workspace (`purge_uninitiated_tenants`) and any row deleted outright.

**Impact**: the 404 (D-6) is what a device sees for a file deleted here, but D-2 has already
stopped listing the row, so a device can only meet it in the moment between listing and download.

---

## 6. Type/Constant Mappings

| Concept | Value |
|---|---|
| File written and current | `file_generated_at >= COALESCE(updated, created)` |
| File owed | `file_generated_at IS NULL OR file_generated_at < COALESCE(updated, created)`, or the UUID is missing from `datapoints/` |
| File orphaned | `datapoints/<uuid>.json` whose UUID has no published, non-deleted registration row (D-7) |
| Missing file response | `404` for `/datapoints/<uuid>.json` and `/storage/datapoints/<uuid>.json` (D-6) |
| Schedule name | `reconcile-datapoint-files`, type `H`, `repeats = -1` |
| Scheduled function | `api.v1.v1_data.tasks.reconcile_datapoint_files` |
| Cleanup refusal threshold | more than half of the folder, or an empty published set (D-7); `--force` overrides |

---

## 7. Compatibility & Migration

### Publication paths that must call `finalize()`

| Path | Where | Today |
|---|---|---|
| Web submit, no approval | `SubmitFormSerializer.create` (`v1_data/serializers.py`) | `async_task(seed_approved_data)` |
| Web / mobile submit, not pending | `SubmitPendingFormSerializer.create` | `async_task(seed_approved_data)` |
| Batch fully approved | `v1_approval/serializers.py`, per datapoint | `async_task(seed_approved_data)`. **Kept as is**: the row stays pending, so it is not listed, until the task flips it, and the task writes the file (D-1) |
| Superadmin direct edit | `FormDataAddListView.put` (`v1_data/views.py`) | `async_task(seed_approved_data)` |
| Web draft publish | `PublishDraftFormDataView` | `async_task(seed_approved_data)` |
| Mobile draft publish | `sync_pending_form_data` (`v1_mobile/views.py`) | `save_to_file` inline, **no view refresh** |
| Excel bulk upload, superadmin | `save_data` (`v1_jobs/seed_data.py`) | **nothing** — new rows have no file, updated rows keep a stale one |
| Seeders, `migrate_form_options` | management commands | `save_to_file` inline |

`seed_approved_data` keeps the `is_pending` / `updated` bookkeeping and writes the file through
`write_file()`. The bulk upload calls `write_file()` once per published row after its answers
are created, and so do the seeders, so their rows are stamped and listed (D-1).

### When a file is not available

Every way a datapoint's file can be unavailable, and how each one heals without an operator:

| Cause | Listed? | Device sees | Overlap validation (GEO-007) | Recovery |
|---|---|---|---|---|
| Not written yet: the write failed, the backfill has not reached it, or the row was restored | No (D-2) | Nothing to download | `geometry_total` still counts it, so the form refuses as "gapped", with Retry (D-3) | Reconciler writes it within the hour. The stamp passes the cursor, so it is listed on the next sync (D-5) |
| Stale: the row changed and the file was not rewritten | No (D-2) | Keeps its previous copy | Checks against that plot's previous polygon, as a device that has not synced for an hour would | Same. `last_updated` moves, so the device downloads the new copy |
| Gone from disk after it was written (deleted by hand, volume lost) | Yes: the stamp says current | `404`, a download error. The job retries and the amended app shows "Unable to sync" (D-6) | That form refuses as "not ready". On builds older than the GEO-006 D-4 amendment, every form does | Reconciler finds the UUID missing from the folder and rewrites it. The next sync is clean |
| The datapoint was deleted | No: not published | Nothing new | Not a candidate | Reconciler deletes the file (D-7) |

No row in this table needs `generate_data_json` to be run by hand.

### Backward Compatibility
- [x] API shape unchanged. Old app builds see fewer rows only while files are owed, and the
      cursor change re-lists them
- [x] A missing datapoint file was a skipped `200` and is now a `404` error. On builds older
      than the GEO-006 D-4 amendment that disables overlap validation until the reconciler
      restores the file (D-6)
- [x] Existing files untouched. The backfill rewrites them with the same content
- [x] `generate_data_json` with `--all` behaves as today

### Mobile App Impact
- [x] Sync endpoints affected: `/device/datapoint-list` (row filter, cursor, `last_updated`),
      and the static `/datapoints/<uuid>.json` route (`404` when absent)
- [x] SQLite schema changes: no
- [x] Version detection: none needed. Every installed build benefits

### Deploying

Run `python manage.py generate_data_json --dry-run` on each server **before** the release.
"Refused to delete N" means more than half the folder has no matching row. The hourly run will
then log a refusal every hour (a Sentry event each time) until someone checks the list and runs
one `generate_data_json --force`. Local development showed this: 8,581 leftover files from
seeding and test runs against 204 published rows.

### Seeder/CLI Compatibility
- [x] Existing seeders work, and now stamp their rows
- [x] New command: none. `generate_data_json` gains the owed-only default with cleanup,
      `--all` and `--dry-run`

---

## 8. Security Considerations

- [x] No new endpoint, permission or input
- [x] Files carry the same JSON `save_to_file` built, now from `FormData.file_payload()`
- [x] The Sentry event for a failed write carries the datapoint id and UUID only, no answers

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | `finalize()` writes the file and stamps the row on commit; a rolled-back transaction writes neither |
| Unit | A write that raises leaves the stamp `NULL` and does not fail the request |
| Unit | Every path in §7 stamps the row (one test per path, asserting the stamp, not the mock) |
| Unit | The bulk upload writes files for new rows and rewrites them for updated ones |
| Integration | Listing omits a row with a `NULL` stamp and a row with a stale stamp; lists it once stamped |
| Integration | A row stamped after `last_synced_at` is in the next cursor-filtered listing |
| Integration | `last_updated` moves when only the file is rewritten |
| Integration | `geometry_total` counts a row whose file is owed (D-3) |
| Unit | Owed-only reconcile touches only owed rows; `--all` touches every row |
| Unit | Reconcile rewrites a stamped row whose file is missing from disk |
| Unit | Reconcile deletes an orphan file, clears a soft-deleted row's stamp, and keeps the file of a published row that has a pending edit |
| Unit | A file written between the folder listing and the query is never deleted |
| Unit | An empty published set, or a run that would delete more than half the folder, deletes nothing and logs an error; `--force` deletes |
| Unit | `--dry-run` writes and deletes nothing |
| Migration | The schedule row is created once, and a replay does not duplicate it |
| Unit | `downloadable()` (`FILE_EXEMPT`) and `needs_file()` agree on which rows get a file |
| Manual | Stop the worker, submit from the web, sync a device: the datapoint arrives |
| Manual | `/datapoints/<absent>.json` answers `404`; `/images/` behaves as before |
| Manual | Delete a listed file by hand and sync a device: "Unable to sync". After the next reconcile, the next sync is clean |

**Hours breakdown**

| Unit | h |
|---|---|
| Field + migration + schedule migration | 0.5 |
| `finalize()` / `write_file()`, on-commit write, failure handling | 1 |
| Route the 8 publication paths through it | 1.5 |
| Listing filter, cursor, `last_updated` | 1 |
| Reconcile mode in `generate_data_json`: owed incl. missing on disk, cleanup, guard, `--dry-run`; scheduled task; `run-prod.sh` | 2 |
| nginx `404` block for datapoint files | 0.5 |
| Tests per §9 | 4 |
| Test-server pass: worker stopped, bulk upload, stale-file rewrite, file deleted by hand | 1 |
| **Total** | **11.5** |

---

## 10. Open Questions

- [x] ~~Deleted datapoints keep their file.~~ **Answered 2026-10-06: the reconciler deletes
      them** → D-7
- [x] ~~When can the nginx 404 land?~~ **Answered 2026-10-06: in this task, with D-2, scoped to
      datapoint files** → D-6 revised. The behaviour for every missing-file case is in §7,
      "When a file is not available"

---

## 11. References

- `doc/design/APP-407-datapoint-sync-resilience.md` §7: the deferred gap this closes
- `doc/design/GEO-006-local-geometry-index.md` D-4 (amended 2026-10-06), D-9
- `doc/design/GEO-007-polygon-overlap-detection.md` D-10
- `backend/api/v1/v1_data/migrations/0006_formdata_file_generated_at.py`: the column and the
  hourly schedule (the pattern of `main`'s `0012_schedule_tenant_purge`)

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-10-06 | Approved |
| Tech Lead | | | |
| Product | | | |
