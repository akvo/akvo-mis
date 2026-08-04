# Administration bulk-upload hardening: design

## Problem

Populating administrative units is the main onboarding data path after a
tenant defines its levels, and it happens through a spreadsheet upload. As it
stands the flow is unsafe and, under tenancy, incorrect:

1. The template leaks across tenants. Every level lookup in
   `utils/upload_administration.py` reads `Levels.objects.order_by('level')`
   unscoped, so a tenant's template would carry every tenant's level columns.
2. The seeder matcher leaks across tenants. `seed_administrations` matches
   existing units by `name__iexact` plus level and parent with no tenant
   filter, so tenant A uploading "Nairobi" can graft onto tenant B's
   "Nairobi."
3. Blank rows silently truncate. `seed_administrations` returning falsy
   `break`s the record loop, skipping the rest of the file and reporting
   success.
4. Status is not pollable. The upload endpoint creates no `Jobs` row;
   errors reach the operator only by emailed CSV, minutes later.
5. The UI reports success on HTTP 200, which means only that the file was
   received.

There is also no guard preventing a tenant from uploading before its hierarchy
is meaningfully defined, and the template's level-0 column must reconcile with
the single root unit that registration and configuration already created.

This iteration hardens the whole path: a readiness gate, tenant-correct
templates and matching, blank-row rejection, and a pollable job with honest UI
status.

## Decisions (from brainstorming)

- Full scope in one iteration. The gate, template scoping, seeder
  scoping, blank-row rejection, and the pollable job are entangled in one flow
  and ship together.
- The gate is "level 0 named plus at least one level ≥ 1", applied to both
  the template download and the upload. Post-configuration level 0 is always
  named, so this effectively means "the tenant has added at least one level
  below the root."
- The frontend computes the gate from the levels store (`getLevels()`), with
  no new endpoint; the backend enforces it independently on both endpoints.
- Blank rows reject the whole file, with a validation error naming the row.
  Nothing imports until it is fixed.
- Entity template scoping is folded in. The entities template shares the
  same unscoped `Levels`, so it is scoped in the same pass.
- Root reconciliation happens via pre-fill plus match. The blank template
  pre-fills every row's level-0 cell with the tenant's named root; the seeder
  resolves level 0 to the tenant's existing single root; a row whose level-0
  cell does not equal the root name is a validation error, not a second-root
  creation.

## Components

### 1. The readiness gate

A helper `bulk_upload_ready(user)` on `Levels.objects.for_user(user)`:

    returns True iff a Levels row at level 0 has a non-empty name
            AND a Levels row at level >= 1 exists

It is enforced in two places:

- Template export (`export_administrations_template` and the entities
  template export) returns 400 with a message directing the user to
  Levels management when the gate is unmet.
- Upload (`upload_bulk_administrators`) returns the same 400 before accepting
  the file.

On the frontend, the upload page derives the same predicate from the levels
store (`getLevels()`) and disables Download Template and Upload with an inline
explanation until the gate is met. The backend check is authoritative; the
client hint is UX only.

### 2. Template tenant-scoping

Thread the acting user (already carried by `generate_administration_excel`
and `generate_entities_data_excel`) into the generators and scope every level
and administration lookup with `for_user`:

- `generate_template` (l.26), the blank upload template.
- `generate_administration_template` (l.78, l.105), the prefilled admin
  download.
- `fill_administration_data` (l.197, l.200), prefilled entities data.
- `generate_entities_template` (l.221), the entities template.

Each tenant's template then contains only its own level columns.

Level-0 pre-fill: the blank `generate_template` pre-fills every data row's
level-0 cell with the tenant's root unit name, so the operator fills only the
deeper columns and cannot accidentally invent a conflicting root.

Legacy note, not reworked: `fill_administration_data` (l.185) reads a
country CSV (`ADMINISTRATION_CSV_FILE`), a single-country artifact predating
tenancy. It is scoped where it touches `Levels` and `Administration`, but the
CSV prefill path itself is legacy and left for a later cleanup.

### 3. Seeder tenant-scoping and root reconciliation

`seed_administrations` receives the uploader's tenant. The handler already
loads the user, and write-enforcement already threads the tenant for stamping
new rows. Two changes:

- Match within the tenant. The existing-unit lookup filters
  `Administration.objects.for_user(user)` (or an explicit `tenant=` filter), so
  a name match can never cross tenants.
- Resolve level 0 to the existing root. For the level-0 column, the seeder
  matches the tenant's single root (`parent=None`) rather than creating a new
  one. The validator below guarantees the cell equals the root name, so the
  match always succeeds and no second root is attempted.

### 4. Blank-row and root-mismatch validation

`validate_administrations_bulk_upload` gains two checks, both producing an
`ExcelError` entry naming the offending row and cell:

- Blank row: a row whose level cells are all empty is an error.
  `administrations_bulk_upload.py`'s `break` becomes `continue` as a backstop,
  but validation rejects the file first.
- Root mismatch: a row whose level-0 cell does not equal the tenant's
  root unit name is an error, which prevents the second-root constraint
  violation.

`ValidationText` gains the two messages. The import is already
`@transaction.atomic`, so a rejected file imports nothing.

### 5. Pollable job

- Add `JobTypes.seed_administration_data = 9` with its `FieldStr` entry.
- `upload_bulk_administrators` creates a `Jobs` row (status `pending`) and
  returns its `job_id` alongside the existing `task_id`.
- `handle_administrations_bulk_upload` sets the row to `done` or `failed` at
  every terminal branch (validation failure, missing sheet, success),
  storing the error-CSV path in `result` on failure. `task_id` is threaded
  from the view into the handler.
- The emailed error CSV remains as a secondary channel.

### 6. Honest UI status

`UploadAdministrationData.jsx` stops rendering success on the upload response.
Instead it polls `GET /api/v1/jobs/{job_id}` and renders:

- `pending` and `on_progress` as a pending state while the import runs;
- `failed` (3) as a failure state with the errors;
- `done` (4) as success, only once rows are actually imported.

The polling interval is cleared on unmount and on every terminal branch.

## Error handling

- Gate failures and validation errors (blank row, root mismatch) are 400s with
  clear messages, before any write.
- Import failures surface through the polled `Jobs` row, not a false success.
- The atomic import guarantees all-or-nothing; a rejected file changes nothing.
- Tenant scoping on both the template and the matcher guarantees no
  cross-tenant read or write through this path.

## Testing

- Gate: template export and upload return 400 when level 0 is unnamed or
  no level ≥ 1 exists; both succeed once the gate is met; the frontend disables
  the controls until then.
- Template scoping: a tenant's administration and entities templates
  contain only that tenant's level columns; the level-0 column is pre-filled
  with the tenant's root name.
- Seeder scoping: an upload by tenant A never matches or modifies tenant
  B's units of the same name; A's units are created and stamped under A.
- Blank row: a mid-file blank row rejects the whole file with the row
  named; a fixed file imports fully.
- Root mismatch: a row whose level-0 cell differs from the root name is
  rejected; a matching cell builds children under the existing root with no
  second root created.
- Job: the upload response carries `job_id`; every terminal branch sets a
  status; the UI shows pending then success or failure, and never success
  while running.
- Regression: existing seeder and test paths (tenant-less) still pass, since
  the tenant filter degrades to `tenant IS NULL` for tenant-less callers.

## Out of scope

- The prefilled-template code-column defect and the legacy country-CSV prefill
  path. Both are flagged, not reworked.
- Entity *data* bulk upload beyond template scoping. The same job and status
  hardening for entities, if wanted, is a follow-up.
- Subdomain routing.
