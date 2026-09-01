# Feature Design Document

## Feature: `administration_csv_seeder` — bootstrap a workspace hierarchy from CSV

**Task ID**: SEED-002
**Author**: Iwan Firmawan
**Date**: 2026-08-31
**Status**: Draft

---

## 1. Context & Problem Statement

```
Currently, there are three ways to get an administration hierarchy, and none
of them works for "give this workspace a hierarchy from a file":

1. administration_seeder (no --source)
   Reads ./source/{COUNTRY_NAME}.topojson with COUNTRY_NAME hardcoded to
   "fiji" (mis/settings.py:289). Writes tenant=None. One country, one
   install, no workspace targeting.

2. administration_seeder --test
   Seeds DEFAULT_ADMINISTRATION_DATA — five hardcoded Indonesian rows used by
   30+ tests. A closed fixture, not an import path.

3. Excel bulk upload (api/v1/v1_jobs/administrations_bulk_upload.py)
   Correct and tenant-aware, but CANNOT create Levels. map_column_model
   resolves each header to an EXISTING level by primary key:

       obj = model.objects.get(id=id, tenant=tenant)   # :142

   So the levels must already exist before the file can be parsed.

Goal:
- One command that takes a CSV and gives a named workspace a complete
  hierarchy — Levels and Administrations both — in a single step.
```

### Why this is blocking

`configure_project` (`v1_users/views.py:496-503`) is the whole of what a new
workspace gets: one `Levels(level=0)` and one root `Administration`. To get
anything below the root today, an operator must:

1. register the workspace
2. complete `configure_project`
3. create each level through the MT-005 level-management UI
4. download the generated Excel template
5. fill it in
6. upload and wait for the validation job

Six steps, one of which is a browser-only UI, before a developer can seed a
single datapoint. [SEED-001](SEED-001-fake-data-prefix-and-clean.md) works
around this with a `DUMMY-` throwaway hierarchy (D-10 there), which is right
for disposable test data and wrong for a workspace anyone intends to keep.

---

## 2. Requirements

### User Acceptance Criteria

- [ ] `--source <file.csv> --tenant <subdomain>` creates every level and every
      administrative unit described by the file, in one command.
- [ ] The CSV is authored by hand in a spreadsheet — no template download, no
      level ids to look up.
- [ ] Re-running the same file against the same workspace changes nothing
      (idempotent).
- [ ] Rows are validated before any write; a bad file fails with the offending
      row and column named, and writes nothing.
- [ ] Works for any country. No `COUNTRY_NAME`, no bundled data file.

### Technical Acceptance Criteria

- [ ] Every `Levels` and `Administration` row carries the target `tenant`.
- [ ] Unit lookup is disambiguated by parent, not by name alone — two units
      with the same name under different parents stay distinct.
- [ ] `Administration.path` is correctly populated on every created row, since
      it is what every visualization administration filter reads
      (`v1_visualization/functions.py:28-43`).
- [ ] Whole import runs in one `transaction.atomic()`.
- [ ] `--tenant` is required and rejects an unknown subdomain before any read
      of the CSV (R-4).
- [ ] `seed_administrations()` is called **unchanged** — no new parameters, no
      fork (R-1).
- [ ] The CSV is read from `STORAGE_PATH`, and no country data file is added to
      the repository (R-3).
- [ ] `administration_seeder` is not modified — its 30+ test callers keep
      working unchanged (D-7).
- [ ] `flake8` clean.

---

## 3. Data Model Changes

### New Models

None.

### Modified Models

| Model | Change | Reason |
|-------|--------|--------|
| — | — | No model changes. `Levels` and `Administration` already carry everything needed. |

### Migration Strategy

```python
# No migration.
#
# Explicitly rejected: Administration.geo. See D-6 — the dashboard map reads
# FormData.geo, never an administration's own coordinates, so the field would
# be written by this command and read by nothing.
```

