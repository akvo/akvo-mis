# Feature Design Document

## Feature: Tenant-aware seeders — marked fake data, CSV hierarchies, and pins that match

**Task IDs**: SEED-001, SEED-002, SEED-003 (one PR, one plan)
**Author**: Iwan Firmawan
**Date**: 2026-08-31 → 2026-09-02
**Branch**: `feature/89-tenant-aware-seeders` → `main`
**Status**: Implemented; pending review

---

## 0. How to read this

Three pieces of work that ship together, because each is unusable without the
one before it. They are kept as three parts rather than flattened, so the
decision IDs already cited in the code comments still resolve.

| Part | Task | What it does | Command |
|---|---|---|---|
| **1** | SEED-001 | Marks generated data `DUMMY-` and gives it a teardown | `fake_complete_data_seeder --clean` |
| **2** | SEED-002 | Imports a real hierarchy — levels *and* units — from a CSV | `administration_csv_seeder` |
| **3** | SEED-003 | Makes a generated pin land inside the unit it belongs to | (no new command) |

**Decision IDs are per-part.** Part 1's `D-6` and Part 2's `D-6` are different
decisions; cross-part references are always written out ("Part 3 D-9").

Three decisions were **reversed while building**, because Part 3 undid choices
Parts 1 and 2 made before the boundary pipeline existed. They are not deleted —
they explain why the middle commits of this branch look the way they do — but
they are moved to [the appendix](#appendix-decisions-reversed-during-this-work)
so the decision log reads as the shipped design.

---

## 1. Context & Problem Statement

```
Three things were true before this work and are not now.

1. Seeded data was indistinguishable from real submissions, and could not
   be removed.
   - fake_complete_data_seeder wrote FormData that is byte-identical in
     shape to a real submission. Nothing on the row, in the UI or in the
     API said "this was generated".
   - The only teardown was dropping the database, which also destroyed the
     hierarchy, forms, roles and users that a full ./seeder.sh run built.
   - So the seeder was usable only on a throwaway local DB -- not on the
     shared dev/staging workspace where dashboard debugging happens.

2. No seeder could target a workspace, and getting a hierarchy into one
   took six manual steps.
   - administration_seeder read ./source/{COUNTRY_NAME}.topojson with
     COUNTRY_NAME hardcoded to "fiji", and wrote tenant=None.
   - The Excel bulk upload is tenant-aware and correct, but CANNOT create
     Levels: map_column_model resolves each header to an EXISTING level by
     primary key, so the levels must exist before the file can be parsed.
   - Which left: register, configure, create each level through a
     browser-only UI, download the template, fill it in, upload, wait.

3. A generated datapoint's pin had no relationship to the unit it named.
   - The seeder picked an administration and a coordinate one line apart:

         adm = targets[index]
         geo_value = random_point_in(bbox)

   - A datapoint reading "Aceh - Acehbarat - Meureubo" (Sumatra, ~4N 96E)
     carried geo [-8.76, 118.94] -- Sumbawa, about 2,000 km away.
   - Most pins were not even on land. India's country box against its real
     polygons: 34% land, 66% sea.
```

**Goal**: `./seeder.sh --tenant acme` builds a workspace a developer can open a
dashboard against, and undo.

This unblocks item 1 of the visualization debugging gap analysis
([MT-002](MT-002-tenant-scoping-database.md)): a `--tenant` flag is only usable
if there is also a way to undo a run that landed in the wrong workspace.

---

## 2. Requirements

### User Acceptance Criteria

**Part 1 — marking and teardown**

- [x] Every seeded datapoint name starts with `DUMMY-` in Manage Data, the
      dashboard viewer, map popups and Excel/DOCX exports.
- [x] Every seeded account is recognisable by email (`dummy-…@test.com`), and
      every seeded mobile assignment name starts with `DUMMY-`.
- [x] `fake_complete_data_seeder --clean` removes all generated data, reports
      what it deleted, and is a no-op the second time.
- [x] `--clean` wipes and **exits**. It never reseeds, and needs only
      `--tenant`.
- [x] `--help` states plainly that the default run produces approved data only
      — no drafts, no pending rows, no approver accounts (Part 1 D-8).
- [x] `--approved true --draft true` fails with a clear message instead of
      silently seeding drafts (Part 1 D-8).

**Part 2 — hierarchy import**

- [x] `--source <file.csv> --tenant <subdomain>` creates every level and every
      unit in one command.
- [x] The CSV is authored in a spreadsheet — no template download, no level ids
      to look up.
- [x] Re-running the same file against the same workspace changes nothing.
- [x] Rows are validated before any write; a bad file names the offending row
      and column, and writes nothing.
- [x] Works for any country. No `COUNTRY_NAME`, no bundled data file.

**Part 3 — pins**

- [x] Generated pins cluster over the units their datapoints name.
- [x] The operator passes no coordinates on the command line.
- [x] The bounding box is visible in the administration UI as an ordinary
      attribute, editable and deletable like any other.
- [x] A workspace whose hierarchy carries no boxes gets an error naming the
      command to run, rather than submissions with no coordinates.

### Technical Acceptance Criteria

- [x] **No schema migration anywhere in this PR.** No new column on `form_data`
      or any other hot table (Part 1 D-1); no new model or field for the boxes
      (Part 3 D-2).
- [x] `--clean` performs a **hard** delete — no `deleted_at`-stamped residue
      (Part 1 D-4).
- [x] `--clean` never deletes a `FormData` row the seeder did not create,
      **even when it reused a pre-existing real user as the submitter**
      (Part 1 D-2 — the sharp edge of this work).
- [x] The `DUMMY-` prefix survives `add_fake_answers`, which overwrites
      `data.name` (Part 1 D-3), and reaches the storage blob (R-2).
- [x] Answers, AnswerHistory and monitoring children go by database cascade,
      not a second queryset. Soft-deleted and draft rows from earlier runs are
      collected too.
- [x] `--clean` raises `CommandError` when `settings.DEBUG` is `False` (R-4).
- [x] `--tenant` is required outside `--test`, and every lookup is scoped by it
      — forms, levels, administrations, roles, organisations, created users.
- [x] Unit lookup is disambiguated by parent, not by name alone (Part 2 D-1).
- [x] `Administration.path` is populated on every created row — it is what
      every visualization administration filter reads.
- [x] `seed_administrations()` is called **unchanged** — no new parameters, no
      fork (Part 2 R-1).
- [x] CSVs are read from `STORAGE_PATH`; no country data file enters the repo
      (Part 2 R-3).
- [x] **Every generated datapoint has a `geo`.** The seeder refuses to run
      rather than writing a row without one (Part 3 D-9).
- [x] `FormData.geo` stays `null=True` in the schema — real submissions may
      legitimately lack a coordinate. The guarantee is a property of the
      seeder, not of the column.
- [x] The notebook writes each unit's box from its largest-area ring, so no
      stored box spans the antimeridian (Part 3 D-7).
- [x] Nothing new reaches the mobile SQLite (Part 3 D-2).
- [x] `--test` is untouched: 35 existing callers keep working.
- [x] `flake8` clean.

---

## 3. Data Model Changes

### New Models

None, in any of the three parts.

### Modified Models

| Model | Change | Reason |
|---|---|---|
| — | — | No model changes. Fake data is marked in existing `name`/`email` text columns; bounding boxes reuse `AdministrationAttribute`. |

### Migration Strategy

```python
# No migration in this PR. Two alternatives were considered and rejected:
#
# 1. FormData.is_fake = BooleanField(default=False)
#    `form_data` is the largest table in the schema and is on the mobile sync
#    path. A column with a default rewrites the table on Postgres < 11 and
#    adds a field to every sync payload -- a permanent production cost for a
#    development-only concern. See Part 1 D-1.
#
# 2. Administration.geo = JSONField(null=True)
#    Needs a migration AND an explicit exclusion from mobile sync, because
#    generate_sqlite exports every model field automatically. An
#    AdministrationAttribute needs neither. See Part 3 D-2.
```

### New constants

```python
# backend/api/v1/v1_data/constants.py

# Marker for seeder-generated rows. Anything carrying this prefix is fair
# game for `fake_complete_data_seeder --clean`, so never apply it to a row a
# human might have authored.
DUMMY_PREFIX = "DUMMY-"

# Seeded accounts are additionally namespaced by email so the clean can find
# them without depending on first/last name, which Faker randomises.
DUMMY_EMAIL_PREFIX = "dummy-"
DUMMY_EMAIL_DOMAIN = "@test.com"
```

```python
# backend/api/v1/v1_profile/constants.py

# The administration attribute carrying a unit's bounding box, as
# "minLng,minLat,maxLng,maxLat". User-visible: it appears in the attribute
# manager alongside real attributes like "Population".
BBOX_ATTRIBUTE_NAME = "Bounding Box"

# CSV column prefix naming an administration attribute. The Excel path keys
# columns as "<id>|<Name>" and looks them up by primary key, which a notebook
# cannot do -- it has no database ids -- so the CSV path is name-keyed.
ATTRIBUTE_COLUMN_PREFIX = "attr_"
```

### New module

`backend/api/v1/v1_profile/bbox.py` — one parser and one set of error messages,
shared by the CSV importer (which validates and writes boxes) and the data
seeder (which reads them). `parse_bbox`, `random_point_in`, `format_bbox`,
`get_bbox_attribute`, `resolve_bbox`, and a `BboxError(ValueError)` so the
module stays importable outside a management command.

---

## 4. CLI Contract

This work adds no HTTP endpoints. The equivalent contract is the management
commands' argument surface.

### `administration_csv_seeder` (Part 2)

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `-s, --source` | str | **required** | CSV path, resolved against `STORAGE_PATH` first (R-3) |
| `-t, --tenant` | str | **required** | Target workspace subdomain. `default` exists on any migrated database (R-4) |
| `--rename-root` | flag | `False` | Allow the level-0 column to rename the workspace's existing root (Part 2 D-4) |
| `--dry-run` | flag | `False` | Validate and report; write nothing |

#### CSV format

One pair of columns per tier, plus optional attribute columns:

```
{level}_{LevelName}    the unit's name at that tier; {LevelName} also names
                       the Levels row
{level}_Code           optional code for that tier
attr_{Attribute Name}  optional; an administration attribute on the row's
                       deepest unit
```

```csv
0_National,0_Code,1_Province,1_Code,2_District,2_Code,attr_Bounding Box
Indonesia,ID,Central Java,CJ,Semarang,CJ-SMG,"110.2,-7.1,110.5,-6.9"
Indonesia,ID,Central Java,CJ,Solo,CJ-SLO,"110.7,-7.7,110.9,-7.5"
Indonesia,ID,Yogyakarta,YK,Sleman,YK-SLM,"110.3,-7.8,110.5,-7.6"
```

Produces:

```
Levels:  (0, "National")  (1, "Province")  (2, "District")

Administration:
  Indonesia [ID]                          level 0, parent None
  ├── Central Java [CJ]                   level 1
  │   ├── Semarang [CJ-SMG]               level 2   + Bounding Box
  │   └── Solo [CJ-SLO]                   level 2   + Bounding Box
  └── Yogyakarta [YK]                     level 1
      └── Sleman [YK-SLM]                 level 2   + Bounding Box
```

Rules:

- Rows are **denormalised** — every row is a complete root-to-leaf path, so
  parent tiers repeat. Repeats are get-or-created, not duplicated.
- Levels must be contiguous from 0. A file with `0_`, `1_`, `3_` is rejected.
- `{level}_Code` is optional; omit the column or leave cells blank.
- A blank name cell truncates that row's path at that tier — the row still
  creates its ancestors. This matches the bulk upload's `break`.
- Column order does not matter; the level number in the header decides the tier.
- `attr_` columns are optional. A CSV without them imports byte-identically to
  before this change.

#### Invocations

```bash
# Validate the whole file and roll back
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source=administrations/indonesia.csv --tenant=acme --dry-run

# Import
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source=administrations/indonesia.csv --tenant=acme
```

```
-- Validating ./storage/administrations/indonesia.csv
   Levels detected: 0 National, 1 Province, 2 District
   Attributes detected: Bounding Box
   Rows: 514
-- Levels:          3 created, 0 reused
-- Administrations: 548 created
-- Attribute values: 514 written
-- Done
```

Validation failure writes nothing:

```
CommandError: Row 12, column '2_District': blank name with a non-blank
              descendant '3_Village'. A path cannot skip a tier.
```

### `fake_complete_data_seeder` (Parts 1 and 3)

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `-t, --tenant` | str | **required** (unless `--test`) | Workspace subdomain to seed into |
| `-r, --repeat` | int | `5` | Registrations per form |
| `-m, --monitoring` | int | `2` | Monitoring submissions per registration |
| `--approved` | bool | `True` | `true`: every row approved — no pending rows, no approver accounts. `false`: half of each form's rows left pending, approver tree built |
| `--draft` | bool | `False` | Also create drafts. Contradicts `--approved=true` |
| `--clean` | bool | `False` | Hard-delete every `DUMMY-` row this workspace owns, then **exit** |
| `--test` | bool | `False` | Bundled `TEST_GEO_DATA` fixture; exempt from `--tenant` |

`--clean` follows the boolean-parsing convention already used by `--approved`
and `--draft` on this command, **not** the `nargs="?" const=1 type=int` style
used by `administration_seeder --clean` (Part 1 D-7).

**There is no `--bbox`.** Coordinates come from the hierarchy — see Part 3.

```bash
# Seed 20 registrations with 3 monitoring rounds each
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    --tenant=acme --repeat=20 --monitoring=3 --approved=true

# Wipe. Terminal on purpose (Part 1 D-9b).
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    --tenant=acme --clean

# Reset = the two above, chained.
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    --tenant=acme --clean && \
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    --tenant=acme --repeat=20
```

```
-- Cleaning fake data
   FormData             340
   MobileAssignment      12
   SystemUser            12
   Administration         0
   Levels                 0
-- Fake data cleared
```

A workspace with no geography fails before any write:

```
CommandError: None of this workspace's administrations carry a 'Bounding Box'
              attribute, so generated datapoints would have no map coordinates.
              Re-import the hierarchy from a CSV carrying an 'attr_Bounding Box'
              column -- the notebook in scripts/administration_csv_generator/
              writes one by default:
                python manage.py administration_csv_seeder
                  --source=administrations/<file>.csv --tenant=<subdomain>
```

---

## 5. Decision Log

### Part 1 — Marked fake data (SEED-001)

#### D-1: How is a row marked as fake?

**Options**: (1) name prefix in existing text columns; (2) a `FormData.is_fake`
boolean; (3) a dedicated `Tenant(subdomain="dummy")`.

**Decision**: option 1, name prefix.

**Rationale**: the user-facing half of the requirement — "tell real from fake at
a glance" — is only satisfied by option 1. A boolean is invisible in Manage
Data, in a dashboard widget, in a map popup and in an Excel export unless every
one of those surfaces is taught to render it, which is a far larger change than
the seeder. Option 2 also costs a migration on the largest table in the schema,
on the mobile sync path, permanently, for a development-only concern.

Option 3 is the right long-term answer once tenancy is everywhere, because
`Tenant` is a real referential boundary rather than a string convention. It was
rejected because at the time no seeder was tenant-aware, so a "dummy tenant"
would have had no hierarchy, no forms and no roles to hang off. D-6 addresses
the underlying gap.

**Impact**: no migration. The delete key becomes a string prefix, which carries
the false-positive risk D-2 addresses.

#### D-2: The delete key is the name prefix, never the creating user

*The most important decision here, and the one most worth reviewing.*

**Options**: (1) delete by `FormData.name__startswith="DUMMY-"`; (2) delete the
seeded users and let `created_by` cascade.

Option 2 looks strictly better at first — `FormData.created_by` is
`on_delete=CASCADE`, so deleting the users removes every row they authored
including monitoring children and drafts, with no dependence on what
`add_fake_answers` did to the name.

**Decision**: option 1.

**Rationale**: **the seeder does not always create its submitter.** It reuses
any existing user who matches:

```python
user = SystemUser.objects.filter(
    **filter_submitter,
    user_user_role__administration=parent_adm,
    tenant=tenant,
).exclude(password__exact="").order_by("?").first()
if not user:
    # ... only here is a new user created
```

On any workspace that already has real submitters, `filter_submitter` matches
them, `.order_by("?").first()` picks one, and the fake datapoints are attributed
to **a real person's account**. Option 2 would then hard-delete that account and
cascade away every genuine submission they ever made — unrecoverable data loss,
triggered by a flag whose name promises cleanup.

Option 1 cannot do this. Its worst case is that a real datapoint whose name
genuinely begins with `DUMMY-` is removed, which requires a human to have typed
that prefix into a meta field.

**Impact**: `created_by` cannot be the delete key, so the prefix *must* be
applied to every `FormData` row including drafts. User cleanup becomes a
separate, guarded step (D-5).

#### D-3: The prefix is stamped after `add_fake_answers`, before `save_to_file`

**Decision**: not at `FormData.objects.create()`.

**Rationale**: a prefix set at `create()` is silently discarded.
`add_fake_answers` rebuilds `data.name` from the form's `meta` questions and
overwrites whatever the caller set:

```python
# v1_data/functions.py
if len(meta_name) > 0:
    name = " - ".join(meta_name)
    if len(name.strip()):
        data.name = name          # clobbers the prefix set at create()
data.save()
```

Any form with at least one `meta: true` question — which is every registration
form in `source/forms/` — loses the prefix. The datapoint then looks real *and*
is invisible to `--clean`: the worst of both, failing silently.

There is a second constraint on the other side. `save_to_file` is a
`@property`, so the bare attribute access **does execute**, and it serialises
`self.name` into a JSON blob uploaded to storage that mobile debugging reads
(R-2). So the stamp lands strictly between the two.

```python
def mark_as_dummy(form_data):
    """Stamp the fake-data prefix, idempotently.

    MUST be called after add_fake_answers(), which rebuilds `name` from the
    form's meta questions and would otherwise discard the prefix, and before
    `save_to_file`, which serialises the name into the storage blob that
    mobile debugging reads.
    """
    if form_data.name.startswith(DUMMY_PREFIX):
        return form_data
    form_data.name = f"{DUMMY_PREFIX}{form_data.name}"
    form_data.save(update_fields=["name"])
    return form_data
```

#### D-4: Hard delete, not soft

**Decision**: `.hard_delete()`.

**Rationale**: `FormData` extends `SoftDeletes`, whose queryset `delete()` is an
`UPDATE`, not a `DELETE`. A bare `.delete()` would leave every row in
`form_data`, still reachable through `objects_with_deleted`, still counted by
anything using a raw manager, and still occupying the `submission_key` unique
index. `--clean` would appear to work while the table grew monotonically.

Hard delete goes through Django's collector, which issues plain `DELETE`s and
does **not** call each child model's overridden `delete()` — which is what we
want: monitoring children (`FormData.parent`), `Answers` and `AnswerHistory`
are removed for real, one statement each.

#### D-5: What `--clean` deletes, in order

Five tiers. Tiers 4 and 5 exist because of the throwaway hierarchy, which Part 3
retired — see the appendix — but the ordering logic remains, since a workspace
seeded by an earlier commit on this branch may still hold `DUMMY-` units.

```python
# Tier 1 -- datapoints. objects_with_deleted, not objects: the default manager
# hides soft-deleted rows, so fake rows soft-deleted by an earlier run would
# survive every subsequent --clean. Drafts are in the same queryset.
# Monitoring children cascade via FormData.parent; Answers and AnswerHistory
# via their `data` FK.
fake_data = FormData.objects_with_deleted.filter(
    name__startswith=DUMMY_PREFIX, form__tenant=tenant
)
fake_data.hard_delete()

# Tier 2 -- mobile assignments. Deleting them before their users keeps the
# reported counts honest and covers assignments attached to a REUSED real
# user, which tier 3 must not touch.
MobileAssignment.objects.filter(
    name__startswith=DUMMY_PREFIX, user__tenant=tenant
).delete()

# Tier 3 -- seeded accounts, guarded. Only accounts the seeder minted, and
# only those with no surviving FormData. This guard is what makes D-2's
# "reused a real user" scenario safe.
SystemUser.objects_with_deleted.filter(
    email__startswith=DUMMY_EMAIL_PREFIX,
    email__endswith=DUMMY_EMAIL_DOMAIN,
    tenant=tenant,
).exclude(form_data_created__isnull=False).hard_delete()

refresh_materialized_data()   # see I-3

# Tiers 4-5 -- generated administrations deepest-first, then their levels.
```

**Explicitly not deleted**:

| Not deleted | Reason |
|---|---|
| `Administration` / `Levels` without `DUMMY-` | Real hierarchy, whether CSV-imported or bulk-uploaded |
| **`Bounding Box` attributes and values** | They belong to the hierarchy, not to the generated data, and carry no prefix (Part 3) |
| `Forms`, `Questions`, `QuestionOptions` | Owned by `form_seeder`; deleting them would break real data |
| `Organisation` | The seeder only reads it, never creates one |
| `Role`, `UserRole`, `UserForms` | Cascade from `SystemUser` in tier 3 |
| `Entity` / `EntityData` | Created by `set_answer_data` via `get_or_create` and shared with real submissions — accepted, R-3 |
| Storage blobs (`datapoints/{uuid}.json`) | Deliberately kept: `DUMMY-` data is also used for mobile debugging, which reads these — R-2 |

#### D-6: `--tenant` is required, and `--clean` is tenant-scoped

**Decision**: required outside `--test`, and every lookup the command makes is
scoped by it.

**Rationale**: `FormData`'s tenant is derived, not stored
(`TENANT_PATH = "form__tenant"`). An unscoped clean on a multi-workspace install
would delete another workspace's fake data — a smaller version of the same class
of accident D-2 guards against.

A fresh database always has a usable value: migration
`v1_users/0004_backfill_default_tenant.py` runs
`Tenant.objects.get_or_create(subdomain="default")`.

**Impact**: every previously unscoped lookup in the command becomes
tenant-scoped, which also closes finding F-1 from the visualization gap
analysis — `Forms.objects.filter(parent__isnull=True)`,
`Organisation.objects.order_by("?")`, `Role.objects.filter(...)` and both
`create_user` calls, which minted users with `tenant=None`.

`resolve_tenant` was extracted to `backend/utils/tenant_command.py` so the
other commands share one lookup and one error message.

#### D-7: `--clean` is a bool, not `nargs="?" type=int`

**Decision**: match this command's own `--approved` / `--draft` parser, not
`administration_seeder --clean`.

**Rationale**: local consistency beats global consistency here. Every other flag
on *this* command already uses the boolean-string parser, and mixing the two
styles inside one `add_arguments` is how `--clean 0` ends up meaning "yes,
clean" to a tired reader.

#### D-8: No new "approved only" flag — it is already the default

**Requested**: a flag that seeds only approved data.

**Finding**: that behaviour already existed and was the default. With
`--approved true --draft false`, `data_is_draft` and `data_is_pending` are both
unconditionally `False`, the approver tree is built only `if not is_approved`,
and both flags land as literal `False` on the row. Nothing reintroduces approval
state: the command creates no `PendingDataApproval` / `DataApproval` rows, and
`v1_data` registers no `pre_save`/`post_save` signal on `FormData`.

**Decision**: add no flag. Make two corrections instead.

1. **Fix the misleading help text.** `--approved` does not mean "create approved
   data"; it means "skip the approval workflow entirely". The old string invited
   the reader to look for a flag that `--approved` already *is*.
2. **Guard the contradictory combination.** `--approved true --draft true`
   silently produced drafts despite the first flag reading like a promise:

   ```python
   if is_approved and is_draft:
       raise CommandError(
           "--draft true contradicts --approved true: approved data has no "
           "drafts. Pass --approved false to seed a mixed workflow."
       )
   ```

**Rationale**: a second flag whose effect is identical to the existing default
is a flag that will drift out of sync with it. The reported problem is
discoverability, and discoverability is fixed by `--help`.

**Impact**: no behaviour change for anyone relying on the defaults.
`--approved true --draft true` changes from "silently seeds drafts" to a hard
error, which is the only backward-incompatible bit and is a bug fix. Five call
sites relied on the old behaviour and were updated to pass `--approved=false`,
which is what they meant (I-4).

#### D-9b: `--clean` is terminal

**Superseded**: the original contract had `--clean` wipe *then seed*, with
`--clean-only` for wipe-and-stop.

**Found in use**: an operator ran `--tenant qa1 --clean=true --bbox "..."`, saw
five datapoints in Manage Data afterwards, and reported "clean is not working".
The clean had worked perfectly — it deleted five rows and the same command then
created five more. The output gave no hint a second phase had started:

```
-- Fake data cleared
Created 5 data entries for form EPS Water Quality Testing
```

**Decision**: one flag. `--clean` hard-deletes and returns.

**Rationale**: `--clean` reads as an imperative. A command that quietly
repopulates afterwards is indistinguishable, from the outside, from a clean that
silently failed — and the person who has to tell them apart is the one who least
expects to. Two flags one word apart, where the *shorter* one does *more*, is
the trap that produced the report.

**Impact**: `--clean` requires only `--tenant`. It accepts both `--clean` and
`--clean=true`. The `refresh_materialized_data()` that ran only on the
`--clean-only` path now runs on every clean, which it always should have: the
view must not serve deleted datapoints.

---

### Part 2 — CSV hierarchy import (SEED-002)

#### D-1: A new command, not `administration_seeder --source`

**Decision**: a new `administration_csv_seeder`.

**Rationale**: `--source` would route through `seed_administration()`, which
carries three defects this feature must not inherit:

```python
# administration_seeder.py -- the upsert key is `name` ALONE.
Administration.objects.update_or_create(
    name=name,                 # no parent, no level, no tenant
    defaults={"level": level, "code": code, "parent": parent},
)
```

- Two units with the same name under different parents collapse into one row,
  and the last row processed wins the `parent`. Any real country file repeats
  names across regions.
- No `tenant` anywhere, so with `unique_root_administration_per_tenant` the
  command can only ever build one hierarchy per install.
- `path` goes stale: `set_administration_path` returns early on
  `if instance.path: return`, so a row reparented by the first defect keeps its
  old ancestry — and `path` is what every visualization administration filter
  reads. The failure is a silently wrong aggregate, not an error.

Fixing all three means rewriting the function, after which the only thing left
in `administration_seeder` is the topojson reader and the `--test` fixture. The
two commands also mean genuinely different things — "seed the bundled country
data" versus "import this file into this workspace" — with different tenancy and
different idempotency.

#### D-2: Header grammar — level-prefix, not level-suffix or id-pipe

Three conventions already existed. This picks a fourth, deliberately.

| Where | Format | Example |
|---|---|---|
| `administration_seeder` + topojson | `{Alias}_{level}`, `code_{level}` | `Province_1`, `code_1` |
| Bulk-upload template | `{level.id}\|{level.name}` | `2\|Province` |
| **This command** | `{level}_{Alias}`, `{level}_Code` | `1_Province`, `1_Code` |

**Against the suffix form.** It is parsed by taking the last underscore-delimited
fragment and asking whether it is a digit, so any alias containing an underscore
or ending in a digit is silently misparsed or dropped — `Region_2` at level 1
becomes level 2. The prefix form splits once on the first `_`, unambiguous
regardless of what the alias contains.

**Against the id-pipe form.** It encodes `Levels.id`, so it presupposes the
levels exist — the exact thing this command must not require (D-5). It also
cannot be authored by hand.

The prefix form carries both the **depth** and the **name** of each tier, which
is precisely what is needed to create the `Levels` rows.

**Known collision**: a level literally named `Code` produces a `1_Code` name
column indistinguishable from the level-1 code column. Rejected with a named
error — though by a different branch than predicted, see I-2.

#### D-3: Reuse the bulk-upload engine; do not write a third one

**Decision**: unit creation goes through
`api/v1/v1_jobs/administrations_bulk_upload.seed_administrations()`, unchanged.

**Rationale**: it is already correct — parent-disambiguated, tenant-scoped, and
case-insensitive on the name. Its signature is exactly the tuple list this
command builds, so the new command is a header parser plus a loop, not a new
engine. It gives idempotency for free, and because it passes `parent=last_obj`
to `create()`, the `set_administration_path` receiver fires with a parent
present and `path` is populated correctly.

**Consequence the reviewer must know about**: `seed_administrations` applies
`name.title()` on create, so CSV values are title-cased on the way in —
`DKI Jakarta` is stored as `Dki Jakarta`. This is pre-existing behaviour of the
shared helper, identical to what the Excel path produces for the same input, and
it is accepted rather than worked around. One code path, one behaviour, both
callers agreeing.

#### D-4: Level 0 must reconcile with the workspace's existing root

**Problem**: a tenant has exactly one root, enforced by
`unique_root_administration_per_tenant`. `configure_project` already created it,
named by the operator. If the CSV's `0_National` column says `Indonesia` but the
workspace root is `Acme Water`, blindly creating the CSV's value raises
`IntegrityError` at the end of a long import.

**Decision**: error by default, naming both values; rename behind
`--rename-root`.

**Rationale**: a mismatch is far more likely to be the wrong file than a
deliberate rename, and the root's name appears throughout the UI and in every
`full_name` / `administration_column` string. Silently renaming it, or silently
discarding what the file says, both hide a wrong-file mistake until someone
notices the labels changed.

If no root exists at all, the level-0 value creates it.

#### D-5: Levels are created from the headers

The capability that justifies a new command rather than reusing the Excel path.

```python
level, created = Levels.objects.get_or_create(
    tenant=tenant, level=depth, defaults={"name": alias},
)
```

Keyed on `(tenant, level)`, which is the unique constraint. **The name is not
part of the key**: a workspace that already defined level 1 as "Province" keeps
that name even if the file's header spells it "Provinsi", because roles and the
generated upload template already reference it. Deliberately not
`update_or_create`. The divergence is reported:

```
-- Levels: 2 created, 1 reused
   level 1 exists as 'Province'; file says 'Provinsi' (kept 'Province')
```

#### D-7: `administration_seeder` is left alone

**Decision**: no change to it in this work, beyond removing the dead
`seed_administration_prod()` path (§5 of the PR summary).

**Rationale**: 30+ test files call it with `--test`. Touching it couples a risky
refactor to a new feature. The three defects in D-1 are real, but this command
**retires** them rather than needing them fixed: they live entirely inside
`seed_administration()`, whose only callers are `seeder.sh` (replaced by
`administration_csv_seeder`) and the `--test` fixture. The correct follow-up is
deletion, not repair.

Note also that `administration_seeder` writes `tenant=None`, and the
`default`-tenant backfill runs **once, at migration time**. Rows it creates
afterwards are never adopted, so its output is already invisible to any properly
registered workspace.

---

### Part 3 — Pins that match their administration (SEED-003)

#### The measurement this part rests on

Two files, chosen because they fail differently: a large contiguous landmass and
a fragmented archipelago across the antimeridian. Points are drawn uniformly
from each box and ray-cast against the real polygons.

**India** — GADM level-2, 676 districts, 5,408 points:

| Points drawn from | Inside the **right** unit | On land **anywhere** |
|---|---|---|
| One country-wide box (before) | <1% | 34% |
| All of the unit's rings | 51% | 95% |
| The unit's **largest-area ring** | **51%** | **96%** |

**Fiji** — GADM level-2, 15 provinces, 3,000 points:

| Points drawn from | Inside the **right** unit | On land **anywhere** |
|---|---|---|
| One country-wide box (before) | ~1.4% | 21% |
| All of the unit's rings | 23% | 42% |
| The unit's **largest-area ring** | **44%** | **70%** |

Three things follow, and they set the shape of this part:

1. **A per-unit box is enough.** On a contiguous landmass 96% of pins land on
   land, and the ~49% that miss their own district land in an adjoining one —
   tens of kilometres out, not two thousand.
2. **An archipelago is worse, and still transformed.** Fiji's 70%/44% is well
   below India's, because a box around an island is mostly ocean. It is still 3×
   the land rate and **31× the right-unit rate** of what an operator typed
   before.
3. **Ring selection is not cosmetic — on Fiji it is the difference between
   working and not.** Two provinces straddle 180°, so a box over all their rings
   spans the whole globe and scores **0%**. Picking one ring fixes them.

#### D-1: Store a bounding box per unit, not a point

**Decision**: each unit carries `minLng,minLat,maxLng,maxLat`; the seeder draws
a fresh random point inside it per datapoint.

**Rationale**: a stored point makes every datapoint in a unit share one
coordinate, collapsing a seeded workspace to one pin per unit — the opposite of
what a map widget is being debugged with. The box preserves scatter and,
measured, still puts 96% of pins on land. Scatter is the feature; exact
containment is not.

**Alternatives**: storing the polygon itself (correct, and megabytes per
workspace in a JSON column, for disposable data); a point plus a jitter radius
(a radius has no relationship to the shape and walks straight out of a narrow
unit).

#### D-2: Reuse `AdministrationAttribute`; add no column

**Decision**: no `Administration.geo` field. The box is an administration
attribute.

**Rationale**: three things fall out at once, and the third was going to bite.

1. No migration, no model change, no new table.
2. The import path already exists — `seed_attributes` does the upsert, in the
   right value envelope, today.
3. **Attributes are not on the mobile sync path.** `generate_sqlite` builds its
   administration columns from `[f.name for f in model._meta.fields]`
   (`utils/custom_generator.py:36`), so a new *model field* ships to every device
   automatically, with no code change and no review — roughly 160 KB on a
   7,230-row hierarchy, for a column the app never reads. Attributes live in a
   separate table that export never touches, so the problem does not arise
   instead of being defended against.

This reverses Part 2 D-6 — see the appendix.

#### D-3: One attribute (`Bounding Box`), not four

**Decision**: a single CSV column `attr_Bounding Box` holding the four numbers
comma-separated.

**Rationale**: the four-column form (`attr_north`, `attr_south`, …) is the more
obvious shape, and costs measurably more for nothing gained:

| | one column | four columns |
|---|---|---|
| `AdministrationAttribute` rows | 1 | 4 |
| `AdministrationAttributeValue` rows (7,230-unit hierarchy) | 7,230 | 28,920 |
| Entries in the operator's attribute UI | 1 | 4 |
| Parser in the seeder | `parse_bbox`, unchanged | new, plus 4 lookups |
| Partially-edited state possible | no | yes (3 of 4 edited) |

The four numbers are one value — meaningless individually, invalid unless
consistent — so they belong in one cell. Splitting them makes the invalid state
representable.

The stored string is byte-for-byte what `parse_bbox` already accepts, so the
seeder reuses that function and its validation rather than growing a second
parser.

#### D-4: CSV convention `attr_<Attribute Name>`

**Decision**: any column matching `^attr_(.*)$` names an administration
attribute, created on demand as `Type.VALUE`.

**Rationale**: `parse_headers` already ignored every column that is not `^\d+_`
and said so in a comment — "*Columns that do not match `^\d+_` are ignored
rather than rejected, so a file carrying attribute columns still imports its
hierarchy (R-2)*". The hook was anticipated; this fills it. Every CSV written
before this change imports byte-identically.

This deliberately diverges from the Excel path, which keys attribute columns as
`<id>|<Name>` and looks them up by primary key. A notebook cannot know a database
id, so name-keyed is the only workable form here.

`.*` rather than `.+` in the pattern: a bare `attr_` column is a typo and is
reported, not silently ignored the way an unrecognised column is.

#### D-5: Remove `--bbox`; resolve the box from the data

**Decision**: delete the `--bbox` argument and its required-check. `parse_bbox`
and `random_point_in` survive, moved into `api/v1/v1_profile/bbox.py` so the
importer and the seeder share one parser, repointed at the attribute value.

**Rationale**: with a per-unit box in the data, a command-line box is a worse
answer to a question already answered better. Leaving both means an operator can
pass one that contradicts the hierarchy, and the seeder would have to pick.

```
target unit's own box
  -> nearest ancestor's box (Administration.ancestors is root-first,
     so walk it reversed)
  -> refuse to run (D-9)
```

There is no `None` rung. The ancestor rung is not decoration:
`seed_administrations` attaches boxes to the row's deepest unit (D-6), so a
workspace that later gains a tier — a 3-tier CSV import followed by an Excel
upload adding a 4th — has target units one level below the boxes. The walk
covers that without a second import.

#### D-6: Attach boxes to the row's deepest unit only

**Decision**: one `attr_Bounding Box` column; the seeder attaches it to the unit
`seed_administrations` returns — the leaf — exactly as the Excel path does.

**Rationale**: a datapoint only ever attaches to a leaf, and parents are covered
by the ancestor walk in D-5, so per-tier columns (`0_attr_…`, `1_attr_…`) would
widen the CSV to buy something already covered. GADM features *are* leaves, so
leaf boxes are the ones the file actually contains.

#### D-7: One ring per unit, chosen by area — this is what fixes the antimeridian

**Decision**: the notebook computes each feature's box from its **largest-area
ring** (shoelace area), not from all its rings.

**Rationale**: measured on Fiji, and the numbers are not marginal. Every Fijian
province is a multipolygon — Lau has 96 rings, Cakaudrove 46 — and two straddle
180°:

```
unit           rings   all-rings lng span   largest-ring lng span
Lau               96              359.86°                   0.13°
Cakaudrove        46              360.00°                   1.04°
Naitasiri          1                0.56°                   0.56°
```

A min/max over coordinates cannot tell "spans the globe" from "has points near
both ±180", so those two provinces get a worldwide box and score **0%**
containment. Choosing one ring collapses them to real boxes, because **a ring
never crosses the antimeridian** — it is a closed loop on one side. Overall:
23% → 44% own-unit, 42% → 70% on land.

**Area, not vertex count.** `max(rings, key=len)` scores 43%/69% against
`max(rings, key=area)`'s 44%/70% — a point of difference, so the choice is made
on correctness instead: vertex count measures how finely a coastline was
digitised, not how big the island is, so a heavily surveyed islet can outvote
the mainland. The shoelace is four lines and removes that failure mode. It made
no measurable difference on India (51%/96% either way), which is the point — it
costs nothing where it is not needed.

**No antimeridian guard is needed anywhere else.** Per-unit boxes, each from a
single ring, cannot span the antimeridian by construction, and D-9 removed the
workspace-union fallback that would otherwise have needed one.

**Alternatives**: all-rings boxes (0% on two Fijian provinces); one box per ring
(breaks the single-value design in D-3 for a case the largest ring covers);
splitting a crossing box in two at 180° (correct, and the seeder would then have
to pick between them per datapoint).

#### D-8: The accuracy ceiling is stated, not hidden

**Decision**: accept ~50% exact containment; have the notebook **report the
measured rate for the file being imported** rather than quoting India's number
at every operator.

**Rationale**: a box is not a polygon and never will be. The notebook already
owns the ray-casting machinery, so Step 8 prints the rate for the file in hand
and lists the units that miss most often. An operator seeing a low number for a
coastal or fjorded country then knows why the map looks the way it does, instead
of filing it as a bug.

**Alternatives**: rejection-sampling in the seeder (needs the polygon, the thing
deliberately not stored); saying nothing (this number will otherwise be
rediscovered as a bug report).

#### D-9: Every generated datapoint has a coordinate, or the seeder refuses

**Decision**: `geo` is never `None` on a row this seeder writes. A preflight
check resolves a box for the target administrations before the transaction
opens; if none resolves, the command exits with an error naming the fix.

**Rationale**: the mechanism was already half in place.
`pick_target_administrations` returns **only** the deepest level present in the
workspace, so a datapoint never attaches to a country or a province — it is
always a leaf. D-6 puts boxes on exactly those leaves. So in the documented flow
a resolvable box is not a likely outcome, it is a guaranteed one, and a `None`
rung would only cover paths that never reach it.

| Path | Targets | Box |
|---|---|---|
| Notebook CSV import (the documented flow) | leaves | always |
| `--test` | `TEST_GEO_DATA` | fixture coordinates, unaffected |
| Bundled sample fixture (`administration_seeder`) | none | writes `tenant=None` rows, so it never fed the tenant-scoped seeder in the first place |
| Hierarchy imported with no boxes | leaves | **error, naming the fix** |

The third row looks like a regression and is not. `seeder.sh` already describes
the bundled sample as "not workspace-scoped — enough to click around, not enough
to demo", and `pick_target_administrations` filters on `tenant=`, so a
`--tenant` run never saw those units. What changes is only the message.

**What this deletes**: the workspace-union fallback, its `> 180°` antimeridian
guard, the "warn once and continue" branch, and `ensure_hierarchy` with its
`--depth` and `--fanout` arguments. The stricter design is the smaller one.

**Alternatives**: warn and write `geo=None` (the failure is silent, and the
resulting map is exactly the bug this part exists to fix); a
`--allow-missing-geo` escape flag (a flag to permit broken output is worth less
than an error message saying what to run instead).

---

### Appendix: decisions reversed during this work

Three decisions were made before the boundary pipeline existed and undone once
it did. They are recorded because they explain the middle commits of this
branch, not because they describe the shipped code.

#### ~~Part 1 D-9: coordinates come from a required `--bbox`~~ → superseded by Part 3 D-5

The original problem was real: the seeder read
`./source/{COUNTRY_NAME}_random_points.csv` with `COUNTRY_NAME` hardcoded to
`"fiji"`, and matched the CSV's `name` column against administration *names*.
That file is not an administration list — it is a **coordinate table keyed by
Fiji province name**, and it only resolved because `administration_seeder`
happened to seed Fiji's topojson under the same names. On any other workspace
`find_administration` returned `None` and the next line raised
`AttributeError: 'NoneType' object has no attribute 'ancestors'`, caught by a
bare `except Exception` and reported as a message that told the operator nothing.

`--bbox` fixed that — one required flag, no default, works for any country. It
was the right answer while the hierarchy carried no geography. Once the notebook
could emit a box per unit, one country-sized rectangle became the *worse*
answer: it puts a pin in the correct unit under 1% of the time.

**Still true from this decision**: the CSV and `find_administration`'s
name-matching are gone from the normal path (retained for `--test` only, see
I-1), and `random_point_in` returns `[lat, lng]` — latitude first, because the
map widgets read `geo[0]` that way. That order is load-bearing and now lives in
one place.

#### ~~Part 1 D-10: an empty hierarchy is auto-generated, prefixed, and cleaned~~ → retired by Part 3 D-9

`configure_project` gives a new workspace one `Levels(level=0)` and one root
`Administration` and nothing else, so seeding datapoints onto it put every
datapoint on one unit: every administration filter returned everything and the
map was a single pin. `ensure_hierarchy` generated a throwaway `DUMMY-` tree
under the root to give the seeder something to attach to.

It is retired because that is precisely the state in which no bounding box
exists anywhere, so it could only ever produce datapoints without coordinates.
The preflight error replaced it, pointing at `administration_csv_seeder`.
Nothing is lost: importing a hierarchy is step 1 of the documented flow, and
`default_roles_seeder` (step 2) already requires it, so the generated hierarchy
was unreachable in the documented flow.

**Still true from this decision**: `Administration` is PROTECTed from five
directions, including from itself, so `--clean` must delete administrations
**after** all datapoints and **deepest level first**. A `.all().delete()` — the
shape `administration_seeder --clean` uses — cannot work, because the
self-referential PROTECT fires on the parents. Tiers 4 and 5 of D-5 keep that
ordering for workspaces seeded by an earlier commit on this branch.

| Referencing field | `on_delete` |
|---|---|
| `FormData.administration` | **PROTECT** |
| `DataBatch.administration` | **PROTECT** |
| `DataApproval.administration` | **PROTECT** |
| `EntityData.administration` | **PROTECT** |
| `Administration.parent` (self-referential) | **PROTECT** |
| `ViewDataOptions.administration` (matview) | **PROTECT** — see I-3 |
| `UserRole.administration` | CASCADE |
| `MobileAssignment.administrations` | M2M join |

#### ~~Part 2 D-6: no geo on administrations~~ → reversed by Part 3 D-2

The reasoning was correct at the time: the dashboard map's endpoint is
`/maps/geolocation/<form_id>` and its serializer is bound to `FormData`, and
`useWidgetData.js` always requests the **registration** form's geolocation
because `geo` is captured once when a site is registered. An `Administration.geo`
column would have been written by the importer and read by nothing.

What changed is that `fake_complete_data_seeder` became a reader. Option 2 of
that decision — *store the point as an `AdministrationAttributeValue`* — is what
shipped, so the conclusion "no migration" survived the reversal intact.

---

## 6. Type/Constant Mappings

### Fake data markers

| Surface | Constant | Literal value |
|---|---|---|
| Datapoint name | `DUMMY_PREFIX` | `"DUMMY-Kramat Jati - …"` |
| Monitoring child name | `DUMMY_PREFIX` | `"DUMMY-2026-03-10 - Mon Mar 10 …"` |
| Draft name | `DUMMY_PREFIX` | `"DUMMY-… - Draft"` |
| Submitter account | `DUMMY_EMAIL_PREFIX` + `DUMMY_EMAIL_DOMAIN` | `"dummy-user.<ns>@test.com"` |
| Approver account | same | `"dummy-approver.<adm><d>@test.com"` |
| Mobile assignment | `DUMMY_PREFIX` | `"DUMMY-<adm>.<username>"` |

### CSV headers

| CSV header | Parsed as | Model field |
|---|---|---|
| `0_National` | depth `0`, alias `National` | `Levels.level=0`, `Levels.name="National"`, `Administration.name` |
| `0_Code` | code column for depth 0 | `Administration.code` |
| `1_Province` | depth `1`, alias `Province` | `Levels.level=1`, `Levels.name="Province"`, `Administration.name` |
| `attr_Bounding Box` | attribute `Bounding Box` | `AdministrationAttributeValue.value` on the row's leaf |
| `attr_Population` | attribute `Population` | same |
| *(anything else)* | ignored | — |

### Bounding boxes

| Constant | Value | Where |
|---|---|---|
| Attribute name | `"Bounding Box"` | `v1_profile/constants.py` |
| Attribute type | `AdministrationAttribute.Type.VALUE` | existing |
| CSV header pattern | `^attr_(.*)$` | `administration_csv_seeder.py` |
| Ring selection | largest shoelace area | notebook, Step 4 |
| Value envelope | `{"value": "<minLng>,<minLat>,<maxLng>,<maxLat>"}` | existing convention |
| Coordinate order in the string | **lng, lat** | matches `parse_bbox` |
| Coordinate order in `FormData.geo` | **lat, lng** | `random_point_in` swaps |

The order flip is load-bearing and handled in exactly one place —
`random_point_in` returns `[lat, lng]` because the map widgets read `geo[0]` as
latitude. Nothing new should reorder either.

---

## 7. Compatibility & Migration

### Backward Compatibility

- [x] Existing API consumers unaffected — no schema or serializer change.
- [x] `seed_administrations()` is called as-is, so its four existing call sites
      and the Excel upload path are untouched.
- [x] CSVs generated before Part 3 import identically — `attr_` columns are
      optional and their absence is the existing code path.
- [x] No repository content added. Country CSVs live in the self-ignoring
      `backend/storage/` directory.
- [ ] Existing data preserved, with one caveat: rows from *previous* seeder runs
      are unprefixed and therefore invisible to `--clean`. They must be removed
      by hand or by dropping the database once (R-1).
- [ ] **`--tenant` is a breaking change** for any non-`--test` invocation.
      Exactly one caller exists in the repo, `seeder.sh`, updated in the same
      work. All 35 test callers pass `--test=true` and are exempt.
- [ ] **`--bbox` is removed**, which is breaking — but the flag is new on this
      same unreleased branch, so no deployed script uses it.

### Mobile App Impact

- [x] SQLite schema unchanged. Administrations reach the device through the
      existing `generate_sqlite` path, and **attribute values are not on it** —
      `generate_sqlite` exports administration *model fields*
      (`utils/custom_generator.py:36`), and attributes live in another table it
      does not read. A regression test pins the exported column list anyway,
      because that line means any future field addition ships silently.
- [ ] Sync content affected, deliberately: a device assigned to a `DUMMY-`
      mobile assignment syncs `DUMMY-`-named datapoints and displays them. That
      is the same "tell fake from real" benefit, on the device.
- [ ] `--clean` hard-deletes rows a device may hold locally; it will not learn
      they are gone until its next full resync. Acceptable for a development
      tool — do not run `--clean` against a workspace with live field devices.
- [ ] Devices already synced hold the old hierarchy until their next
      `generate_sqlite` + resync. `seeder.sh` already runs `generate_sqlite` at
      the end of a seed.

### Seeder/CLI Compatibility

| Command | Change |
|---|---|
| `fake_complete_data_seeder` | `--tenant` required; `--clean` terminal; `--bbox`, `--depth`, `--fanout` removed |
| `administration_csv_seeder` | **new**; accepts `attr_*` columns |
| `administration_seeder` | `seed_administration_prod()` and the topojson path removed; `--test` fixture unchanged |
| `form_seeder` | `--tenant` added, optional — omitting it keeps the pre-workspace behaviour |
| `default_roles_seeder` | unchanged; takes no `--tenant` (it derives each role's workspace from its level) |
| `administration_attribute_seeder` | unchanged |
| `seeder.sh` | `--tenant` is now a required argument, not a prompt; `seeder.prod.sh` merged in and deleted; entities step dropped; bounding-box prompt removed |

---

## 8. Security Considerations

- [x] Permission model: management commands, shell access only. No new HTTP
      surface, so no new authz decision.
- [x] No new attack vectors.
- [x] **Tenant scoping.** `AdministrationAttribute` is `TENANT_PATH = "tenant"`;
      the get-or-create passes `tenant=` or one workspace's box definition
      becomes another's. `AdministrationAttributeValue` derives its tenant
      through `administration__tenant`, so it follows automatically.
- [x] **Input validation.** The CSV is untrusted text. `parse_bbox` rejects
      non-numeric values, inverted axes and out-of-range coordinates, and the
      import routes through it rather than storing the cell verbatim, so a
      malformed box fails at import with a row number instead of at seed time
      with a stack trace. The whole import runs in one `transaction.atomic()`,
      so a bad row on line 400 leaves nothing behind.
- [x] **The delete filter is a compile-time constant, never a CLI argument.**
      A `--prefix <str>` option must not be added: it would turn `--clean` into
      an arbitrary `DELETE FROM form_data WHERE name LIKE $1`.
- [ ] **Destructive-operation review required.** `--clean` hard-deletes. Four
      guards, all of which a reviewer should confirm are present:
      (a) the delete key is the prefix, never `created_by` (Part 1 D-2);
      (b) the prefix is a compile-time constant, not user input;
      (c) user deletion is additionally guarded on having no surviving
      `FormData`; (d) the command refuses to run when `settings.DEBUG` is
      `False` (R-4).

R-4 is a *configuration* guard, not an environment guard: a staging deployment
running with `DEBUG=True` is still allowed to clean, which is intended — staging
is where dashboard debugging happens.

---

## 9. Testing Strategy

**99 tests ship with this work**: 52 for `administration_csv_seeder`, 47 for the
prefix, `--clean` and the bounding boxes.

### Part 1 — marking and teardown

| Type | Coverage |
|---|---|
| Unit | `mark_as_dummy` is idempotent — twice yields one prefix, not `DUMMY-DUMMY-` |
| Unit | **Prefix survives `add_fake_answers`** — seed a form with a `meta: true` question and assert the prefix after the full create path. The D-3 regression, and the single most valuable test here |
| Integration | `--clean` removes root, monitoring-child and draft `FormData` and cascades `Answers` to zero |
| Integration | **`--clean` preserves real data.** Create an unprefixed `FormData` whose `created_by` is a user the seeder also reused; run `--clean`; assert row and user both survive. The D-2 regression |
| Integration | `--clean` collects rows soft-deleted by an earlier run |
| Integration | `--clean` is idempotent — second run deletes 0 and exits 0 |
| Integration | Default run is approved-only: no pending rows, no drafts, no approver accounts |
| Unit | `--approved true --draft true` raises `CommandError` |
| Unit | Omitting `--tenant` without `--test` raises before any write; `--test=true` alone succeeds |
| Integration | Two workspaces seeded separately: cleaning one leaves the other's `DUMMY-` data untouched |
| Unit | `--clean` under `override_settings(DEBUG=False)` raises and deletes nothing |
| Integration | The uploaded blob's `datapoint_name` carries `DUMMY-` — asserts the stamp landed before `save_to_file` |

### Part 2 — CSV import

| Type | Coverage |
|---|---|
| Unit | `parse_headers` returns the right depth/alias/code map, and rejects non-contiguous levels, no level columns, and the `Code`-named-level collision |
| Unit | Columns not matching `^\d+_` are ignored, not errors |
| Integration | A 3-tier, 4-row file creates the expected counts, with repeated parent tiers reused |
| Integration | **Same name under different parents stays distinct** — `Central/Nasau` and `Western/Nasau` produce two rows with different `path`s. The D-1 defect this command exists to avoid |
| Integration | Every created administration has a correct `path`; `full_name` renders the whole ancestry |
| Integration | Idempotency — the same file twice creates nothing the second time |
| Integration | Two tenants importing the same file get two independent hierarchies, neither visible to the other via `for_user` |
| Integration | Root mismatch raises and writes nothing; `--rename-root` renames instead |
| Integration | An existing level keeps its name when the file's alias differs |
| Integration | `--dry-run` reports counts and writes nothing |
| Unit | Missing or unknown `--tenant` fails before the CSV is opened; the error lists known subdomains |
| Unit | `resolve_source` prefers storage over an identically-named local file, falls back to a literal path, and names both locations when neither resolves |
| Integration | Names are title-cased, matching the Excel path — asserts the accepted behaviour so a later change to `seed_administrations` is caught here rather than in production |

### Part 3 — bounding boxes

| Type | Coverage |
|---|---|
| Unit | `parse_attribute_headers` recognises `attr_Bounding Box`; rejects a bare `attr_` and two columns naming one attribute |
| Integration | Attribute created once per workspace and reused on re-import; value upserted, not duplicated |
| Integration | A malformed box fails with the offending row number and rolls back; an inverted box is rejected |
| Integration | Two workspaces importing the same file get two separate `AdministrationAttribute` rows |
| Integration | A file without `attr_` columns still imports its hierarchy, writing no attribute values |
| Integration | A non-bbox attribute (`attr_Population`) is stored too, as `Type.VALUE` |
| Integration | **A datapoint's `geo` falls inside its own administration's stored box.** Each unit gets a *different* box in the fixture, deliberately: a shared box would pass even if the seeder ignored the administration entirely, which is the bug this part exists to fix |
| Integration | Monitoring children inherit the parent's pin |
| Integration | Pins are not all identical — a box scatters, which is why D-1 stores a box |
| Integration | Ancestor fallback fires when the leaf has no box |
| Integration | A box edited into nonsense falls through to the ancestor instead of failing the run |
| Integration | No box anywhere → `CommandError` naming `administration_csv_seeder`, nothing written |
| Integration | A workspace with only a root is refused — where `ensure_hierarchy` used to invent a tree |
| Integration | Every row written has a non-null `geo` |
| Unit | `--bbox` is rejected as an unknown argument |
| Unit | `--test` still produces `TEST_GEO_DATA` coordinates |
| Integration | **`--clean` keeps the boxes** — they belong to the hierarchy, carry no `DUMMY-` prefix, and the prefix-keyed deletion already leaves them alone. The test exists to keep it that way |

### Verification performed

- **Full backend suite: 1,975 tests pass** (1 skipped). `flake8` clean on every
  file this work touches.
- **Three regressions were confirmed to fail against the previous
  implementation** before the fix was restored: the hyphen shredding, `--clean`
  preserving real data authored by a reused submitter, and — by mutating the
  seeder to use a fixed unit's box — the pin-inside-its-own-unit assertion.
- `seeder.sh` argument handling, both `--tenant` forms, the `DEBUG` gate and
  both administration branches were exercised by dry-running the script with
  `python manage.py` substituted for `echo`.
- End to end: 6,695 GADM features → CSV → 7,230 administrations; then seed, then
  `--clean`, leaving 0 rows and the imported hierarchy intact.
- End to end with a real Fiji file: 15 provinces imported with boxes → 140
  datapoints, **0 without a coordinate, 0 outside their own box**, widest
  imported box 1.19° rather than 360°.
- The notebook runs end to end against India (676 districts) and Fiji.
- **No frontend code changed**, so no frontend test run is claimed.

**Not done**: a manual click-through of Manage Data and a dashboard after
seeding. The API-level behaviour is covered above; the visual check is the
remaining manual verification.

---

## 10. Resolved Questions & Open Items

### Resolved

**R-1 · Pre-existing unprefixed fake data — accepted, no backfill.**
Rows from earlier seeder runs carry no marker, so `--clean` cannot see them.
This is a new MIS with no accumulated seeder history worth rescuing. A backfill
would also reintroduce the D-2 hazard: keyed on
`created_by.email LIKE '%@test.com'` it would mark rows authored by *reused*
accounts, which is exactly the mis-attribution Part 1 D-2 exists to prevent.

**R-2 · Storage blobs are kept, and `save_to_file` stays.**
`--clean` removes the database rows but leaves `datapoints/{uuid}.json`.
Accepted: the blobs are wanted, because `DUMMY-` data is also used for mobile
debugging and that path reads the generated JSON. This is what makes the D-3
ordering constraint load-bearing rather than incidental — the blob embeds
`datapoint_name`, so the prefix must be stamped before `save_to_file` runs or
the mobile payload says `Kramat Jati` while the database says
`DUMMY-Kramat Jati`. Blobs accumulate across `--clean` cycles; they are keyed by
`uuid` so they never collide, and nothing reads a blob whose row is gone.

**R-3 · `Entity` / `EntityData` are not deleted — acceptable.**
`set_answer_data` creates entity rows via `get_or_create` for entity-cascade
questions. They are shared with real submissions and are not prefixed, so an
entity-cascade dropdown keeps showing seeder-invented options after a `--clean`.
Deleting them would risk removing entities a real submission references, and
`EntityData.administration` is `PROTECT` besides.

**R-4 · `--clean` refuses to run when `DEBUG=False`.**
The guard makes the destructive path impossible to trigger under production
configuration, independently of the other three guards in §8.

**R-5 · CSVs live in storage, not in the repository.**
`--source` resolves against `STORAGE_PATH` with a literal-path fallback. The
decisive property is that `backend/storage/.gitignore` is `*` / `!.gitignore` —
a self-ignoring directory — so a country file dropped there cannot be committed
by accident. `source/` has no such guard, and committing a national
administrative gazetteer is not something a single `.gitignore` line should be
the only thing preventing.

**R-6 · `seed_administrations()` is used unchanged.**
No `normalize_name` parameter, no fork, no reimplementation. This supersedes an
earlier "store verbatim" position: using the helper as-is means `name.title()`
applies, so `DKI Jakarta` is stored as `Dki Jakarta` — exactly what the Excel
path already produces. One code path, one behaviour, both callers agreeing.

**R-7 · Bounding box questions — all four settled.**

1. *One column or four?* → **One.** 7,230 value rows instead of 28,920, one
   entry in the attribute manager, `parse_bbox` reused unchanged, and no way to
   represent a half-edited box.
2. *`"Bounding Box"` visible in the attribute manager?* → **Accepted.** It sits
   alongside "Population" and is editable like any other attribute. No `hidden`
   flag on `AdministrationAttribute`, which would be a larger change than the
   whole of Part 3. A box edited into nonsense fails `parse_bbox` at seed time
   and falls through to the ancestor, so the damage is bounded.
3. *Boxes by default, or behind a config flag?* → **By default.** ~40 characters
   per row (~290 KB on a 7,230-row file); the alternative is discovering the
   column is missing only when the map comes up empty, and re-importing an
   entire hierarchy to add it.
4. *Fiji / the antimeridian?* → **Answered by measurement**, see Part 3 D-7.

### Still open

- [ ] **Retire `administration_seeder`.** Its three defects (Part 2 D-1) are not
      worth fixing, because `administration_csv_seeder` replaces every non-test
      caller. The only dependency to unpick is the `--test` fixture used by 30+
      tests — a fixture problem, not a correctness problem. Deletion, not repair.
      Porting the fixture would need a **committed** file, which R-5 rules out
      of `storage/`; it would have to keep `DEFAULT_ADMINISTRATION_DATA` as a
      Python constant and feed it through the same parser, or place one small
      fixture under `api/v1/v1_profile/tests/fixtures/`.
- [ ] **`name.title()` in `seed_administrations`** turns `AcehBarat` into
      `Acehbarat` and `DKI Jakarta` into `Dki Jakarta`. Pre-existing, shared with
      the Excel upload path, and accepted here so both paths agree. If it ever
      needs fixing, fix it in the shared helper for both callers and decide what
      to do about rows already stored title-cased. Not a blocker.

---

## 10b. Implementation Notes (deviations found while building)

None of these changes a decision, but a reviewer should know why the code
differs from the snippets above.

### I-1: `--test` keeps `find_administration` and `TEST_GEO_DATA`

Part 1 D-9 said the CSV name-matching and `find_administration()` are deleted.
They are deleted from the **normal** path, and retained for `--test`.

35 test files call this command as `--test=true`, and `TEST_GEO_DATA` is a
closed fixture whose names line up with `DEFAULT_ADMINISTRATION_DATA` at several
different depths. Routing `--test` through `pick_target_administrations` instead
would attach every fixture datapoint to the two deepest villages, changing the
administration distribution those files were written against. The exemption
keeps them byte-identical. `find_administration` is now tenant-scoped, so it no
longer reads across workspaces.

### I-2: the `Code`-named-level collision degrades, it does not raise

Part 2 D-2 predicted `parse_headers` would reject a level literally named `Code`
with a "collides" message. It cannot: `1_Code` is claimed as level 1's **code**
column before any name column is considered, so level 1 simply has no name
column and the tier goes missing. The contiguity check reports it instead:

```
Levels must be contiguous from 0. Found [0, 2], expected [0, 1]
```

Still rejected, still with a usable message, by a different branch. The
duplicate-name branch that *is* reachable covers two name columns for one tier
(`1_Province` alongside `1_Region`), and its message was reworded to say that.
Both paths have a test.

### I-3: `--clean` must refresh the materialized view before tier 4

`ViewDataOptions.administration` is `on_delete=PROTECT`. The model is
`managed = False` — it maps a matview with no real FK constraint — but Django's
collector does not know that and evaluates the PROTECT anyway. After tier 1
removes the datapoints, `view_data_options` still holds their rows until it is
refreshed, so tier 4 raised:

```
ProtectedError: Cannot delete some instances of model 'Administration' because
they are referenced through protected foreign keys:
'ViewDataOptions.administration'
```

The fix is a `refresh_materialized_data()` between tiers 1 and 4, which is
correct independently of the delete: the view must not serve datapoints that no
longer exist.

### I-4: `pick_role()` — generated levels have no roles

`UserRole.role` is **not** nullable, and the original code passed whatever
`Role.objects.filter(administration_level=...).first()` returned straight into
`user_user_role.create(role=role)`. A generated hierarchy created levels
`default_roles_seeder` never saw, so the level-exact lookup legitimately missed
and the seeder died on an `IntegrityError` several frames later. `pick_role`
falls back to any role with the same access, then raises a sentence instead of a
traceback. Fake data needs *a* role, not the anatomically correct one.

### I-5: D-8's breaking change, realised

`--approved true --draft true` now raises. Five call sites relied on the old
silent behaviour and were updated to pass `--approved=false`, which is what they
meant — drafts only exist in a mixed workflow.

### I-6: `settings.STORAGE_PATH`, not `storage.check()`

Part 2 D-3's `resolve_source` snippet calls `storage.check(source)`. The shipped
code reads `settings.STORAGE_PATH` directly, because `utils/storage.py` binds
the value at import time, so `override_settings(STORAGE_PATH=…)` never reaches
it and the check would look in the real storage directory while the join pointed
at the temporary one. One source of truth, and the resolver is testable.

### I-7: `csv`, not `pandas`

The Excel path uses pandas and is consequently littered with `pd.isnull()`
checks, because pandas turns an empty cell into `NaN`. `csv.DictReader` gives
back empty strings, so "blank means truncate here" is a plain falsy check.
`utf-8-sig` is used so a spreadsheet-exported BOM does not become part of the
first header's name.

### I-8: the notebook was not valid nbformat

Every cell's `source` was a list of lines with no trailing newlines, back to the
committed version. Jupyter joins that list with `""`, so each cell collapsed
onto one line. Normalised while adding Step 4, along with the missing cell `id`
fields.

---

## 11. References

- Related tasks:
  - [MT-002 Tenant scoping (database)](MT-002-tenant-scoping-database.md) — the
    tenancy this work depends on
  - [MT-005 Level management CRUD](MT-005-level-management-crud.md) — the UI
    path Part 2 shortcuts
  - [MT-007 Administration bulk upload hardening](MT-007-administration-bulk-upload-hardening.md)
    — the Excel path
  - [VIZ-009 Legacy dashboard removal](VIZ-009-legacy-dashboard-removal.md) —
    the surface this data feeds
- Prior art:
  - `api/v1/v1_jobs/administrations_bulk_upload.py` — `seed_administrations()`
    reused wholesale (Part 2 D-3), and the attribute upsert reused by Part 3
  - `api/v1/v1_profile/management/commands/administration_seeder.py` — the
    legacy path and its three defects (Part 2 D-1)
  - `utils/upload_administration.py` — the id-pipe header convention rejected in
    Part 2 D-2
  - `utils/soft_deletes_model.py` — the soft/hard delete semantics behind
    Part 1 D-4
  - `utils/draft_model.py` — why `FormData.objects` includes drafts but excludes
    deleted rows
- Tooling:
  - `scripts/administration_csv_generator/README.md` — the notebook that turns
    boundary data into the CSV
  - [GADM](https://gadm.org/download_country.html) — boundary source, and where
    the India and Fiji files behind the numbers in Part 3 came from

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-09-02 | Implemented, pending review |
| Tech Lead | | | |
| Product | | | |
