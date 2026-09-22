# Feature Design Document

## Feature: Migrating a single-host install into a workspace

**Task ID**: MT-014
**Author**: Iwan Firmawan
**Date**: 2026-09-22
**Status**: Done — migrated to production 2026-09-22
**Implementation**: `migration/migrate-tenant.sh`, `migration/import.sql`,
`migration/verify.sql`

---

## 1. Context & Problem Statement

```
Currently:
- Several MIS installs run single-host, one database per customer,
  with every row untenanted. `mohhs` is one of them.
- The SaaS instance is shared-table multi-tenant: one schema, a `tenant`
  table, and a nullable `tenant_id` FK on nine root tables. Everything
  else is scoped by traversal through TENANT_PATH.
- There is no tooling to move a single-host install into a workspace.
  A `pg_dump` from one cannot be restored into the other: the target is
  live and already holds nine workspaces whose primary keys collide.

Goal:
- Move a single-host install's database and file storage into an existing
  workspace, run from a developer machine against both the local stack and
  the production GKE cluster, repeatably enough to rehearse locally and
  then run for real at cutover.
```

Requirements discovery and the fact-finding behind this design are in
[doc/claude/tenant-data-migration-mohhs.md](../claude/tenant-data-migration-mohhs.md).
That document's D1–D8 are the *product* decisions this design implements;
the D-1…D-9 below are the *technical* decisions it makes.

The first customer is `mohhs` (tenant id 10), but nothing here is
specific to it. The subdomain is an argument.

---

## 2. Requirements

### User Acceptance Criteria

- [x] `https://<subdomain>.<BASE_DOMAIN>/control-center` lists the source
      install's forms, with matching submission counts per form
- [x] A user from the source install signs in with their existing password
      and sees only their own workspace
- [x] The administration hierarchy renders to full depth, and photo answers
      render from the migrated image files
- [ ] A user from another workspace is refused at this workspace's host,
      and vice versa — untested; the host-routing guard it relies on is
      covered by [MT-008](MT-008-subdomain-routing.md) and unchanged here
- [ ] Mobile assignments sync against a freshly generated master-data
      SQLite file — untested

### Technical Acceptance Criteria

- [x] Every migrated row is reachable from the target tenant via its
      declared `TENANT_PATH`; no orphans
- [x] `form.id`, `question.id` and `question_group.id` are byte-identical
      to the source
- [x] `administrator.path` resolves to the correct ancestors after ID
      remapping
- [x] Row counts for every other tenant are unchanged
- [x] The database half runs in a single transaction and rolls back whole
- [x] `--dry-run` reports what would be written without writing
- [x] Re-running against an already-migrated workspace refuses, or with
      `--reset` reproduces the same result
- [x] The same invocation works against local and production, differing
      only by `--env`

---

## 3. Data Model Changes

**None.** No Django model, migration, or table definition changes. This is
a data movement, and the target schema already accommodates every source
column — the 14 migrations the source lags by are purely additive
(nullable `tenant_id` FKs, `system_user.is_active`, the new `dashboard`
tables).

### Staging schema

The one structure this introduces is transient: a schema `mig_src`,
created and dropped inside the same transaction as the import.

```sql
CREATE SCHEMA mig_src;
CREATE TABLE mig_src.<table> (LIKE public.<table>);  -- per migrated table
-- ... load source rows, transform, INSERT INTO public.<table> SELECT ...
DROP SCHEMA mig_src CASCADE;
```

Staging tables are cloned from the **target's** definitions, not from the
dump's DDL (D-2). They carry no constraints beyond NOT NULL and no foreign
keys, so source rows load in any order.

One column needs attention: `system_user.is_active` is NOT NULL with no
database default and does not exist in the source. Its staging table gets
`ALTER COLUMN is_active SET DEFAULT true` so the source's `COPY` — which
names its columns explicitly and simply omits it — succeeds, satisfying
FR-6 (users can sign in immediately).

### Migration Strategy