---

## 4. CLI Contract

### Arguments

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `-s, --source` | str | **required** | CSV path, resolved against `STORAGE_PATH` first (R-3) |
| `-t, --tenant` | str | **required** | Target workspace subdomain. `default` exists on any migrated database (R-4) |
| `--rename-root` | bool | `False` | Allow the level-0 column to rename the workspace's existing root (D-4) |
| `--dry-run` | bool | `False` | Validate and report; write nothing |

### CSV format

Header grammar — one pair of columns per tier:

```
{level}_{LevelName}      the unit's name at that tier;
                         {LevelName} also names the Levels row
{level}_Code             optional code for that tier
```

```csv
0_National,0_Code,1_Province,1_Code,2_District,2_Code
Indonesia,ID,Central Java,CJ,Semarang,CJ-SMG
Indonesia,ID,Central Java,CJ,Solo,CJ-SLO
Indonesia,ID,Yogyakarta,YK,Sleman,YK-SLM
```

Produces:

```
Levels:  (0, "National")  (1, "Province")  (2, "District")

Administration:
  Indonesia [ID]                          level 0, parent None
  └── Central Java [CJ]                   level 1
  │   ├── Semarang [CJ-SMG]               level 2
  │   └── Solo [CJ-SLO]                   level 2
  └── Yogyakarta [YK]                     level 1
      └── Sleman [YK-SLM]                 level 2
```

Rules:

- Rows are **denormalised** — every row is a complete root-to-leaf path, so
  parent tiers repeat. Repeats are get-or-created, not duplicated.
- Levels must be contiguous from 0. A file with `0_`, `1_`, `3_` is rejected.
- `{level}_Code` is optional; omit the column entirely or leave cells blank.
- A blank name cell truncates that row's path at that tier — the row still
  creates its ancestors. This matches the bulk upload's `break`
  (`administrations_bulk_upload.py:50-51`).
- Column order in the file does not matter; the level number in the header
  determines the tier.

### Where the CSV lives

`--source` resolves against `STORAGE_PATH` (`mis/settings.py:257`, default
`./storage`) before falling back to a literal filesystem path. Country files
are operator data, not repository content, and `backend/storage/.gitignore` is
`*` / `!.gitignore` — a self-ignoring directory — so anything dropped there can
never be committed by accident. See R-3.

```python
def resolve_source(source):
    """Storage-relative first, literal path second.

    Storage is the intended home: country files are operator data, are
    often large, and must not be committed. The literal fallback keeps
    `--source ./tmp/scratch.csv` working while iterating.
    """
    if storage.check(source):
        return f"{settings.STORAGE_PATH}/{source}"
    if os.path.isfile(source):
        return source
    raise CommandError(
        f"'{source}' not found in storage ({settings.STORAGE_PATH}/) "
        f"or as a file path. Copy the CSV into "
        f"{settings.STORAGE_PATH}/administrations/ and pass "
        f"'administrations/{os.path.basename(source)}'."
    )
```

### Invocations

```bash
# Give the 'acme' workspace an Indonesian hierarchy.
# File sits at backend/storage/administrations/indonesia.csv — gitignored.
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source administrations/indonesia.csv --tenant acme

# Check the file without touching the database
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source administrations/indonesia.csv --tenant acme --dry-run

# Single-host install: 'default' exists on any migrated database (R-4)
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source administrations/kenya.csv --tenant default

# Literal path, for iterating on a file you have not filed yet
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source ./tmp/scratch.csv --tenant acme --dry-run
```

### Output contract

```
-- Validating ./source/indonesia.csv
   Levels detected: 0 National, 1 Province, 2 District
   Rows: 514
-- Levels:          3 created, 0 reused
-- Administrations: 548 created, 0 reused
-- Done
```

Validation failure writes nothing:

```
CommandError: Row 12, column '2_District': blank name with a non-blank
              descendant '3_Village'. A path cannot skip a tier.
```

