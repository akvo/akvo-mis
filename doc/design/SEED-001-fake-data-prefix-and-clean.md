# Feature Design Document

## Feature: Marked fake data (`DUMMY-`) and a `--clean` teardown

**Task ID**: SEED-001
**Author**: Iwan Firmawan
**Date**: 2026-08-31
**Status**: Draft

---

## 1. Context & Problem Statement

```
Currently:
- `fake_complete_data_seeder` writes FormData that is byte-indistinguishable
  from real submissions. Nothing on the row, in the UI, or in the API says
  "this was generated".
- There is no way to remove it. The only teardown is dropping the database,
  which also destroys the administration hierarchy, forms, roles and users
  that took a full `./seeder.sh` run to build.
- Consequently the seeder can only be used on a throwaway local DB. It cannot
  be used on a shared dev/staging workspace, which is exactly where dashboard
  and visualization debugging needs to happen.
- Re-running the command appends: `existing_data_count % total_points` picks up
  the geo index where the last run stopped
  (`fake_complete_data_seeder.py:191-197`), so successive runs silently pile up
  and there is no way to get back to a known state.
- The command only runs against a Fiji-shaped workspace. It matches a hardcoded
  `source/fiji_random_points.csv` against administration *names*, so on any
  other workspace — including every workspace created the normal way, through
  registration + `configure_project` — it dies on
  `AttributeError: 'NoneType' object has no attribute 'ancestors'`. See D-9.
- A freshly-registered workspace has exactly one level and one root
  administration and nothing below it, so even with the name matching fixed
  there is nothing to attach datapoints to. See D-10.

Goal:
- Every row the seeder creates is visibly marked with a `DUMMY-` prefix, so a
  human reading a datapoint list, a dashboard widget or a map popup can tell
  generated data from real data at a glance.
- `--clean` removes all fake data and only fake data, leaving real submissions,
  forms, administrations, roles and real user accounts untouched.
- `--clean` is idempotent and safe to run when there is nothing to clean.
```

This unblocks item 1 of the visualization debugging gap analysis (multi-tenant
seeding, see [MT-002](MT-002-tenant-scoping-database.md)): a `--tenant` flag is
only usable if there is also a way to undo a run that landed in the wrong
workspace.

---

## 2. Requirements

### User Acceptance Criteria

- [ ] Every seeded datapoint name starts with `DUMMY-` in Manage Data, the
      dashboard viewer, map popups and Excel/DOCX exports.
- [ ] Every seeded user account is recognisable by email (`dummy-…@test.com`)
      and by name.
- [ ] Every seeded mobile assignment name starts with `DUMMY-`.
- [ ] `./dc.sh exec backend python manage.py fake_complete_data_seeder --clean`
      removes all generated data and reports what it deleted.
- [ ] `--clean` wipes and exits. It never reseeds, and it requires only
      `--tenant` — no `--bbox`, because it generates nothing.
- [ ] Running `--clean` twice in a row is a no-op the second time.
- [ ] `--help` states plainly that the default run produces approved data only
      — no drafts, no pending rows, no approver accounts (D-8).
- [ ] `--approved true --draft true` fails with a clear message instead of
      silently seeding drafts (D-8).
- [ ] The command runs against a workspace of any country, given `--bbox`, with
      no code change and no country data file (D-9).
- [ ] The command runs against a freshly-registered workspace that has only a
      root administration, generating a throwaway hierarchy under it (D-10).
- [ ] Generated administrations and levels are `DUMMY-` prefixed and removed by
      `--clean` alongside the datapoints (D-10).

### Technical Acceptance Criteria

- [ ] **No schema migration.** No new column on `form_data` or any other hot
      table (see D-1).
- [ ] `--clean` performs a **hard** delete. No `deleted_at`-stamped residue is
      left behind (see D-4) — a soft delete would leave the rows visible to
      `objects_with_deleted` and to the mobile sync's deleted-row handling.
- [ ] `--clean` never deletes a `FormData` row that the seeder did not create,
      **even when the seeder reused a pre-existing real user as the submitter**
      (see D-2 — this is the sharp edge of this feature).
- [ ] The prefix survives `add_fake_answers`, which overwrites `data.name`
      (see D-3).
- [ ] Answers, AnswerHistory and monitoring children are removed by database
      cascade, not by a second queryset.
- [ ] Soft-deleted and draft fake rows from earlier runs are also collected.
- [ ] Whole operation runs inside one `transaction.atomic()`.
- [ ] `--clean` raises `CommandError` when `settings.DEBUG` is `False` (R-4).
- [ ] `--tenant` is required outside `--test`, and every lookup the command
      makes is scoped by it — forms, levels, administrations, roles,
      organisations and created users (D-6).
- [ ] The `DUMMY-` prefix reaches the storage blob, not just the database row —
      `save_to_file` is kept for mobile debugging and embeds `name` (R-2).
- [ ] `flake8` clean.

---

## 3. Data Model Changes

### New Models

None.

### Modified Models

| Model | Change | Reason |
|-------|--------|--------|
| — | — | No model changes. The marker is carried in existing `name` / `email` text columns. |

### Migration Strategy

```python
# No migration.
#
# Rejected alternative: FormData.is_fake = models.BooleanField(default=False)
# `form_data` is the largest table in the schema and is on the mobile sync
# path. Adding a column with a default rewrites the table on Postgres < 11
# and adds a field to every sync payload — a permanent production cost for a
# development-only concern. See D-1.
```

### New constant

```python
# backend/api/v1/v1_data/constants.py  (new file, or reuse an existing one)

# Marker for seeder-generated rows. Anything carrying this prefix is fair
# game for `fake_complete_data_seeder --clean`, so never apply it to a row a
# human might have authored.
DUMMY_PREFIX = "DUMMY-"

# Seeded accounts are additionally namespaced by email so the clean can find
# them without depending on first/last name, which Faker randomises.
DUMMY_EMAIL_PREFIX = "dummy-"
DUMMY_EMAIL_DOMAIN = "@test.com"
```

---

## 4. CLI Contract

This feature adds no HTTP endpoints. The equivalent contract is the management
command's argument surface.