```
- Nothing is altered in the target schema; only rows are inserted.
- Source rows are loaded into mig_src, transformed there, then
  INSERT ... SELECT into public in foreign-key order.
- Sequences are advanced past the inserted maxima with setval().
- Rollback: the whole database half is one transaction. Files are copied
  before it, deliberately (D-8), so a rollback leaves unreferenced files
  rather than dangling references.
```

---

## 4. API Contract

**Not applicable.** No endpoint is added, changed, or removed. The
migration operates below the application, directly on the database and the
storage volume, while the application is running.

The operator-facing contract is the script's command line:

```bash
migration/migrate-tenant.sh \
  --tenant   <subdomain> \
  --dump     <path/to/source.sql> \
  --files    <path/to/source/storage> \
  --env      local|test|prod \
  [--reset] [--dry-run] [--skip-files]
```

| Flag | Purpose |
|------|---------|
| `--tenant` | Target workspace subdomain. Resolved to `tenant.id`; the run aborts if it does not exist. |
| `--dump` | Plain-format `pg_dump` of the source install. |
| `--files` | Source `STORAGE_PATH` root; `images/` and `datapoints/` are read from it. |
| `--env` | `local` talks to the compose `db` on `localhost:5432`. `test` and `prod` open a port-forward to the Cloud SQL proxy sidecar on the matching cluster. `test` was added during implementation so the cluster path can be rehearsed before production. |
| `--reset` | Delete the target tenant's existing workspace data first (D-9). |
| `--dry-run` | Run the transaction and `ROLLBACK` instead of committing; print the verification report. |
| `--skip-files` | Database only, for fast iteration during rehearsal. |

---

## 5. Decision Log

### D-1: Staging schema in the same database, not a second database or FDW

**Options Considered**:
1. Restore the dump into a separate database and pull rows across with
   `postgres_fdw` or `dblink`.
2. Restore into a staging **schema** of the same database.
3. Parse the dump in application code and insert through the ORM.

**Decision**: Option 2.

**Rationale**: `INSERT ... SELECT` between two schemas of one database
needs no extension, no second connection, and participates in a single
transaction. Cloud SQL permits creating a schema with the application
role; creating a database may not be. Option 1 would require an extension
installed on a managed instance, and Option 3 is addressed in D-4.

**Impact**: The whole database half is atomic, and rollback is free.

### D-2: Clone staging tables from the target, load only the dump's data

**Options Considered**:
1. Replay the dump's own `CREATE TABLE` DDL into the staging schema,
   rewriting `public.` to `mig_src.`.
2. Build staging tables as `LIKE public.<table>` and feed in only the
   dump's `COPY` blocks.

**Decision**: Option 2.

**Rationale**: The dump was produced by `pg_dump` 14.24 against a 14.23
server; the local target runs Postgres 12 and production runs Cloud SQL at
an unpinned version. Replaying cross-version DDL invites failures that
have nothing to do with the data. Cloning the target's own definitions
sidesteps version skew entirely, and because the target's columns are a
superset, the source's explicit `COPY` column lists load cleanly with
absent columns taking their defaults.

It also makes exclusion free: tables not cloned cannot be loaded, so
`jobs`, `mobile_apks` and the `django_*` operational tables are dropped by
simply not appearing in the inventory, rather than by filtering rows.

**Impact**: The dump is consumed as data, never as DDL. The extractor
keeps only whitelisted `COPY <table> (...) FROM stdin;` blocks up to their
`\.` terminator, rewriting the schema prefix. `\restrict` / `\unrestrict`
lines — emitted by recent `pg_dump` builds and not understood by older
`psql` — are stripped in the same pass.

### D-3: One global ID offset, not per-table

**Options Considered**:
1. Offset each table by its own target maximum.
2. One offset constant applied to every remapped table.
3. Map every ID individually through lookup tables.

**Decision**: Option 2, with the offset computed at run time as the
greatest current value across all affected sequences, rounded up to the
next 10 000 000.

**Rationale**: Source IDs are small (largest is `option` at 4644). A
single constant is trivially auditable — every migrated row's provenance is
visible in its ID — and one number appearing in every statement is far
easier to review than fifteen. Option 3 is the general solution and is
unnecessary at this scale.