---

## 5. Decision Log

### D-1: New command, not `administration_seeder --source`

**Options Considered**:

1. Add `--source` to `administration_seeder`.
2. A new `administration_csv_seeder`.

**Decision**: Option 2.

**Rationale**: `--source` would route through `seed_administration()`, which
carries three defects that this feature must not inherit:

```python
# administration_seeder.py:67-74 — the upsert key is `name` ALONE.
Administration.objects.update_or_create(
    name=name,                 # no parent, no level, no tenant
    defaults={"level": level, "code": code, "parent": parent},
)
```

- Two units with the same name under different parents collapse into one row,
  and the last row processed wins the `parent`. Any real country file repeats
  names across regions.
- No `tenant` anywhere, so combined with `unique_root_administration_per_tenant`
  the command can only ever build one hierarchy per install.
- `path` goes stale: `set_administration_path` returns early on
  `if instance.path: return` (`v1_profile/models.py:98-105`), so a row
  reparented by the first defect keeps its old ancestry — and `path` is what
  every visualization administration filter reads. The failure is a silently
  wrong aggregate, not an error.

Fixing all three means rewriting the function, after which the only thing left
in `administration_seeder` is the Fiji topojson reader and the `--test`
fixture. The two commands also mean genuinely different things — "seed the
bundled country data" versus "import this file into this workspace" — with
different tenancy and different idempotency. Overloading one command with both
is how `--test` / `--clean` / `--source` / `--file` start contradicting each
other.

**Impact**: `administration_seeder` is untouched; its 30+ test callers are
unaffected. Deprecating it is a later decision (D-7).

---

### D-2: Header grammar — level-prefix, not level-suffix or id-pipe

Three conventions now exist in the codebase. This picks a fourth, deliberately.

| Where | Format | Example |
|---|---|---|
| `administration_seeder` + topojson | `{Alias}_{level}`, `code_{level}` | `Province_1`, `code_1` |
| Bulk-upload template (`utils/upload_administration.py:25-28`) | `{level.id}\|{level.name}` | `2\|Province`, `2\|Province Code` |
| **This command** | `{level}_{Alias}`, `{level}_Code` | `1_Province`, `1_Code` |

**Decision**: level-prefix with `_`.

**Rationale**:

*Against the suffix form.* It is parsed by taking the last underscore-delimited
fragment and asking whether it is a digit:

```python
# administration_seeder.py:111-116
geo_config = [
    key for key in geo_config if (
        key.split("_")[-1].isdigit() and not key.startswith("code_")
    )
]
```

Any level alias containing an underscore or ending in a digit is silently
misparsed or silently dropped — `Region_2` at level 1 becomes level 2. The
prefix form splits once on the first `_`, which is unambiguous regardless of
what the alias contains.

*Against the id-pipe form.* It encodes `Levels.id`, a database primary key, so
it presupposes the levels exist. That is the exact thing this command must not
require (D-5). It also cannot be authored by hand — an operator would have to
look up primary keys.

The prefix form carries both the **depth** and the **name** of each tier, which
is precisely the information needed to create the `Levels` rows.

**Known collision**: a level literally named `Code` produces a `1_Code` name
column indistinguishable from the level-1 code column. Validated and rejected
with a named error rather than silently mishandled.