### Arguments

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--clean` | flag | `False` | Hard-delete every `DUMMY-` row this workspace owns, then **exit**. Seeds nothing, so `--bbox` is not required |
| `-r, --repeat` | int | `5` | *(existing)* |
| `-m, --monitoring` | int | `2` | *(existing)* |
| `--approved` | bool | `True` | *(existing — help text corrected, see D-8)* |
| `--draft` | bool | `False` | *(existing)* |
| `--test` | bool | `False` | *(existing)* |
| `-t, --tenant` | str | **required** (unless `--test`) | Workspace subdomain to seed into. `default` exists on any migrated database — see D-6 |
| `--bbox` | str | **required** (unless `--test`) | `minLng,minLat,maxLng,maxLat` for generated geo points. No default — see D-9 |
| `--depth` | int | `2` | Levels of throwaway hierarchy generated when the workspace has none (D-10) |
| `--fanout` | int | `4` | Children per generated administration (D-10) |

"Approved data only — no drafts, no pending, no approval workflow" is
**already the default behaviour**; it needs no new flag, only a guard and
honest help text. See D-8.

`--clean` follows the boolean-parsing convention already used by `--approved`
and `--draft` in this command, **not** the `nargs="?" const=1 type=int` style
used by `administration_seeder --clean`. Rationale in D-7.

### Invocations

```bash
# Wipe. Tenant and nothing else -- no bbox, because nothing is generated.
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    --tenant acme --clean

# Seed 20 registrations with 3 monitoring rounds each
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    -r 20 -m 3 --tenant acme --bbox "177.0,-18.3,180.0,-16.1"

# Reset = the two above, chained. `--clean` is terminal on purpose (D-9b).
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    --tenant acme --clean && \
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    -r 20 --tenant acme --bbox "177.0,-18.3,180.0,-16.1"

# A workspace in Kenya — same command, different box, no code change
./dc.sh exec backend python manage.py fake_complete_data_seeder \
    -r 20 --tenant kenya-wash --bbox "33.9,-4.7,41.9,5.5"

# Test fixture path — bbox exempt, uses TEST_GEO_DATA (D-9)
./dc.sh exec backend python manage.py fake_complete_data_seeder --test=true
```

Missing `--bbox` fails before any write:

```
CommandError: --bbox is required. Example for Fiji:
              --bbox '177.0,-18.3,180.0,-16.1'
```

### Output contract

```
-- Cleaning fake data
   FormData (registrations + monitoring + drafts): 340
   Answers (cascaded):                             4080
   MobileAssignment:                               12
   SystemUser:                                     12
-- Fake data cleared
Created 20 data entries for form Visualization Test Registration
...
```

---

## 5. Decision Log

### D-1: How is a row marked as fake?

**Options Considered**:

1. **Name prefix in existing text columns** (`FormData.name`,
   `SystemUser.email`, `MobileAssignment.name`).
2. **A dedicated boolean column** — `FormData.is_fake`.
3. **A dedicated tenant** — seed everything into a `Tenant(subdomain="dummy")`
   and clean by dropping that tenant's rows.

**Decision**: Option 1, name prefix.

**Rationale**:
The user-facing half of the requirement — "distinguish real from fake at a
glance" — is only satisfied by option 1. A boolean column is invisible in
Manage Data, in a dashboard widget, in a map popup and in an Excel export
unless every one of those surfaces is also taught to render it, which is a far
larger change than the seeder. Option 2 also costs a migration on the largest
table in the schema, on the mobile sync path, permanently, for a
development-only concern.

Option 3 is genuinely attractive and is the right long-term answer once the
`--tenant` work lands, because `Tenant` is a real referential boundary rather
than a string convention. It is rejected *for now* because no seeder is
tenant-aware yet (`administration_seeder`, `form_seeder`,
`default_roles_seeder`, `organisation_seeder` and `entities_seeder` contain
zero `tenant` references), so a "dummy tenant" would have no hierarchy, no
forms and no roles to hang off. Revisit as D-6.

**Impact**: No migration. Prefix handling must be added at ~6 creation sites.
The delete key becomes a string prefix, which carries the false-positive risk
addressed in D-2.

---

### D-2: What is the delete key — the name prefix, or the creating user?

This is the most important decision in the document and the one most worth
reviewing carefully.

**Options Considered**:

1. **Delete by `FormData.name__startswith="DUMMY-"`**, cascade to answers.
2. **Delete the seeded users and let `created_by` cascade** do the rest.

Option 2 looks strictly better at first: `FormData.created_by` is
`on_delete=CASCADE`, so deleting the users removes every row they authored
including monitoring children and drafts, with no dependence on what
`add_fake_answers` did to the name.

```python
# backend/api/v1/v1_data/models.py:45-49
created_by = models.ForeignKey(
    to=SystemUser,
    on_delete=models.CASCADE,      # ← would cascade the whole tree
    related_name="form_data_created",
)
```

**Decision**: Option 1 — delete by name prefix on `FormData`.

**Rationale**: **the seeder does not always create its submitter.** It reuses
any existing user who happens to match:

```python
# backend/api/v1/v1_data/management/commands/fake_complete_data_seeder.py:218-224
user = SystemUser.objects.filter(
    **filter_submitter,
    user_user_role__administration=parent_adm,
) \
    .exclude(password__exact="") \
    .order_by("?").first()
if not user:
    # ... only here is a new user created
```

On any workspace that already has real submitters, `filter_submitter` matches
them, `.order_by("?").first()` picks one, and the fake datapoints are
attributed to a **real person's account**. Option 2 would then hard-delete that
account and cascade away every genuine submission they ever made. That is
unrecoverable data loss triggered by a flag whose name promises cleanup.

Option 1 cannot do this: the worst case is that a real datapoint whose name
genuinely begins with `DUMMY-` is removed, which requires a human to have typed
that prefix into a meta field.

**Impact**:
- `created_by` cannot be used as the delete key, so the prefix *must* be
  correctly applied to every `FormData` row — including drafts (D-5).
- User cleanup becomes a separate, guarded step (D-5).
- A run interrupted between `create()` and the prefix stamp leaves orphans.
  Mitigated by the whole seeding loop already running inside
  `transaction.atomic()` (`fake_complete_data_seeder.py:200`).

---

### D-3: Where in the flow is the prefix stamped?

**Options Considered**:

1. At `FormData.objects.create(name=f"{DUMMY_PREFIX}{name}")`.
2. After `add_fake_answers()` returns.

**Decision**: Option 2 — after `add_fake_answers()`, before `save_to_file`.

**Rationale**: option 1 is silently discarded. `add_fake_answers` rebuilds
`data.name` from the form's `meta` questions and overwrites whatever the caller
set:

```python
# backend/api/v1/v1_data/functions.py:194-199
if len(meta_name) > 0:
    name = " - ".join(meta_name)
    # make sure the name is not empty white spaces
    if len(name.strip()):
        data.name = name          # ← clobbers the prefix set at create()
data.save()
```

Any form with at least one `meta: true` question — which is every registration
form in `source/forms/`, e.g. `site_name` (600101) on `example-vis-6.json` —
loses the prefix. The datapoint then looks real *and* is invisible to
`--clean`: the worst of both outcomes, and it fails silently.

There is a second ordering constraint on the other side. `save_to_file` is a
`@property`, so the bare attribute access at line 377 **does execute**, and it
serialises `self.name` into a JSON blob uploaded to cloud storage:

```python
# backend/api/v1/v1_data/models.py:113-136
@property
def save_to_file(self):
    ...
    data = {
        "id": self.id,
        "datapoint_name": self.name,   # ← must already carry the prefix
        ...
    }
    file_name = f"{str(self.uuid)}.json"