**Impact**: Remapped IDs land in a clearly identifiable band.
Sequences are advanced with `setval()` after insert so subsequent
application writes do not collide.

### D-4: Bash driving SQL, not a Django management command

**Options Considered**:
1. A `manage.py import_workspace` command using the ORM.
2. A bash entrypoint driving a SQL transform.

**Decision**: Option 2.

**Rationale**: The transform is set-based — offset primary keys, rewrite
`administrator.path`, stamp `tenant_id` — which is one statement per table
in SQL and an object-graph walk in the ORM. The ORM would still have to
shell out to load the dump, so it adds a layer without removing one. The
surrounding work (restoring to staging, moving 1.4 GB of files, switching
between `./dc.sh` and `kubectl`) is shell work regardless.

It also matches the existing idiom: `seeder.sh` is already a bash wrapper
taking `--tenant=<subdomain>` and threading it through.

**Impact**: Three files, no application code, nothing shipped in the
container image.

### D-5: Preserve timestamp-based IDs, offset serial ones

**Options Considered**:
1. Offset every primary key uniformly.
2. Offset only the tables whose keys actually collide.

**Decision**: Option 2.

**Rationale**: `form`, `question` and `question_group` use
epoch-millisecond primary keys. All 858 such IDs in the source were checked
against the target: none collide. More importantly, form IDs are not
internal — deployed mobile clients and stored form JSON reference them
directly, so renumbering would break apps already in the field.

`answer.options` was checked for the same hazard and stores option
*values* and geo coordinates as strings, never option IDs, so offsetting
`option.id` is safe.

**Impact**: Three tables insert with their keys untouched; the rest are
offset.

### D-6: A containerised `psql`, so the host needs nothing installed

**Options Considered**:
1. Require `postgresql-client` on the operator's machine.
2. `kubectl exec` into the backend pod and use its `psql`.
3. Run `psql` from a pinned `postgres:14-alpine` container.

**Decision**: Option 3.

**Rationale**: Option 2 is impossible — the backend image is
`python:3.8.5` with no Postgres client installed. Option 1 adds a setup
step and drifts by version between operators. A pinned container gives the
same client everywhere and needs only Docker, which the project already
requires.

**Impact**: The script's only host dependencies are `docker`, `kubectl`
and `gcloud`.

### D-7: Reach production through a port-forward to the proxy sidecar

**Options Considered**:
1. Connect to Cloud SQL directly over its public IP.
2. Run `cloud-sql-proxy` locally against the operator's gcloud credentials.
3. `kubectl port-forward` to the existing proxy sidecar in the backend pod.

**Decision**: Option 3.

**Rationale**: The backend pod already runs `cloud-sql-proxy` (a native
sidecar — `initContainers` with `restartPolicy: Always`, image
`gce-proxy:1.30.1`) listening on `127.0.0.1:5432` in the pod's network
namespace. `kubectl port-forward` reaches exactly that, so the connection
reuses the deployment's own authorised path with no new credentials, no
new IP allowlist entry, and nothing to install.

**Impact**: `--env prod` runs `kube prod`, opens the forward on a local
port, and points the same `psql` invocation at it. Local and production
differ only in host and port, satisfying the "no hand-editing between
environments" requirement.

### D-8: Files before database, streamed as tar

**Options Considered**:
1. `kubectl cp` the directories.
2. `tar` piped through `kubectl exec`.
3. Copy files after the database transaction commits.

**Decision**: Option 2, run **before** the database transaction.

**Rationale**: `kubectl cp` is unreliable at 5 000+ files and offers no
resumption; a tar stream is one connection and preserves modes. Ordering
matters more: if files are copied first and the transaction then fails, the
result is unreferenced files on a volume — harmless, and overwritten by the
next attempt. The reverse order risks committed rows whose images 404.