```python
LEVEL_HEADER = re.compile(r"^(\d+)_(.+)$")

def parse_headers(columns):
    """{level: (name_column, alias, code_column_or_None)} from CSV headers."""
    levels, codes = {}, {}
    for col in columns:
        m = LEVEL_HEADER.match(col.strip())
        if not m:
            continue                      # attribute columns, ignored
        depth, alias = int(m.group(1)), m.group(2).strip()
        if alias.lower() == "code":
            codes[depth] = col
            continue
        if depth in levels:
            raise CommandError(
                f"Two name columns for level {depth}: "
                f"'{levels[depth][0]}' and '{col}'. A level named 'Code' "
                f"collides with the '{depth}_Code' column; rename it."
            )
        levels[depth] = (col, alias)
    if not levels:
        raise CommandError(
            "No level columns found. Headers must look like "
            "'0_National,0_Code,1_Province,1_Code'."
        )
    expected = list(range(len(levels)))
    if sorted(levels) != expected:
        raise CommandError(
            f"Levels must be contiguous from 0. Found {sorted(levels)}, "
            f"expected {expected}."
        )
    return {
        d: (col, alias, codes.get(d))
        for d, (col, alias) in levels.items()
    }
```

---

### D-3: Reuse the bulk-upload engine, do not write a third one

**Decision**: unit creation goes through
`api/v1/v1_jobs/administrations_bulk_upload.seed_administrations()`.

**Rationale**: it is already correct — parent-disambiguated, tenant-scoped, and
case-insensitive on the name:

```python
# administrations_bulk_upload.py:82-103
def seed_administrations(data, tenant=None):
    last_obj = None
    for item in data:
        level, name, code = item
        obj = Administration.objects.filter(
            Q(name__iexact=name), level=level,
            parent=last_obj, tenant=tenant,
        ).first()
        if not obj:
            obj = Administration.objects.create(
                name=name.title(), code=code, level=level,
                parent=last_obj, tenant=tenant,
            )
        last_obj = obj
    return last_obj
```

Its signature is exactly the tuple list this command builds — `[(Levels, name,
code), ...]` ordered root-first — so the new command is a header parser plus a
loop, not a new engine. It also gives idempotency for free: the second run
finds every row and creates nothing. And because it passes `parent=last_obj` to
`create()`, the `set_administration_path` receiver fires with a parent present
and `path` is populated correctly.

**Used unchanged — no new parameters, no fork** (R-1). The command builds the
`[(Levels, name, code), ...]` list its signature already expects and calls it.

**Consequence the reviewer must know about**: `seed_administrations` applies
`name.title()` on create (`administrations_bulk_upload.py:97`), so CSV values
are title-cased on the way in:

| CSV says | Stored as |
|---|---|
| `Central Java` | `Central Java` |
| `DKI Jakarta` | `Dki Jakarta` |
| `KwaZulu-Natal` | `Kwazulu-Natal` |

This is pre-existing behaviour of the shared helper, identical to what the
Excel upload path produces for the same input, and it is accepted here rather
than worked around. Adding a `normalize_name` flag was considered and rejected
as unnecessary surface: one code path, one behaviour, and the Excel path and
the CSV path agree with each other. If title-casing turns out to matter, fix it
once in `seed_administrations` for both callers — see §10.

---

### D-4: Level 0 must reconcile with the workspace's existing root

**Problem**: a tenant has exactly one root, enforced by the database:

```python
# v1_profile/models.py:92-99
models.UniqueConstraint(
    fields=["tenant"],
    condition=models.Q(parent__isnull=True),
    name="unique_root_administration_per_tenant",
)
```

`configure_project` already created it, named by the operator. If the CSV's
`0_National` column says `Indonesia` but the workspace root is `Acme Water`,
blindly creating the CSV's value raises `IntegrityError` at the end of a long
import.

**Options Considered**:

1. Error, naming both values.
2. Rename the existing root to the CSV's value.
3. Ignore the level-0 column and attach everything to the existing root.

**Decision**: Option 1 by default; option 2 behind `--rename-root`.

**Rationale**: a mismatch is far more likely to be the wrong file than a
deliberate rename, and the root's name appears throughout the UI and in every
`full_name` / `administration_column` string. Silently renaming it (option 2)
or silently discarding what the file says (option 3) both hide a
wrong-file-for-this-workspace mistake until someone notices the labels changed.