```

So the stamp must land strictly between `add_fake_answers` (line 341) and
`save_to_file` (line 377).

**Impact**: one helper, called at each `FormData` creation site.

```python
def _mark_as_dummy(form_data):
    """Stamp the fake-data prefix, idempotently.

    MUST be called after add_fake_answers(), which rebuilds `name` from the
    form's meta questions and would otherwise discard the prefix
    (functions.py:194-198), and before `save_to_file`, which serialises the
    name into the storage blob.
    """
    if form_data.name.startswith(DUMMY_PREFIX):
        return form_data
    form_data.name = f"{DUMMY_PREFIX}{form_data.name}"
    form_data.save(update_fields=["name"])
    return form_data
```

---

### D-4: Soft delete or hard delete?

**Options Considered**:

1. `FormData.objects.filter(...).delete()` — the default.
2. `.hard_delete()`.

**Decision**: Option 2, hard delete.

**Rationale**: `FormData` extends `SoftDeletes`, whose queryset `delete()` is
an `UPDATE`, not a `DELETE`:

```python
# backend/utils/soft_deletes_model.py:15-24
def delete(self, hard: bool = False):
    if hard:
        return super().delete()
    return super().update(deleted_at=timezone.now())   # ← rows still there

def hard_delete(self):
    return self.delete(hard=True)
```

Option 1 would leave every row in `form_data`, still reachable through
`objects_with_deleted`, still counted by anything using a raw manager, and
still occupying the `submission_key` unique index. `--clean` would appear to
work and the table would grow monotonically.

Note that hard delete goes through Django's collector, which issues plain
`DELETE`s and does **not** call each child model's overridden `delete()`. That
is what we want: monitoring children (`FormData.parent`, CASCADE), `Answers`
(`Answers.data`, CASCADE) and `AnswerHistory` (`AnswerHistory.data`, CASCADE)
are all removed for real, in one statement each.

**Impact**: the reviewer should check that no call site uses a bare
`.delete()`.

---

### D-5: What exactly does `--clean` delete?

**Decision**: three tiers, in this order.

```python
# Tier 1 — datapoints. objects_with_deleted, not objects: the default manager
# hides soft-deleted rows (soft_deletes_model.py:44), so fake rows soft-deleted
# by an earlier run or by the UI would survive every subsequent --clean.
# It does NOT filter is_draft, so drafts created by --draft true are included
# in the same queryset.
fake_data = FormData.objects_with_deleted.filter(
    name__startswith=DUMMY_PREFIX
)
# Monitoring children cascade via FormData.parent (CASCADE); Answers and
# AnswerHistory cascade via their `data` FK. No second queryset needed.
data_count = fake_data.count()
fake_data.hard_delete()

# Tier 2 — mobile assignments. FK to SystemUser is CASCADE, so tier 3 would
# take these anyway; deleting them first keeps the reported counts honest and
# covers assignments attached to a REUSED real user, which tier 3 must not
# touch.
MobileAssignment.objects.filter(
    name__startswith=DUMMY_PREFIX
).delete()   # plain model, not SoftDeletes — bare delete() is correct here

# Tier 3 — seeded accounts, guarded. Only accounts the seeder itself minted
# (dummy- prefix AND @test.com), and only those with no surviving FormData.
# The guard is what makes D-2's "reused a real user" scenario safe: a real
# account never matches the email filter, and a seeded account that somehow
# authored real data is skipped rather than cascaded.
orphaned = SystemUser.objects_with_deleted.filter(
    email__startswith=DUMMY_EMAIL_PREFIX,
    email__endswith=DUMMY_EMAIL_DOMAIN,
).exclude(
    form_data_created__isnull=False,
)
user_count = orphaned.count()
orphaned.hard_delete()
```

Tiers 4 (generated administrations) and 5 (generated levels) are defined in
D-10, and must run last: every PROTECT pointing at `Administration` has to be
cleared by tiers 1–3 first.

**Explicitly NOT deleted**, with reasons:

| Not deleted | Reason |
|---|---|
| `Administration` / `Levels` **not** carrying `DUMMY-` | Real hierarchy, whether bulk-uploaded or seeded by `administration_seeder`. Only rows this command generated (D-10) are removed |
| `Forms`, `Questions`, `QuestionOptions` | Owned by `form_seeder`; deleting them would break real data |
| `Organisation` | The seeder only *reads* it (`fake_complete_data_seeder.py:217`), never creates one |
| `Role`, `UserRole`, `UserForms` | Cascade from `SystemUser` in tier 3 |
| `Entity` / `EntityData` | Created by `set_answer_data` via `get_or_create` (`functions.py:56,74`) and shared with real submissions — accepted, R-3 |
| Storage blobs (`datapoints/{uuid}.json`) | Written by `save_to_file`, and deliberately kept: `DUMMY-` data is also used for mobile debugging, which reads these — R-2 |

---

### D-6: `--tenant` is required, and `--clean` is tenant-scoped

**Decision**: `--tenant <subdomain>` is **required** (exempt under `--test`,
exactly as `--bbox` is), and `--clean` is scoped by it.

```python
parser.add_argument(
    "-t", "--tenant", type=str, default=None,
    help="Workspace subdomain to seed into. Required unless --test.",
)

# --test drives a closed fixture with no workspace, and is how all 34
# existing test callers invoke this command. Same exemption as --bbox (D-9).
tenant = None
if not is_test:
    if not options.get("tenant"):
        raise CommandError(
            "--tenant is required. 'default' exists on any migrated "
            "database (v1_users/0004_backfill_default_tenant.py)."
        )
    tenant = Tenant.objects.filter(
        subdomain=options["tenant"]
    ).first()
    if not tenant:
        raise CommandError(
            f"No workspace with subdomain '{options['tenant']}'."
        )
```

A fresh database always has a usable value: migration
`v1_users/0004_backfill_default_tenant.py` runs
`Tenant.objects.get_or_create(subdomain="default")`. `seeder.sh:79` must prompt
for a subdomain and pass it, alongside the `--bbox` prompt from D-9.

`--clean` composes with it: a clean is always scoped to one workspace.

**Rationale**: `FormData`'s tenant is derived, not stored
(`TENANT_PATH = "form__tenant"`, `v1_data/models.py:20`). An unscoped clean on
a multi-workspace install would delete another workspace's fake data, which is
a smaller version of the same class of accident D-2 guards against.

```python
# D-5 tier 1, tenant-scoped:
fake_data = FormData.objects_with_deleted.filter(
    name__startswith=DUMMY_PREFIX,
)
if tenant is not None:          # None only under --test
    fake_data = fake_data.filter(form__tenant=tenant)