**Impact**: `tar cf - -C <src> images datapoints | kubectl exec -i <pod> --
tar xf - -C /app/storage`. Locally the same stream targets `$STORAGE_PATH`
directly. Filenames are UUID-suffixed, so merging into the shared global
folders carries no realistic collision risk.

### D-10: Schedule around the nightly CronJob rather than suspending it

**Options Considered**:
1. Suspend `akvo-mis-jobs` for the duration of the run and resume after.
2. Run outside the 23:00 window and leave the CronJob alone.

**Decision**: Option 2.

**Rationale**: The job runs `/app/job.sh`, which calls
`generate_excel_data` for each form in `source/forms/*.prod.json` and
writes XLSX output plus an index page into `storage/cronjob_results/`. It
does not insert into any migrated table, and it writes to a folder this
migration never touches — the tar stream carries only `images/` and
`datapoints/`. Its reads are covered by MVCC: the import is one
transaction, so a concurrent report sees the workspace either wholly
before or wholly after.

Suspending would therefore protect against nothing, while introducing a
real failure mode — a forgotten `--unsuspend` stops nightly reporting
silently, and nobody notices until someone asks for a report.

**Impact**: The runbook says to avoid starting a production run shortly
before 23:00, purely so 1.4 GB is not streaming onto the NFS volume while
the job writes to it. No cluster object is modified.

### D-9: Re-runnability by explicit reset, not by idempotent upsert

**Options Considered**:
1. Make every insert an upsert keyed on some natural identifier.
2. Refuse if the workspace already holds data, with `--reset` to clear it.

**Decision**: Option 2.

**Rationale**: Product decision D3 means this runs at least twice — a
local rehearsal against this snapshot, then production against a fresh dump
taken at cutover — and repeatedly during development. But the two runs
carry *different* data, so an upsert would silently merge two generations
of a workspace. Refusing by default makes the destructive step deliberate.

**Impact**: `--reset` deletes **every** row the target tenant owns, in
reverse foreign-key order, preserving only the `tenant` row itself. Without
it, a non-empty workspace aborts the run before anything is written.

The reset is total, including the workspace's superadmin. Nothing is
special-cased, so there is no "which account survives?" branch to get
wrong, and the reset is a clean inverse of the import. A superadmin is
recreated afterwards with the existing tenant-aware command:

```bash
./dc.sh exec backend ./manage.py createsuperuser --tenant=<subdomain>
```

`--tenant` is **mandatory** here. That flag is the project's own subclass
of Django's command
([backend/api/v1/v1_users/management/commands/createsuperuser.py](../../backend/api/v1/v1_users/management/commands/createsuperuser.py));
omitting it produces a `tenant=NULL` account that
`TenantAwareBackend.authenticate` can never match, so it can sign in at no
workspace host at all.

Note that the account currently in the `mohhs` workspace came from the
two-phase **registration** flow ([MT-006](MT-006-two-phase-registration.md)),
not from `createsuperuser`. The two produce an equivalent account for this
purpose; only registration additionally creates the levels and root
administration that D1 discards.

---

## 6. Type/Constant Mappings

| Constant | Value | Meaning |
|----------|-------|---------|
| Scripts location | `migration/` | New top-level directory: `migrate-tenant.sh`, `import.sql`, `verify.sql` |
| Staging schema | `mig_src` | Created and dropped within the import transaction |
| ID offset | `ceil(max_sequence_value / 1e7) * 1e7` | Added to every remapped primary and foreign key |
| Local DSN | `localhost:5432` | Compose `db` service, published in `docker-compose.yml` |
| Production DSN | `localhost:<forwarded>` | `kubectl port-forward` onto the proxy sidecar |
| Storage mount | `/app/storage` | PVC `akvo-mis`, 10 Gi RWX `managed-nfs-storage` |
| Namespace | `akvo-mis-namespace` | Same name on the `test` and `production` clusters |

### Verified environment versions

| | Local | Production |
|---|---|---|
| Postgres server | 12 (`postgres:12-alpine`) | 14 (Cloud SQL `akvo-mis-prod`) |
| `BASE_DOMAIN` | operator's choice | `mis.akvo.org` |
| Backend image | `python:3.8.5`, no Postgres client | same |