```python
root = Administration.objects.filter(
    tenant=tenant, parent__isnull=True
).first()
if root and not rename_root and root.name.lower() != csv_root.lower():
    raise CommandError(
        f"Workspace root is '{root.name}' but the file's level-0 column "
        f"says '{csv_root}'. Pass --rename-root to rename it, or check "
        f"you are importing the right file."
    )
```

If no root exists at all — a tenant-less install, or a workspace that never
completed `configure_project` — the level-0 value creates it.

---

### D-5: Levels are created from the headers

This is the capability that justifies a new command rather than reusing the
Excel path.

```python
def ensure_levels(header_map, tenant):
    """Levels for every tier in the file, created or reused.

    Keyed on (tenant, level), which is the unique constraint
    (v1_profile/models.py:27-32). The NAME is not part of the key: a
    workspace that already defined level 1 as "Province" keeps that name
    even if the file's header spells it "Provinsi", because roles and the
    upload template already reference it.
    """
    out = {}
    for depth, (_col, alias, _code) in sorted(header_map.items()):
        level, created = Levels.objects.get_or_create(
            tenant=tenant, level=depth, defaults={"name": alias},
        )
        out[depth] = (level, created)
    return out
```

**Deliberately not** `update_or_create`: renaming a level a workspace already
uses would silently change what its roles and its generated upload template
say. Reuse the existing name and report the divergence:

```
-- Levels: 2 created, 1 reused
   level 1 exists as 'Province'; file says 'Provinsi' (kept 'Province')
```

---

### D-6: No geo on administrations — `--bbox` stays on the data seeder

**Options Considered**:

1. `Administration.geo` JSONField, populated from a `--bbox` on this command.
2. Store the point as an `AdministrationAttributeValue`.
3. No administration geo; `fake_complete_data_seeder --bbox` generates points
   directly (SEED-001 D-9).

**Decision**: Option 3.

**Rationale**: the dashboard map does not read administration coordinates and
has no way to. Its endpoint is `/maps/geolocation/<form_id>` and its serializer
is bound to `FormData`:

```python
# v1_visualization/serializers.py:87-90
class GeoLocationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormData
        fields = ["id", "name", "geo", "administration_id"]
```

`useWidgetData.js:126-153` confirms the widget always requests the
**registration** form's geolocation, because `geo` is captured once when a site
is registered. An `Administration.geo` column would be written by this command
and read by nothing — a migration on a shared table to feed a consumer that
does not exist.

**Impact**: SEED-001 D-9 is unchanged. This command has no `--bbox`.

---

### D-7: `administration_seeder` is left alone

**Decision**: no change to `administration_seeder` in this task.

**Rationale**: 30+ test files call it with `--test`, and `seeder.sh` /
`seeder.prod.sh` call it bare. Touching it couples a risky refactor to a new
feature and makes the diff unreviewable. The three defects named in D-1 are
real and affect production data, but they are a separate task.

**Do the three defects in D-1 need fixing? No — this command retires them.**

They are not latent bugs in shared code; they live entirely inside
`seed_administration()`, which has exactly two kinds of caller:

| Caller | Fate |
|---|---|
| `seeder.sh` / `seeder.prod.sh` (bare — Fiji topojson) | Replaced by `administration_csv_seeder` |
| 30+ tests via `--test` (`DEFAULT_ADMINISTRATION_DATA`) | The only real dependency |

Nothing else imports it. So the correct follow-up is **deletion, not repair** —
fixing three defects in a command that is about to be replaced is work thrown
away twice. The `--test` fixture is the whole of what has to be dealt with, and
it is a fixture problem, not a correctness problem: those tests need five
hardcoded Indonesian rows in the database, and they do not care which code path
puts them there.

Note also that `administration_seeder` writes `tenant=None` and the
`default`-tenant backfill (`v1_users/0004_backfill_default_tenant.py`) only runs
**once, at migration time**. Rows it creates afterwards are never adopted, so
its output is already invisible to any properly-registered workspace. It only
makes sense in the legacy single-host mode.