```

The same scoping applies to tiers 2–5 — `MobileAssignment` via `user__tenant`,
`SystemUser` via `tenant`, `Administration` and `Levels` via `tenant`.

**Impact**: every unscoped lookup in the command becomes tenant-scoped, which
also closes finding F-1 from the visualization gap analysis:
`Forms.objects.filter(parent__isnull=True)` (`:78`, `:252`, `:303`),
`Organisation.objects.order_by("?")` (`:217`), `Role.objects.filter(...)`
(`:84`, `:241`), and both `create_user` calls (`:68`, `:232`), which currently
mint users with `tenant=None`.

**Breaking**: `seeder.sh:79` is the only non-`--test` caller and must be
updated. All 34 test callers pass `--test=true` and are exempt.

---

### D-7: Flag style — `--clean` as bool, not `nargs="?" type=int`

**Options Considered**:

1. Match `administration_seeder`:
   `parser.add_argument("-c", "--clean", nargs="?", const=1, default=False, type=int)`
2. Match this command's own `--approved` / `--draft`:
   `type=lambda x: x.lower() in ('true','1','yes','on')`

**Decision**: Option 2.

**Rationale**: local consistency beats global consistency here. Every other
flag on *this* command already uses the boolean-string parser
(`fake_complete_data_seeder.py:128-145`), and mixing the two styles inside one
`add_arguments` is how `--clean 0` ends up meaning "yes, clean" to a tired
reader. The int-style flag in `administration_seeder` is not worth propagating.

---

### D-8: A flag for "approved data only — no draft, no pending, no approval"

**Requested**: a new flag that seeds only approved data.

**Finding**: this behaviour already exists, and it is the default. Tracing all
three sub-conditions with the shipped defaults (`--approved true`,
`--draft false`):

```python
# fake_complete_data_seeder.py:317-323
data_is_draft = is_draft and (form_data_counts[f.name] % 2 == 1)
#               ^^^^^^^^ False  → data_is_draft is always False
data_is_pending = (
    not is_approved and (form_data_counts[f.name] % 2 == 1)
)
#   ^^^^^^^^^^^^^^^ False  → data_is_pending is always False

# fake_complete_data_seeder.py:288-301 — the approver tree is built only when
# approval is actually wanted, so with the default nothing is created.
if not is_approved:
    approver = SystemUser.objects.filter(...)
    if not approver:
        create_approvers_recursively(...)

# fake_complete_data_seeder.py:328-337 — both flags land as literal False.
form_data = FormData.objects.create(
    ..., is_pending=data_is_pending, is_draft=False,
)
```

Confirmed by inspection that nothing else reintroduces approval state: this
command creates no `PendingDataApproval` / `DataApproval` rows, and `v1_data`
registers **no** `pre_save` / `post_save` signal on `FormData`. `has_approval`
is consulted at exactly one place (`:366`), inside the draft branch, which the
default never enters.

So `python manage.py fake_complete_data_seeder -r 20` already yields exactly
approved data — no drafts, no pending rows, no approver accounts.

**Decision**: add no new flag. Make two corrections instead.

1. **Fix the misleading help text.** `--approved` does not mean "create
   approved data"; it means "skip the approval workflow entirely". The current
   string invites the reader to think there is a matching flag for the clean
   case when `--approved` *is* that flag.

   ```python
   parser.add_argument(
       "--approved",
       type=lambda x: x.lower() in ('true', '1', 'yes', 'on'),
       default=True,
       help=(
           "true (default): every row is approved — no pending rows, no "
           "approver accounts created. false: half the rows per form are "
           "left pending and an approver tree is built for them."
       ),
   )
   ```

2. **Guard the contradictory combination.** `--approved` and `--draft` are
   independent booleans today, so `--approved true --draft true` silently
   produces drafts despite the first flag reading like a promise of clean data.
   Fail fast rather than surprise:

   ```python
   if is_approved and is_draft:
       raise CommandError(
           "--draft true contradicts --approved true: approved data has no "
           "drafts. Pass --approved false to seed a mixed workflow."
       )
   ```

**Rationale**: a second flag whose effect is identical to the existing default
is a flag that will drift out of sync with it. The reported problem is
discoverability, and discoverability is fixed by `--help`, not by more surface.

**Impact**: no behaviour change for anyone already relying on the defaults.
`--approved true --draft true` changes from "silently seeds drafts" to a hard
error, which is the only backward-incompatible bit and is a bug fix.

**If a distinct flag is still wanted** after reading this, the cheap version is
an alias that sets the group explicitly rather than a fourth independent
boolean:

```python
# --approved-only: assert the clean combination regardless of other flags.
if options.get("approved_only"):
    is_approved, is_draft = True, False
```

---

### D-9: Coordinates come from a required `--bbox`, not from a country CSV

**Problem**: the seeder cannot run at all against a workspace it did not seed
itself. It reads `./source/{COUNTRY_NAME}_random_points.csv`
(`COUNTRY_NAME = "fiji"`, hardcoded at `mis/settings.py:289`) and matches the
CSV's `name` column against administration *names*:

```python
# fake_complete_data_seeder.py:153-156, 205-207
csv_path = f"./source/{COUNTRY_NAME}_random_points.csv"
fake_geo = pd.read_csv(csv_path)
...
geo = fake_geo_data[index]
adm = find_administration(geo["name"], last_level)   # → None for any
                                                     #   non-Fiji workspace
```

That file holds 102 rows / 86 unique names, all Fiji provinces (`Ba`, `Bua`,
`Cakaudrove`, `Macuata`, `Naitasiri`). It is therefore not an administration
list — it is a **coordinate table keyed by Fiji province name**, and it only
resolves because `administration_seeder` happens to seed Fiji's topojson under
the same names.

For any other workspace `find_administration` returns `None`
(`fake_complete_data_seeder.py:32-38`) and the very next line raises:

```python
parent_adm = adm.ancestors.exclude(parent__isnull=True).first()  # :210
# AttributeError: 'NoneType' object has no attribute 'ancestors'
```

caught by the bare `except Exception` at `:449` and reported as
`Error occurred: 'NoneType' object has no attribute 'ancestors'.` — which
tells the operator nothing about the actual cause.

**Decision**: drop the CSV from this command entirely. Administrations come
from the database (D-10); coordinates come from a **required** `--bbox`.

```python
parser.add_argument(
    "--bbox",
    type=str,
    default=None,
    help=(
        "Bounding box for generated geo points, as "
        "'minLng,minLat,maxLng,maxLat'. REQUIRED unless --test. There is "
        "deliberately no default: every workspace is a different country, "
        "and a silent Fiji default puts every pin in the wrong hemisphere."
    ),
)