The source dump was produced by `pg_dump` 14.24 against a 14.23 server, so
production is the **same major version** as the dump's origin and carries
no version skew at all. Local Postgres 12 is the only place the versions
differ, which is where D-2 earns its keep: because the dump is consumed as
data rather than DDL, the local rehearsal behaves identically to the
production run.

### Table inventory

Insert order is top to bottom. Counts are from the `mohhs` snapshot.

| # | Table | Rows | ID policy |
|---|-------|------|-----------|
| 1 | `levels` | 3 | offset, `tenant_id` stamped |
| 2 | `organisation` | 2 | offset, `tenant_id` stamped |
| 3 | `administrator` | 180 | offset + `path` rewrite, `tenant_id` stamped |
| 4 | `system_user` | 6 | offset + duplicate reconciliation, `tenant_id` stamped |
| 5 | `form` | 8 | **preserved**, `tenant_id` stamped |
| 6 | `question_group` | 63 | **preserved** |
| 7 | `question` | 787 | **preserved** |
| 8 | `option` | 492 | offset |
| 9 | `form_published_version` | 66 | offset |
| 10 | `user_form` | 3 | offset |
| 11 | `data` | 135 | offset, incl. self-referencing `parent_id` |
| 12 | `answer` | 4366 | offset |
| 13 | `mobile_assignments` | 5 | offset |
| 14 | `mobile_assignments_forms` | 29 | offset |
| 15 | `mobile_assignments_administrations` | 7 | offset |

**Excluded**: `jobs`, `mobile_apks` (product decisions D4/D5);
`django_session`, `django_q_task`, `django_q_ormq`, `django_admin_log`,
`django_content_type`, `auth_permission`, `django_migrations`
(operational).

**Empty at source, so absent by construction**: `data_approval`, `batch`,
`batch_data`, `batch_comment`, `batch_attachment`, `answer_history`,
`role`, `role_access`, `role_feature_access`, `user_role`, `entities`,
`entity_data`, `question_attribute`, `administration_attribute`,
`administration_attribute_value`, `organisation_attribute`, `dashboard`.

The inventory is data, not code: a source install with rows in those
tables adds them to the list without changing the mechanism.

### Two transforms that are not a plain offset

**`administrator.path`** encodes ancestry as a dot-terminated ID trail
(`7254.7255.7256.`). Each component must be offset in place, with NULL and
empty paths — the root — passed through untouched.

**`system_user` duplicate reconciliation.** Any source account whose email
already exists under the target tenant is not inserted; every foreign key
referencing it is repointed at the surviving target row. Collisions are
found by query against `unique_email_per_tenant`, not from a hardcoded
list, and an unaccounted-for collision aborts the run. In the `mohhs`
snapshot exactly one account collides — the registration superadmin — which
implements product decision D6.

---

## 7. Compatibility & Migration

### Backward Compatibility

- [x] Existing API consumers unaffected — no endpoint or schema change
- [x] Existing data preserved — the migration only inserts; other tenants
      are never written to
- [x] CLI tools still work — no management command is modified

### Mobile App Impact

- **Sync endpoints affected**: none structurally. Mobile clients belonging
  to the migrated workspace see their forms at the *same* form IDs (D-5),
  so an app already in the field continues to resolve them.
- **SQLite schema changes**: no. Master-data SQLite is regenerated after
  the import with `generate_sqlite --tenant=<subdomain>`; it is never
  copied, as it lives under `MASTER_DATA`, not `STORAGE_PATH`.
- **Version detection**: not applicable — no app release is required.
- Mobile clients must be repointed at the new host as part of cutover,
  which is sequencing work outside this design's scope.

### Seeder/CLI Compatibility

- [x] Existing seeders work — untouched
- **New commands needed**: none. `generate_sqlite --tenant=<subdomain>` is
  run after the import as a post-step, using the existing command.

---

## 8. Security Considerations

- [x] **Permission model defined.** Imported rows are stamped with the
      target `tenant_id`, so `for_user` scoping governs them exactly as it
      governs natively created rows.