Retirement is a follow-up, explicitly out of scope here — it fits the direction
of `feature/313-viz-009-legacy-dashboard-removal`, but bundling it would make
this diff unreviewable.

---

## 6. Type/Constant Mappings

| CSV header | Parsed as | Model field |
|---|---|---|
| `0_National` | depth `0`, alias `National` | `Levels.level=0`, `Levels.name="National"`, `Administration.name` |
| `0_Code` | code column for depth 0 | `Administration.code` |
| `1_Province` | depth `1`, alias `Province` | `Levels.level=1`, `Levels.name="Province"`, `Administration.name` |
| `1_Code` | code column for depth 1 | `Administration.code` |
| *(anything else)* | ignored | — |

---

## 7. Compatibility & Migration

### Backward Compatibility

- [x] Existing API consumers unaffected — no HTTP surface, no schema change.
- [x] Existing data preserved — the command only get-or-creates.
- [x] CLI tools still work — `administration_seeder`, `form_seeder` and
      `seeder.sh` are untouched (D-7).
- [x] **No shared code is modified.** `seed_administrations()` is called as-is
      (R-1), so its four existing call sites — `administrations_bulk_upload.py:64`
      and three in `tests_bulk_upload_tenant.py` — and the Excel upload path are
      untouched. This command adds files; it changes none.
- [x] No repository content added. Country CSVs live in the self-ignoring
      `backend/storage/` directory (R-3).

### Mobile App Impact

- [x] Sync endpoints affected: none directly. Administrations reach the device
      through the existing `generate_sqlite` path, which is unchanged.
- [x] SQLite schema changes: no.
- [ ] Devices already synced against a workspace hold the old hierarchy until
      their next `generate_sqlite` + resync. Run `generate_sqlite` after an
      import, as `seeder.sh` already does at the end of a seed.

### Seeder/CLI Compatibility

- [x] Existing seeders work.
- [ ] New seeder commands needed: `administration_csv_seeder`.
- [ ] Interaction with [SEED-001](SEED-001-fake-data-prefix-and-clean.md) D-10:
      the throwaway `DUMMY-` hierarchy is generated **only when the workspace
      has no administration below its root**. Running this command first means
      D-10 finds a real hierarchy and generates nothing, which is the intended
      relationship — SEED-002 for a workspace you keep, SEED-001 D-10 for one
      you do not.

---

## 8. Security Considerations

- [x] Permission model defined — management command, shell access only.
- [ ] **Input validation.** `--source` is an operator-supplied file path read
      with `pd.read_csv`. Validate the parsed header map and every row before
      the first write, and run the whole import inside one
      `transaction.atomic()` so a malformed row on line 400 leaves nothing
      behind.
- [x] No new attack vectors — no HTTP surface, nothing user-facing.
- [x] Not destructive. This command only creates. It has no `--clean`; removing
      administrations is `SEED-001 --clean` (for `DUMMY-` rows) or a manual
      operation, and is deliberately not offered here given the five PROTECT
      constraints pointing at `Administration` (documented in SEED-001 D-10).

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | `parse_headers` returns the right depth/alias/code map for a well-formed header row. |
| Unit | `parse_headers` rejects: non-contiguous levels, no level columns, and the `Code`-named-level collision (D-2). |
| Unit | Attribute-looking columns that do not match `^\d+_` are ignored, not errors. |
| Integration | A 3-tier, 4-row file creates the expected `Levels` and `Administration` counts, with repeated parent tiers reused rather than duplicated. |
| Integration | **Same name under different parents stays distinct** — `Central/Nasau` and `Western/Nasau` produce two rows. This is the D-1 defect the new command exists to avoid. |
| Integration | Every created administration has a correct `path`; `full_name` renders the whole ancestry (guards the D-3 receiver interaction). |
| Integration | Idempotency — running the same file twice creates nothing the second time. |
| Integration | Two tenants importing the same file get two independent hierarchies and neither can see the other's units via `for_user`. |
| Integration | Root mismatch raises `CommandError` and writes nothing; `--rename-root` renames instead (D-4). |
| Integration | An existing level keeps its name when the file's alias differs (D-5). |
| Integration | `--dry-run` reports counts and writes nothing. |
| Unit | Missing `--tenant`, or an unknown subdomain, fails before the CSV is opened; the error lists known subdomains (R-4). |
| Unit | `resolve_source` prefers storage over an identically-named local file, falls back to a literal path, and raises a `CommandError` naming both locations when neither resolves (R-3). |
| Unit | A file carrying attribute columns imports its hierarchy and ignores them without erroring (R-2). |
| Integration | Names are title-cased, matching the Excel path: `DKI Jakarta` → `Dki Jakarta`. Asserts the accepted R-1 behaviour so a later change to `seed_administrations` is caught here rather than in production. |