# In handle(), before any work:
if not is_test and not options.get("bbox"):
    raise CommandError(
        "--bbox is required. Example for Fiji: "
        "--bbox '177.0,-18.3,180.0,-16.1'"
    )
```

**Rationale**: Fiji is one deployment. The platform is generic and every tenant
is a different country, so a default coordinate source is a default that is
wrong for everyone except one project. Making it required turns a silent
wrong-hemisphere bug into a one-line prompt at the point of use. It also
removes the last reason this command reads `COUNTRY_NAME`.

**`--test` is exempt.** 34 test files call
`call_command("fake_complete_data_seeder", "--test=true", ...)` and rely on
`TEST_GEO_DATA` (`v1_profile/constants.py:151-161`), whose points and names
line up with `DEFAULT_ADMINISTRATION_DATA`. Requiring `--bbox` unconditionally
would break all 34 at once for no benefit — `--test` is a closed fixture, not a
workspace.

**Impact**:
- `source/{COUNTRY}_random_points.csv` and the `pandas` read are removed from
  this command. The files stay in the repo for other consumers.
- `seeder.sh:79` must prompt for a bbox and pass it through.
- `find_administration()` is deleted along with the name matching (D-10).

```python
def random_point_in(bbox):
    """A [lat, lng] inside the bbox, in the order FormData.geo expects.

    FormData.geo is [Y, X] — latitude first. The CSV path built it as
    [geo["Y"], geo["X"]] (:206) and the map widgets read it that way, so
    the order is load-bearing, not cosmetic.
    """
    min_lng, min_lat, max_lng, max_lat = bbox
    return [uniform(min_lat, max_lat), uniform(min_lng, max_lng)]
```

---

### D-10: An empty hierarchy is auto-generated, prefixed, and cleaned

**Problem**: `configure_project` (`v1_users/views.py:496-503`) is the whole of
what a new workspace gets — one `Levels(level=0)` and one root
`Administration`, both tenant-scoped:

```python
level_zero = Levels.objects.create(
    name=validated["level_0_name"], level=0, tenant=user.tenant
)
Administration.objects.create(
    parent=None, level=level_zero,
    name=validated["root_unit_name"], tenant=user.tenant,
)
```

There is nothing below the root until someone bulk-uploads an administration
file. Seeding datapoints onto a bare root is possible but useless for the
purpose this seeder exists for: every datapoint lands on one administration, so
every administration filter returns everything and the map is a single pin.

**Decision**: when the target workspace has no administration below its root,
generate a throwaway hierarchy, mark it `DUMMY-`, and remove it in `--clean`.

```python
parser.add_argument("--depth", type=int, default=2,
                    help="Levels of throwaway hierarchy to generate below "
                         "the root when the workspace has none.")
parser.add_argument("--fanout", type=int, default=4,
                    help="Children per generated administration. "
                         "depth=2 fanout=4 gives 16 leaf units.")
```

```python
def ensure_hierarchy(root, tenant, depth, fanout, stdout):
    """Build a DUMMY- hierarchy under `root`, or return what already exists.

    Reuses any Levels the workspace already defines — a tenant may have
    levels 0..4 from its upload template with no units filled in yet — and
    only mints DUMMY- levels to reach `depth`. Levels are unique on
    (tenant, level) (v1_profile/models.py:27-32), so get_or_create on that
    pair is the safe form.
    """
    existing = Administration.objects.filter(
        parent__isnull=False, tenant=tenant,
    )
    if existing.exists():
        return list(existing.filter(
            level__level=existing.aggregate(m=Max("level__level"))["m"]
        ))

    parents = [root]
    for d in range(1, depth + 1):
        level, _ = Levels.objects.get_or_create(
            tenant=tenant, level=d,
            defaults={"name": f"{DUMMY_PREFIX}Level {d}"},
        )
        children = []
        for parent in parents:
            for i in range(fanout):
                # parent is set, so the pre_save receiver
                # (v1_profile/models.py:98-105) populates `path` — which is
                # what every visualization administration filter reads.
                children.append(Administration.objects.create(
                    name=f"{DUMMY_PREFIX}{level.name} {parent.id}-{i + 1}",
                    parent=parent, level=level, tenant=tenant,
                ))
        parents = children
    stdout.write(f"-- Generated {len(parents)} throwaway administrations")
    return parents
```

**Rationale**: it duplicates a slice of the bulk-upload path, which is the
argument against it, but the alternative is that this command simply does not
work on a freshly-registered workspace — which is now the normal way a
workspace comes into existence. The duplication is bounded (one function, no
Excel parsing, no attributes) and every row it writes is disposable by
construction.

**Relationship to [SEED-002](SEED-002-administration-csv-seeder.md)**: the two
are complements, not alternatives. `administration_csv_seeder` imports a *real*
hierarchy for a workspace someone intends to keep; D-10 generates a disposable
one for a workspace nobody does. The `existing.exists()` check above means that
running SEED-002 first makes D-10 a no-op, which is the intended ordering. Do
not use D-10 to stand up a workspace you plan to keep — every unit it creates
carries `DUMMY-` and is removed by `--clean`.

**Impact — this makes `--clean` order-sensitive.** `Administration` is
PROTECTed from five directions, including from itself:

| Referencing field | `on_delete` |
|---|---|
| `FormData.administration` (`v1_data/models.py:33`) | **PROTECT** |
| `DataBatch.administration` (`v1_approval/models.py:26`) | **PROTECT** |
| `DataApproval.administration` (`v1_approval/models.py:161`) | **PROTECT** |
| `EntityData.administration` (`v1_profile/models.py:166`) | **PROTECT** |
| `Administration.parent` (self-referential) | **PROTECT** |
| `UserRole.administration` | CASCADE |
| `AdministrationAttribute` link | CASCADE |
| `MobileAssignment.administrations` | M2M join |

So administrations must be deleted **after** all datapoints and **deepest level
first**. A `.all().delete()` — the shape `administration_seeder --clean` uses —
cannot work here, because the self-referential PROTECT fires on the parents.

```python
# --clean tier 4, after tiers 1-3 (D-5). Deepest level first: the
# self-referential PROTECT means a parent cannot go before its children.
fake_admins = Administration.objects.filter(name__startswith=DUMMY_PREFIX)
if tenant is not None:
    fake_admins = fake_admins.filter(tenant=tenant)
for level in sorted(
    {a.level.level for a in fake_admins}, reverse=True
):
    fake_admins.filter(level__level=level).delete()

