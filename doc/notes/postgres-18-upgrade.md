# Upgrading a local database to PostgreSQL 18

The dev, test and CI compose stacks moved from `postgres:12-alpine` to
`postgres:18.6-alpine`. This is groundwork for the Django 6.1 migration: CI runs
the version test and production will run, so a version surprise surfaces here
rather than in a deployment.

PostgreSQL does not read a data directory written by an older major version, so
an existing `pg-data` volume cannot simply be pointed at the new image. One
dump-and-replay per volume is needed, once.

## The data directory moved

`postgres:18` and newer store data in a **major-version-specific subdirectory**
and refuse to start if anything is mounted at the old location
([docker-library/postgres#1259](https://github.com/docker-library/postgres/pull/1259)):

```
Counter to that, there appears to be PostgreSQL data in:
  /var/lib/postgresql/data (unused mount/volume)
```

The compose files mount `pg-data` at `/var/lib/postgresql` instead, and the
server writes to `/var/lib/postgresql/18/docker`. That is the layout the image
wants so a future major bump can use `pg_upgrade --link` without crossing a
mount boundary.

## Migrating your volume

`db/script/dump-db.sh` writes to `db/docker-entrypoint-initdb.d/001-init.sql`,
and `initdb` replays everything in that directory when it finds an empty data
directory. So the dump is also the restore — no manual `psql` step:

```bash
git stash list                      # make sure the PG18 pins are NOT yet checked out
./dc.sh up -d db                    # still on 12
db/script/dump-db.sh                # -> db/docker-entrypoint-initdb.d/001-init.sql
git checkout <branch-with-pg18>     # now take the new pins
./dc.sh down -v                     # drops pg-data AND pg-admin-data
./dc.sh up -d                       # 18.6 replays 000-init.sql then 001-init.sql
./dc.sh exec backend python manage.py migrate
```

`001-init.sql` is gitignored. It is written by the container as `root`; if that
bothers your tooling, `docker run --rm -v "$PWD/db/docker-entrypoint-initdb.d:/d"
alpine chown "$(id -u):$(id -g)" /d/001-init.sql`.

Delete `001-init.sql` once the restore is done, or every later `down -v` will
replay that same snapshot instead of starting clean.

**Each worktree is its own compose project**, so each has its own `pg-data`
volume and needs its own pass. `docker volume ls | grep pg-data` lists them.

If you do not care about your local data, skip the dump entirely:

```bash
./dc.sh down -v && ./dc.sh up -d
./dc.sh exec backend ./seeder.sh
```

`pg-admin-data` must be recreated too — pgAdmin went from 5.7 to 9.18, which
runs as a different uid and will not adopt the old volume. `down -v` covers it.

## `system_user` is now a reserved builtin

PostgreSQL 16 added a `system_user` **function** to `pg_catalog`, and this schema
has a *table* of that name. An unquoted reference resolves to the function:

```sql
SELECT count(*) FROM system_user;     -- 1  (the authenticated identity)
SELECT count(*) FROM "system_user";   -- 27 (the users table)
```

Django quotes every identifier, so the ORM is unaffected. Hand-written SQL is
not: quote the table name. In a join the unquoted form at least fails loudly
(`column u.id does not exist`); a bare `FROM system_user` silently returns one
wrong row.

It is the only one of the 49 tables whose name collides with a `pg_catalog`
function. To re-check after a future major bump:

```sql
SELECT t.tablename
FROM pg_tables t
JOIN pg_proc p ON p.proname = t.tablename
             AND p.pronamespace = 'pg_catalog'::regnamespace
WHERE t.schemaname = 'public';
```
