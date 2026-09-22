# Workspace migration

Moves a single-host MIS install into one workspace of the multi-tenant
instance: database rows and file storage.

Design and rationale: [MT-014](../doc/design/MT-014-single-host-to-workspace-migration.md).
Requirements and the fact-finding behind it:
[doc/claude/tenant-data-migration-mohhs.md](../doc/claude/tenant-data-migration-mohhs.md).

## Use

```bash
# rehearse -- runs the whole transaction and rolls it back
./migration/migrate-tenant.sh \
    --tenant mohhs \
    --dump   storage/mohhs/db/mohhs.sql \
    --files  storage/mohhs/storage \
    --env    local --reset --dry-run

# for real
./migration/migrate-tenant.sh \
    --tenant mohhs \
    --dump   storage/mohhs/db/mohhs.sql \
    --files  storage/mohhs/storage \
    --env    local --reset
```

Afterwards, three steps the script deliberately does not take. Locally:

```bash
./dc.sh exec backend ./manage.py createsuperuser --tenant=mohhs
./dc.sh exec backend ./manage.py generate_sqlite  --tenant=mohhs
# then assign roles -- imported users are superusers with no user_role
```

On a cluster, the same two commands go through the backend pod:

```bash
POD=$(kubectl -n akvo-mis-namespace get pods -o name | grep backend-deployment | head -1)
kubectl -n akvo-mis-namespace exec -it "$POD" -- ./manage.py createsuperuser --tenant=mohhs
kubectl -n akvo-mis-namespace exec -it "$POD" -- ./manage.py generate_sqlite  --tenant=mohhs
```

`--tenant` on `createsuperuser` is **mandatory**. Without it the account
gets `tenant=NULL` and can sign in at no workspace host at all.

## Flags

| Flag | |
|---|---|
| `--tenant` | Target workspace subdomain. Must already exist. |
| `--dump` | Plain-format `pg_dump` of the source install. |
| `--files` | Source `STORAGE_PATH` root. `images/` and `datapoints/` are read from it. |
| `--env` | `local`, `test` or `prod`. |
| `--reset` | Delete everything the workspace owns first. Without it a non-empty workspace aborts the run. |
| `--dry-run` | Roll back instead of committing. Skips the file transfer. |
| `--skip-files` | Database only. |

## Requirements

`docker`, plus `kubectl` for `--env test|prod`. No Postgres client is
needed on the host — `psql` runs from a pinned container, because neither a
developer machine nor the backend image (`python:3.8.5`) has one.

## Production

`--env test|prod` resolves credentials from the `akvo-mis` secret and
reaches Cloud SQL through the proxy sidecar already running in the backend
pod, via `kubectl port-forward`. Files go over `tar` piped through
`kubectl exec` into the `/app/storage` PVC.

Rehearse with `--env test --dry-run` before trusting `--env prod`: that
path — cluster credentials, port-forward, tar-over-exec — is the part the
local run never exercises.

Avoid starting a production run shortly before 23:00, when the
`akvo-mis-jobs` CronJob writes to the same volume. It is not suspended:
it touches no migrated table and no migrated folder (MT-014 D-10).

## Files

| | |
|---|---|
| `migrate-tenant.sh` | Entry point: arguments, workspace resolution, COPY extraction, file transfer, connection setup |
| `import.sql` | One transaction: guard, snapshot, reset, staging, offset, user map, inserts, `setval` |
| `verify.sql` | Seven assertions, run inside the transaction before commit |

A failure at any point leaves the database untouched — the whole import is
one transaction. Files are copied first on purpose, so a rollback leaves
unreferenced files rather than rows whose images 404.