# tier 5 — only DUMMY- levels, and only once no administration is left at
# them. Levels CASCADE to Administration, so an early or unguarded delete
# here would silently take real units with it.
Levels.objects.filter(
    name__startswith=DUMMY_PREFIX, tenant=tenant,
).exclude(administrator_level__isnull=False).delete()
```

**Note for the reviewer**: `administration_seeder --clean`
(`administration_seeder.py:158-161`) does `Levels.objects.all().delete()` then
`Administration.objects.all().delete()` with no ordering and no PROTECT
handling. It appears in **no test** and in neither `seeder.sh` nor
`seeder.prod.sh` — it is the only `--clean` in the repo and nothing exercises
it. Do not treat it as a working precedent; verify it by hand before copying
any part of its shape.

---

### D-9b: `--clean` is terminal, and `--clean-only` is gone

**Superseded**: the original contract had `--clean` wipe *then seed*, with
`--clean-only` for wipe-and-stop.

**Found in use**: an operator ran

```
fake_complete_data_seeder --tenant qa1 --clean=true --bbox "..."
```

saw five datapoints in Manage Data afterwards, and reported "clean is not
working". The clean had worked perfectly — it deleted five rows and the same
command then created five more. The output gave no hint that a second phase
had started:

```
-- Fake data cleared
Created 5 data entries for form EPS Water Quality Testing
```

**Decision**: one flag. `--clean` hard-deletes and returns.

**Rationale**: `--clean` reads as an imperative. A command that quietly
repopulates afterwards is indistinguishable, from the outside, from a clean
that silently failed — and the person who has to tell them apart is the one
who least expects to. Two flags one word apart, where the *shorter* one does
*more*, is the trap that produced the report.

Chaining covers the combined case, and says what it does:

```bash
manage.py fake_complete_data_seeder --tenant acme --clean && \
manage.py fake_complete_data_seeder --tenant acme --bbox "..." -r 20
```

**Impact**:
- `--bbox` is no longer required for a clean; a clean generates no points,
  so demanding a bounding box for one was pure friction. Only `--tenant`
  remains.
- `--clean` accepts both `--clean` and `--clean=true` (`nargs="?"`,
  `const=True`), so the bare imperative form works.
- The `refresh_materialized_data()` that ran only on the `--clean-only`
  path now runs on every clean, which it always should have: the view must
  not serve deleted datapoints.
- Tests: `test_clean_then_reseed_does_not_double` becomes two runs, and
  `test_clean_seeds_nothing` / `test_clean_needs_no_bbox` are added.

---

## 6. Type/Constant Mappings

| Surface | Constant | Literal value |
|---------|----------|---------------|
| Datapoint name | `DUMMY_PREFIX` | `"DUMMY-"` |
| Monitoring child name | `DUMMY_PREFIX` | `"DUMMY-2025-03-10 - Mon Mar 10 ..."` |
| Draft name | `DUMMY_PREFIX` | `"DUMMY-… - Draft"` |
| Submitter account | `DUMMY_EMAIL_PREFIX` + `DUMMY_EMAIL_DOMAIN` | `"dummy-user.<ns>@test.com"` |
| Approver account | same | `"dummy-approver.<adm><d>@test.com"` |
| Mobile assignment | `DUMMY_PREFIX` | `"DUMMY-<adm>.<username>"` |

### Creation sites to touch

| Line (current) | Object | Change |
|---|---|---|
| `:68` | approver `SystemUser` | email `dummy-approver.…@test.com` |
| `:232` | submitter `SystemUser` | email `dummy-user.<ns>@test.com` |
| `:267` | `MobileAssignment` | `name=f"{DUMMY_PREFIX}{uname}"` |
| `:328` → after `:341` | root `FormData` | `_mark_as_dummy()` after `add_fake_answers` |
| `:350` → after `:364` | draft `FormData` | `_mark_as_dummy()` after `add_fake_answers` |
| `:400` → after `:416` | monitoring child `FormData` | `_mark_as_dummy()` after `add_fake_answers` |
| *(new)* | generated `Administration` | `name=f"{DUMMY_PREFIX}…"` (D-10) |
| *(new)* | generated `Levels` | `name=f"{DUMMY_PREFIX}Level {d}"` (D-10) |

### Code removed by D-9

| Line | Removed |
|---|---|
| `:12` | `from mis.settings import COUNTRY_NAME` |
| `:1` | `import pandas as pd` (only used for the CSV read) |
| `:153-156` | `csv_path` / `pd.read_csv` / `sample(frac=1)` |
| `:32-38` | `find_administration()` — name matching is gone with the CSV |
| `:170-171` | `Levels.objects.order_by("-level").first()` — reads across every tenant; replaced by a per-tenant `Max("level__level")` (D-10) |

Note the approver-email change interacts with the restore path at
`fake_complete_data_seeder.py:58-66`, which looks up soft-deleted users by the
exact email string. That lookup must be updated in the same edit or it will
stop finding previously-seeded approvers and start minting duplicates.

---

## 7. Compatibility & Migration

### Backward Compatibility

- [x] Existing API consumers unaffected — no schema or serializer change.
- [x] Existing data preserved — the prefix applies only to newly generated
      rows. Data from *previous* seeder runs is unprefixed and therefore
      invisible to `--clean`; it must be removed by hand or by dropping the DB
      once. Called out in Open Questions.
- [ ] CLI tools still work — **`--tenant` and `--bbox` are breaking changes**
      for any non-`--test` invocation (D-6, D-9). Exactly one caller exists in
      the repo, `seeder.sh:79`, which must be updated in the same commit to
      prompt for both. All 34 test callers pass `--test=true` and are exempt.
      Every other flag keeps its behaviour and default; `--clean` defaults to
      `False`.

### Mobile App Impact

- [ ] Sync endpoints affected: **yes, indirectly.** `v1_mobile` sync serves
      datapoints by administration and mobile assignment. A device assigned to
      a `DUMMY-` mobile assignment will sync `DUMMY-`-named datapoints and
      display them. This is intended — it is the same "tell fake from real"
      benefit on the device.
- [x] SQLite schema changes: no.
- [ ] Version detection: n/a. But note that `--clean` hard-deletes rows a
      device may already hold locally; the device will not learn they are gone
      until its next full resync. Acceptable for a development tool; do not run
      `--clean` against a workspace with live field devices.

### Seeder/CLI Compatibility

- [x] Existing seeders work — `administration_seeder` and `form_seeder` are
      untouched and run before this command as they do today. This command no
      longer *depends* on `administration_seeder` having run (D-10).
- [ ] New seeder commands needed: none. This is a change to one existing
      command plus one shared constant.
- [ ] `./seeder.sh` must gain a bounding-box prompt (required by D-9) and
      should gain a "Clear existing fake data?" prompt:

      ```bash
      echo "Workspace subdomain? [default]"
      read -r subdomain
      subdomain="${subdomain:-default}"

      echo "Bounding box for generated points (minLng,minLat,maxLng,maxLat)?"
      echo "  Fiji: 177.0,-18.3,180.0,-16.1"
      read -r bbox

      python manage.py fake_complete_data_seeder \
          --repeat="${fake_data_count}" --monitoring="${monitoring_data_count}" \
          --approved="${approved}" --draft="${draft_data}" \
          --tenant="${subdomain}" --bbox="${bbox}"
      ```

---

## 8. Security Considerations

- [x] Permission model defined — management command, shell access only. No new
      HTTP surface, so no new authz decision.
- [x] Input validation specified — `--clean` is a boolean; there is no
      user-supplied pattern to inject. The delete filter is a hardcoded
      constant, never a CLI argument. **A `--prefix <str>` option must not be
      added**: it would turn `--clean` into an arbitrary
      `DELETE FROM form_data WHERE name LIKE $1`.
- [x] No new attack vectors introduced.
- [ ] **Destructive-operation review required.** `--clean` hard-deletes. The
      four guards are: (a) the delete key is the prefix, never `created_by`
      (D-2); (b) the prefix is a compile-time constant, not user input;
      (c) user deletion is additionally guarded on having no surviving
      `FormData`; (d) the command refuses to run when `settings.DEBUG` is
      `False` (R-4). A reviewer should confirm all four are present before this
      merges.

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | `_mark_as_dummy` is idempotent — calling it twice yields one prefix, not `DUMMY-DUMMY-`. |
| Unit | Prefix survives `add_fake_answers`: seed a form with a `meta: true` question, assert `name.startswith(DUMMY_PREFIX)` after the full create path. This is the D-3 regression and is the single most valuable test here. |
| Integration | `--clean` removes root, monitoring-child and draft `FormData` and cascades `Answers` to zero. |
| Integration | **`--clean` preserves real data.** Create an unprefixed `FormData` whose `created_by` is a user the seeder also reused; run `--clean`; assert the row and the user both survive. This is the D-2 regression. |
| Integration | `--clean` collects rows soft-deleted by an earlier run (`objects_with_deleted`, D-5 tier 1). |
| Integration | `--clean` is idempotent — second run deletes 0 and exits 0. |
| Integration | `--clean -r 5` wipes then reseeds; final count equals a fresh `-r 5`, not double. |
| Integration | Default run is approved-only (D-8): after `-r 5`, assert `FormData.objects.filter(is_pending=True).count() == 0`, `objects_draft.count() == 0`, and no `approver.*@test.com` account exists. |
| Unit | `--approved true --draft true` raises `CommandError` (D-8). |
| Unit | Omitting `--bbox` or `--tenant` without `--test` raises `CommandError` before any write; `--test=true` without either succeeds (D-6, D-9). |
| Integration | Two workspaces seeded separately: `--clean --tenant a` leaves workspace `b`'s `DUMMY-` data untouched (D-6). |
| Unit | `--clean` under `override_settings(DEBUG=False)` raises `CommandError` and deletes nothing (R-4). |
| Integration | The uploaded blob's `datapoint_name` carries `DUMMY-` — asserts the stamp landed before `save_to_file`, which is the R-2 / D-3 ordering contract. |
| Unit | Every generated `geo` falls inside the given bbox, in `[lat, lng]` order (D-9). |
| Integration | On a workspace with root only, `--depth 2 --fanout 4` generates 16 leaf administrations, all `DUMMY-` prefixed, all with a populated `path` (D-10). |
| Integration | On a workspace that already has a hierarchy, nothing is generated and the existing leaf units are used (D-10). |
| Integration | `--clean` removes generated administrations and levels deepest-first without raising `ProtectedError`, and leaves non-`DUMMY-` administrations and levels intact (D-10). |
| E2E (manual) | Seed, open the dashboard viewer, confirm `DUMMY-` appears in map popups, table widget rows and the datapoint list. |

```python
# Sketch of the D-2 regression — the test that matters most.
def test_clean_preserves_real_data_from_a_reused_user(self):
    call_command("administration_seeder", "--test")
    call_command("form_seeder", "--test")
    # A real submitter the seeder is free to pick up at line 218.
    real_user = self.create_submitter(...)
    real_row = FormData.objects.create(
        name="Real village survey", form=self.form,
        administration=self.adm, created_by=real_user, geo=[0, 0],
    )

    call_command("fake_complete_data_seeder", "-r", "2")
    call_command("fake_complete_data_seeder", "--clean-only")

    real_row.refresh_from_db()          # must not raise
    self.assertEqual(real_row.deleted_at, None)
    self.assertTrue(
        SystemUser.objects_with_deleted.filter(pk=real_user.pk).exists()
    )
    self.assertEqual(
        FormData.objects_with_deleted.filter(
            name__startswith=DUMMY_PREFIX
        ).count(),
        0,
    )