```python
# The D-1 regression — the reason this command exists.
def test_same_name_under_different_parents_stays_distinct(self):
    csv = (
        "0_National,1_Province,2_District\n"
        "Fiji,Central,Nasau\n"
        "Fiji,Western,Nasau\n"
    )
    call_command("administration_csv_seeder", "--source", self.write(csv))

    nasau = Administration.objects.filter(name__iexact="Nasau")
    self.assertEqual(nasau.count(), 2)
    self.assertNotEqual(
        nasau[0].parent_id, nasau[1].parent_id,
    )
    # And the paths must differ, or every viz administration filter
    # silently merges them.
    self.assertNotEqual(nasau[0].path, nasau[1].path)
```

---

## 10. Resolved Questions & Open Items

### Resolved

**R-1 · Use `seed_administrations()` unchanged. Keep it simple.**
No `normalize_name` parameter, no fork, no local reimplementation. The command
builds the tuple list the existing signature expects and calls it.

*This supersedes an earlier "store verbatim" position.* Using the helper as-is
means `name.title()` applies, so `DKI Jakarta` is stored as `Dki Jakarta` —
exactly what the Excel upload path already produces for the same input. One
code path, one behaviour, both callers agreeing. The trade is accepted
deliberately: see the table in D-3, and the follow-up in "Still open" if it
ever needs fixing for real.

**R-2 · No attribute columns in v1.**
The Excel path supports them via
`map_column_model(columns[level_count:], AdministrationAttribute, tenant)`
(`administrations_bulk_upload.py:31-35`), but attributes are the part of that
format that genuinely needs a generated template — the header must carry an
`AdministrationAttribute` primary key, which is not hand-authorable. Columns
that do not match `^\d+_` are ignored rather than rejected, so a file carrying
attribute columns still imports its hierarchy; the attributes are simply not
read. Revisit only if asked for.

**R-3 · CSVs live in storage, not in the repository.**
No `source/administrations/` directory is added. `--source` resolves against
`STORAGE_PATH` (`mis/settings.py:257`, default `./storage`) with a literal-path
fallback (§4).

The decisive property: `backend/storage/.gitignore` contains

```gitignore
*
!.gitignore
```

so the directory ignores its own contents. A country file dropped there cannot
be committed by accident, which is the stated requirement. `source/` has no
such guard, and committing a national administrative gazetteer — often tens of
thousands of rows — into the repository is not something a `.gitignore` entry
should be the only thing preventing.

*Implication for D-7*: porting `administration_seeder --test` onto this path
would need a **committed** fixture, which R-3 rules out of `storage/`. That
follow-up would have to either keep `DEFAULT_ADMINISTRATION_DATA` as a Python
constant and feed it through the same parser, or place one small fixture under
`api/v1/v1_profile/tests/fixtures/`. Noted, not decided here.