- [x] **Input validation specified.** The subdomain must resolve to an
      existing tenant. Unaccounted-for email collisions abort. The `COPY`
      extractor accepts only whitelisted table names, so an unexpected
      table in the dump is ignored rather than loaded.
- [x] **No new attack vectors introduced.** No code ships in the
      application image; the scripts run from a developer machine against
      credentials the operator already holds.

Two findings carried over from discovery, both verified:

**Imported superusers do not cross tenants.** The `mohhs` source governs
access purely by `is_superuser`, and all six accounts carry it.
`for_user`
([backend/utils/tenant_scoped_model.py](../../backend/utils/tenant_scoped_model.py))
filters on `user.tenant` with **no superuser bypass**, and
`django.contrib.admin` is installed but routed nowhere — there is no
`admin.site.urls` in the backend. A superuser in the migrated workspace
therefore sees that workspace and nothing else.

**The workspace lands without least privilege.** Because the source never
populated `role` or `user_role`, imported users have no role assignments.
This faithfully reproduces the source install rather than repairing it.
Assigning real roles is follow-up work, tracked separately.

**Production credentials** are never written to disk by the script: the
database is reached through the deployment's own proxy sidecar (D-7), and
the password is read from the existing `akvo-mis` secret at run time.

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | The `COPY`-block extractor against a fixture dump: whitelisted tables kept, others dropped, `\restrict` stripped, `\.` terminators respected. The `path` rewrite against roots, single-level and deep paths, NULL and empty. |
| Integration | Full import into a scratch database seeded with two other tenants. Assert: per-table row counts match source; `form`/`question`/`question_group` IDs unchanged; every `administrator.path` component resolves to an existing ancestor of the same tenant; no `(email, tenant_id)` duplicated; other tenants' row counts unchanged; sequences exceed all inserted IDs. |
| Integration | `--reset` then re-import produces byte-identical results (D-9). `--dry-run` writes nothing. A deliberately unaccounted-for email collision aborts with a non-zero exit and an empty target. |
| E2E | Against the local stack at `<subdomain>.<BASE_DOMAIN>`: sign in as a migrated user; control-center lists the expected forms; a form's submission count matches; a photo answer renders; the administration tree expands to full depth; a user from another workspace is refused. |
| E2E | `generate_sqlite --tenant=<subdomain>` produces a master-data file a mobile assignment syncs against. |
| Manual | Production dry run against the `test` cluster before the real run, exercising the port-forward and tar paths end to end. |

The integration suite is the gate. It is cheap — the whole dataset is
under 6 000 rows — so it runs as a normal test rather than as a rehearsal
ritual.

---

## 10. Open Questions

All four questions raised during design are resolved:

- [x] **Script location** — a new top-level `migration/` directory holding
      `migrate-tenant.sh`, `import.sql` and `verify.sql`. `scripts/` is
      notebooks and Python tools, so it was not the right home.
- [x] **Reset scope** — total, per D-9. The superadmin is recreated with
      `./manage.py createsuperuser --tenant=<subdomain>`.
- [x] **Cloud SQL version** — production is `akvo-mis-prod`, POSTGRES_14,
      the same major version as the dump's origin. The version-agnostic
      approach in D-2 is kept regardless, because it is what makes the
      local Postgres 12 rehearsal faithful.
- [x] **Nightly CronJob** — not suspended, per D-10. Schedule the run away
      from 23:00.

Remaining, and carried deliberately:

- [ ] Product decision D1 said the registration superadmin would survive
      the import. D-9's total reset supersedes that: the account is
      deleted and recreated instead. The outcome is equivalent, but the
      requirements document's FR-5 should be read through D-9.
- [ ] Assigning real roles to the migrated workspace is follow-up work.
      Imported users are superusers with no `user_role`, reproducing the
      source install rather than repairing it. Needs its own task.

---

## 11. References

- Requirements and fact-finding:
  [doc/claude/tenant-data-migration-mohhs.md](../claude/tenant-data-migration-mohhs.md)