```

---

## 10. Resolved Questions & Open Items

### Resolved

**R-1 · Pre-existing unprefixed fake data — accepted, no backfill.**
Rows from earlier seeder runs carry no marker, so `--clean` cannot see them.
This is a new MIS with no accumulated seeder history worth rescuing, so no
backfill ships. This also avoids reintroducing the D-2 hazard: a backfill keyed
on `created_by.email LIKE '%@test.com'` would mark rows authored by *reused*
accounts, which is exactly the mis-attribution D-2 exists to prevent.
*Implication*: on any database that predates this change, unprefixed fake rows
survive `--clean` and must be removed by hand or by dropping the database once.

**R-2 · Storage blobs are kept, and `save_to_file` stays.**
`--clean` removes the database rows but leaves `datapoints/{uuid}.json` in
storage. Accepted: the blobs are wanted, because `DUMMY-` data is also used for
**mobile debugging**, and that path reads the generated JSON.

This makes the D-3 ordering constraint load-bearing rather than incidental. The
blob embeds the datapoint name:

```python
# v1_data/models.py:113-124 — @property, so the bare attribute access at
# fake_complete_data_seeder.py:377 DOES execute.
@property
def save_to_file(self):
    ...
    data = {"id": self.id, "datapoint_name": self.name, ...}
```

So the prefix must be stamped **before** `save_to_file` runs, or the mobile
debugging payload says `Kramat Jati` while the database says
`DUMMY-Kramat Jati`. The stamp goes strictly between `add_fake_answers`
(`:341`) and `save_to_file` (`:377`) — after the first because it overwrites
`name`, before the second because it serialises `name`.

*Implication*: blobs accumulate across `--clean` cycles. They are keyed by
`uuid`, so they never collide, and nothing reads a blob whose row is gone.
Accepted as a known, bounded leak.

**R-3 · `Entity` / `EntityData` are not deleted — acceptable.**
`set_answer_data` creates entity rows via `get_or_create` for entity-cascade
questions (`v1_data/functions.py:56-78`). They are shared with real
submissions and are not prefixed, so an entity-cascade dropdown keeps showing
seeder-invented options after a `--clean`. Confirmed acceptable — deleting them
would risk removing entities a real submission references, and `EntityData.
administration` is `PROTECT` besides.

**R-4 · `--clean` refuses to run when `DEBUG=False`.**
Confirmed. The guard makes the destructive path impossible to trigger under
production configuration, independent of the three guards in §8.

```python
from django.conf import settings