**R-4 · `--tenant` is required.**
Not optional, no tenant-less fallback. A hierarchy always belongs to a
workspace, and an unscoped import is the mistake this command exists to make
impossible.

```python
parser.add_argument(
    "-t", "--tenant", type=str, required=True,
    help="Workspace subdomain to import into.",
)

tenant = Tenant.objects.filter(
    subdomain=options["tenant"]
).first()
if not tenant:
    known = ", ".join(
        Tenant.objects.order_by("subdomain")
        .values_list("subdomain", flat=True)[:10]
    ) or "none"
    raise CommandError(
        f"No workspace with subdomain '{options['tenant']}'. "
        f"Known: {known}"
    )
```

A fresh database always has at least one usable value: migration
`v1_users/0004_backfill_default_tenant.py` runs
`Tenant.objects.get_or_create(subdomain="default")`, so `--tenant default` works
immediately after `migrate` with no registration flow. SEED-001 adopts the same
rule, with the same `--test` exemption it already applies to `--bbox`.

### Still open

- [ ] **`name.title()` in `seed_administrations`.** Accepted for now (R-1); the
      CSV and Excel paths agree, which is the property worth having. If it ever
      needs fixing, fix it in the shared helper for both callers and decide
      what to do about rows already stored title-cased. Not a blocker.

---

## 10b. Implementation Notes (deviations found while building)

### I-1: `settings.STORAGE_PATH`, not `storage.check()`

D-3's `resolve_source` snippet calls `storage.check(source)`. The shipped
code reads `settings.STORAGE_PATH` directly instead, because
`utils/storage.py` binds the value at import time:

```python
# utils/storage.py:1-2
import os
from mis.settings import STORAGE_PATH     # module-level binding
```

`override_settings(STORAGE_PATH=...)` therefore never reaches it, so
`storage.check()` and the path this command builds would disagree under
test — the check would look in the real storage directory while the join
pointed at the temporary one. One source of truth, and the resolver is
testable.

### I-2: the `Code`-named-level collision degrades, it does not raise

D-2 predicted `parse_headers` would reject a level literally named `Code`
with a "collides" message. It cannot: `1_Code` is claimed as level 1's
**code** column before any name column is considered, so level 1 simply has
no name column and the tier goes missing. The contiguity check reports it
instead:

```
Levels must be contiguous from 0. Found [0, 2], expected [0, 1]
```

Still rejected, still with a usable message, but by a different branch. The
duplicate-name branch that *is* reachable covers two name columns for one
tier (`1_Province` alongside `1_Region`), and its message was reworded to
say that rather than to blame `Code`. Both paths have a test.

### I-3: `csv`, not `pandas`

The Excel path uses pandas and is consequently littered with `pd.isnull()`
checks, because pandas turns an empty cell into `NaN`. `csv.DictReader`
gives back empty strings, so "blank means truncate here" is a plain falsy
check. `utf-8-sig` is used so a spreadsheet-exported BOM does not become
part of the first header's name.

---

## 11. References

- Related tasks:
  - [SEED-001 Fake data prefix and clean](SEED-001-fake-data-prefix-and-clean.md) — D-10 throwaway hierarchy, D-9 `--bbox`
  - [MT-005 Level management CRUD](MT-005-level-management-crud.md) — the UI path this command shortcuts
  - [MT-007 Administration bulk upload hardening](MT-007-administration-bulk-upload-hardening.md) — the Excel path
  - [MT-002 Tenant scoping (database)](MT-002-tenant-scoping-database.md)
- Prior art:
  - `api/v1/v1_jobs/administrations_bulk_upload.py` — `seed_administrations()`, reused wholesale (D-3)
  - `api/v1/v1_profile/management/commands/administration_seeder.py` — the legacy path and its three defects (D-1)
  - `utils/upload_administration.py:20-47` — the id-pipe header convention rejected in D-2

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-08-31 | Draft |
| Tech Lead | | | |
| Product | | | |