- Tenant scoping model: [MT-002](MT-002-tenant-scoping-database.md),
  [MT-003](MT-003-tenant-isolation-read-filtering.md),
  [MT-004](MT-004-tenant-write-path-enforcement.md)
- Host routing: [MT-008](MT-008-subdomain-routing.md),
  [doc/notes/subdomain-local-dev.md](../notes/subdomain-local-dev.md)
- Mobile isolation: [MT-010](MT-010-mobile-app-tenant-isolation.md)
- Tenant-aware seeders: [SEED](SEED-tenant-aware-seeders.md)
- Prior art: `api/v1/v1_users/migrations/0004_backfill_default_tenant.py`,
  the only existing bulk tenant-stamping code

---

## 12. Implementation Results

Implemented as designed, in three files, with no application code touched:

| File | Lines | Role |
|------|-------|------|
| `migration/migrate-tenant.sh` | ~230 | Argument handling, workspace resolution, COPY extraction, file transfer, connection setup |
| `migration/import.sql` | ~400 | The transaction: guard, snapshot, reset, staging, offset, user map, inserts, `setval` |
| `migration/verify.sql` | ~280 | Seven assertions, run inside the transaction before commit |

### Verified run, local, 2026-09-22

`--reset` against the `mohhs` workspace (tenant 10), after a green
`--dry-run` of the same invocation:

| Entity | Rows |
|--------|------|
| form | 8 |
| administration | 180 |
| user | 6 |
| submission | 135 |
| answer | 4366 |

5 114 images and 26 datapoints transferred. All nine other workspaces
unchanged. All seven verification assertions passed: row counts, user
resolution, `unique_email_per_tenant`, administration paths,
cross-workspace references, other-workspace snapshot, sequence advance.

### Deviations from the design

**`--env test` added.** The design named `local|prod`. A `test` value was
added so the cluster path — credentials, port-forward, tar-over-exec — can
be rehearsed against the test cluster, which the design's own testing
strategy called for but the interface did not allow.

**Work directory moved out of `/tmp`.** Docker Desktop bind-mounts only
paths it has been told to share, and `/tmp` is not one of them, so the
extracted COPY file could not be mounted into the `psql` container. The
work directory is now created under the repository root and removed on
exit; `.migration-work.*` is gitignored.

### Verified run, production, 2026-09-22

`--env prod --reset` against `mohhs.mis.akvo.org` (tenant id 4 there, not
10 — the subdomain is what the script resolves), after a green
`--env prod --dry-run` of the same invocation. Identical counts to local:
8 forms, 180 administrations, 6 users, 135 submissions, 4366 answers.
5 115 images and 32 datapoints on the PVC, 1.3 GB. Staging schema dropped.
The three other production workspaces — `default`, `devops`, `jonah` —
unchanged.

The file transfer took roughly 45 minutes, against seconds locally:
`tar` over `kubectl exec` onto NFS costs far more per file than a local
copy, and 5 140 small files is the worst shape for it. Budget an hour for
a workspace this size and do not mistake the silence for a hang. The
database half took under a minute.

### One bug the production path surfaced

`psql` runs in a container with `--network=host` (D-6), which is correct
on plain Docker Engine but wrong under Docker Desktop, Colima or Rancher
Desktop: those run containers inside a VM, so `--network=host` is the
VM's loopback. `kubectl port-forward` listens on the real host and is
invisible from there. The symptom is `connection refused` against a
listener that is demonstrably healthy.

Local had been passing by accident — the compose `db` publishes its port,
which the VM can reach — so this could only surface on a cluster. The
script now probes both routes at startup and falls back to
`host.docker.internal`, which keeps it correct on either engine.

This is the argument for the design's own advice to rehearse the cluster
path: everything `--env prod` adds over `local` was exactly where the bug
was.

### Not yet exercised

- Mobile master-data SQLite regeneration and a mobile sync against it.
- Cross-workspace refusal, which depends on host routing this change does
  not touch ([MT-008](MT-008-subdomain-routing.md)).

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