if (clean or clean_only) and not settings.DEBUG:
    raise CommandError(
        "--clean is refused when DEBUG=False. This hard-deletes rows and "
        "is a development tool; it must never run against a production "
        "configuration."
    )
```

Note this is a *configuration* guard, not an environment guard: a staging
deployment running with `DEBUG=True` is still allowed to clean, which is the
intended behaviour since staging is where dashboard debugging happens.

### Still open

- [ ] **Retire `administration_seeder`** once
      [SEED-002](SEED-002-administration-csv-seeder.md) lands. Its three
      defects (D-1 there) are not worth fixing, because
      `administration_csv_seeder` replaces every non-test caller. The only
      dependency to unpick is the `--test` fixture used by 30+ tests. Deletion,
      not repair — see SEED-002 D-7.
- [ ] **`administration_seeder` needs its own fix, out of scope here.** The
      review that produced D-10 found three defects in it that this task does
      not touch and that affect real (non-`DUMMY-`) data:
      1. `update_or_create(name=name, defaults={...})`
         (`administration_seeder.py:67`) keys on **name alone** — no parent,
         no level, no tenant. Same-named units under different parents
         collapse into one row and the last writer wins the `parent`. Compare
         `administrations_bulk_upload.py:88-93`, which correctly keys on
         `(name__iexact, level, parent, tenant)`.
      2. It writes `tenant=None` throughout, so combined with
         `unique_root_administration_per_tenant` it can only ever build one
         hierarchy per install.
      3. `path` goes stale on update: `set_administration_path` returns early
         on `if instance.path: return` (`v1_profile/models.py:98-105`), so a
         row reparented by defect 1 keeps its old ancestry — and `path` is
         what every visualization administration filter reads
         (`v1_visualization/functions.py:28-43`). Silent wrong aggregates.

      Recommend a separate task; folding it in would make this change
      unreviewable. [SEED-002](SEED-002-administration-csv-seeder.md) D-1
      records the same three defects as the reason it does not extend that
      command either.

---

## 10b. Implementation Notes (deviations found while building)

Three things the design did not anticipate. All are in the shipped code;
none changes a decision, but a reviewer should know why the code differs
from the snippets above.

### I-1: `--test` keeps `find_administration` and `TEST_GEO_DATA`

D-9 says the CSV name-matching and `find_administration()` are deleted.
They are deleted from the **normal** path, but retained for `--test`.

34 test files call this command as `--test=true`, and `TEST_GEO_DATA`
(`v1_profile/constants.py:151-161`) is a closed fixture whose names line up
with `DEFAULT_ADMINISTRATION_DATA` at several different depths. Routing
`--test` through `pick_target_administrations` instead would attach every
fixture datapoint to the two deepest villages, changing the administration
distribution those 34 files were written against. The exemption keeps them
byte-identical.

`find_administration` is now tenant-scoped, so it no longer reads across
workspaces the way `Levels.objects.order_by("-level").first()` did.

### I-2: `pick_role()` — generated levels have no roles

`UserRole.role` is **not** nullable, and the original code passed whatever
`Role.objects.filter(administration_level=...).first()` returned straight
into `user_user_role.create(role=role)`. A generated hierarchy (D-10)
creates levels `default_roles_seeder` never saw, so the level-exact lookup
legitimately misses and the seeder died on an IntegrityError several frames
later.

```python
def pick_role(data_access, level, tenant):
    base = Role.objects.filter(
        role_role_access__data_access=data_access, tenant=tenant
    )
    role = base.filter(administration_level=level).order_by("?").first()
    if role:
        return role
    role = base.order_by("?").first()      # any role with this access
    if role:
        return role
    raise CommandError(
        "This workspace has no role granting ... Run default_roles_seeder."
    )
```

The fallback is deliberate rather than silent: fake data needs *a* role,
not the anatomically correct one, and the third branch turns a missing
`default_roles_seeder` run into a sentence instead of a traceback.

### I-3: `--clean` must refresh the materialized view before tier 4

`ViewDataOptions.administration` is `on_delete=PROTECT`
(`v1_visualization/models.py:28-32`). The model is `managed = False` — it
maps a matview with no real FK constraint — but Django's collector does not
know that and evaluates the PROTECT anyway.

After tier 1 removes the datapoints, `view_data_options` still holds their
rows until it is refreshed, so tier 4 raised:

```
ProtectedError: Cannot delete some instances of model 'Administration'
because they are referenced through protected foreign keys:
'ViewDataOptions.administration'
```

The fix is a `refresh_materialized_data()` between tier 1 and tier 4, which
is correct independently of the delete: the view must not serve datapoints
that no longer exist.

### I-4: D-8's breaking change, realised

`--approved true --draft true` now raises, as designed. Five existing call
sites relied on the old silent behaviour and were updated to pass
`--approved=false`, which is what they meant — drafts only exist in a mixed
workflow:

| File | Change |
|---|---|
| `v1_data/tests/tests_draft_data_list.py:29` | `approved=False` added |
| `v1_data/tests/tests_delete_draft_data.py:29` | `approved=False` added |
| `v1_data/tests/tests_draft_data_details.py:29` | `approved=False` added |
| `v1_data/tests/tests_fake_complete_data_seeder.py` | 2 call sites |
| `seeder.sh` | answering "y" to drafts now forces `approved=false` |

---

## 11. References

- Related tasks:
  - [SEED-002 Administration CSV seeder](SEED-002-administration-csv-seeder.md) — the real-hierarchy counterpart to D-10
  - [MT-002 Tenant scoping (database)](MT-002-tenant-scoping-database.md) — D-6
  - [VIZ-009 Legacy dashboard removal](VIZ-009-legacy-dashboard-removal.md) — the surface this data feeds
  - [VIZ-010 Visualization quick wins](VIZ-010-visualization-quick-wins.md) — QW-2 needs 50+ geolocated fake points
- Prior art:
  - `administration_seeder --clean` (`api/v1/v1_profile/management/commands/administration_seeder.py:151-161`) — the existing clean convention, deliberately not copied (D-7)
  - `utils/soft_deletes_model.py` — the soft/hard delete semantics behind D-4
  - `utils/draft_model.py` — why `FormData.objects` includes drafts but excludes deleted rows

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-08-31 | Draft |
| Tech Lead | | | |
| Product | | | |
