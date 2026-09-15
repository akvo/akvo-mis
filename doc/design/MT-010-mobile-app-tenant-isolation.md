# Mobile app tenant isolation: design

## Problem

The mobile surface is largely tenant-safe *by construction*: device endpoints
authenticate via a `MobileAssignmentToken` to an `assignment`, and most scope
their data by the assignment's `forms` and `administrations`. Because
write-path enforcement makes an assignment reference only its own tenant's
objects, an endpoint that filters by the assignment is transitively
single-tenant.

An audit of every mobile endpoint found four places that break or bypass
that guarantee:

1. Offline SQLite is global and public. `generate_sqlite`
   (`utils/custom_generator.py:18`) dumps every tenant's `Administration`,
   `Organisation`, `Entity` and `EntityData` into one global file per model;
   `download_sqlite_file` (`v1_mobile/views.py:312`) serves those by filename
   with no permission class (DRF default `AllowAny`) and a raw
   `os.path.join` open, which is a path-traversal risk. A device downloads
   every tenant's data offline, without auth.
2. `get_mobile_form_details` does `get_object_or_404(Forms, pk=form_id)`
   with no assignment or tenant check, so any device can fetch any form's full
   definition by id.
3. `sync_pending_form_data` does `get_object_or_404(Forms, pk=formId)`
   with no form-in-assignment check, so a device can submit against another
   tenant's form.
4. `get_forms_tree` returns `Forms.objects.filter(...)` unscoped, so the
   assignment-builder UI shows every tenant's published forms.

Read-path isolation did not catch these: (1) is a management command plus a
static file server, and (2) through (4) fetch by explicit id rather than
through a scoped queryset.

**Revised at implementation time.** MT-003 landed after this design was
written and already routes both id lookups through
`Forms.objects.for_user(assignment.user)` (`v1_mobile/views.py:143` and
`:198`), so (2) and (3) no longer leak across tenants. What this design
additionally proposed there — checking the form is in `assignment.forms`
rather than merely in the same tenant — is device-to-device hardening
inside one tenant, not a tenancy fix, so it moved out of scope. This
iteration implements (1) and (4).

The APK endpoints (`download_apk_file`, `check_apk_version`, `upload_apk_file`)
are out of scope, since they serve the global app binary rather than tenant
data.

## Decisions (from brainstorming)

- Full mobile isolation in one iteration. The four fixes share the theme
  (a device or assignment-builder must only reach its own tenant) and are
  small individually.
- Per-tenant SQLite in per-tenant subdirectories:
  `MASTER_DATA/<subdomain>/<table>.sqlite`, keeping the logical filenames, so
  the mobile app's form-definition references (`administrator.sqlite`) need no
  change. The download endpoint maps the logical name to the caller's tenant
  file.
- Lazy generation. The download generates a tenant's file on demand if
  absent, then serves it; `update_sqlite` keeps it fresh afterward. There is no
  coupling to registration or config, and no device ever 404s on a
  valid-but-ungenerated file.
- Assignment membership is the check for device endpoints. Form-details
  and sync validate the form against `assignment.forms`; the forms-tree, a web
  `IsAuthenticated` endpoint, scopes via `for_user`.

## Components

### 1. Per-tenant SQLite generation

`generate_sqlite(model, tenant=None, test=…)`:

- Scope the dump: `model.objects.filter(**{model.TENANT_PATH: tenant})`, which
  means `Administration`, `Organisation` and `Entity` by `tenant`, and
  `EntityData` by `entity__tenant`.
- Write to `MASTER_DATA/<tenant.subdomain>/<table>.sqlite`. A tenant-less
  caller (`tenant=None`) keeps writing to the current root location, so
  seeders and the existing suite are unchanged.
- *Implemented:* the `test_` prefix is orthogonal to the tenant directory
  rather than forcing the root location — a tenant file under test is
  `MASTER_DATA/acme/test_administrator.sqlite`. Folding the test path back
  to the root, as first written here, would have made per-tenant generation
  untestable. `sqlite_path(model, tenant, test)` is the one place that
  resolves this, so generation, update and download cannot disagree.
- *Implemented:* the frame is built with `columns=field_names`, so a tenant
  with no rows yet gets a valid empty `nodes` table instead of no file. The
  previous `if no_rows < 1: return` meant a tenant with no entities would
  404 on `entity_data.sqlite`, which its forms still reference.
- The `generate_sqlite` management command loops over tenants, and still emits
  the tenant-less and test artifacts its callers expect.

`update_sqlite(model, data, tenant=None, id=…)`:

- Resolve the same per-tenant file path and upsert the single row there. The
  Administration, Organisation and Entity serializer callers pass the
  instance's tenant.
- *Implemented here, not deferred.* The bulk-upload handlers
  (`v1_jobs/job.py`, administrations and entity data) regenerate the
  uploading tenant's file, passing `user.tenant`. This was originally
  cross-referenced to the bulk-upload iteration, but MT-007 had already
  merged: leaving it would have made per-tenant files go stale after every
  bulk upload, since the handlers refreshed only the root file that devices
  no longer read. That is a regression this iteration introduces, so this
  iteration fixes it.

### 2. Authenticated, tenant-resolved SQLite download

`download_sqlite_file`:

- Add `permission_classes([IsMobileAssignment])`.
- Resolve the tenant from `request.auth.assignment.user.tenant`.
- Whitelist the requested logical name against the known set
  (`administration`, `organisation`, `entity`, `entity_data`, matching the
  model `db_table` names and `administrator.sqlite`). Reject anything else with
  404. This removes the raw `file_name` path join and its `..` traversal risk.
- Serve `MASTER_DATA/<tenant.subdomain>/<whitelisted-name>`, generating it
  via `generate_sqlite(model, tenant)` if absent, then streaming it.

App-side note: the endpoint was public and now requires the mobile token.
*Confirmed at implementation time:* it did **not** carry one.
`cascades.download` (`app/src/lib/cascades.js`) called
`FileSystem.downloadAsync` with `{cache: false}` and no headers, bypassing
the axios client entirely, so the endpoint would have 401'd for every
device. The fix passes `api.getConfig().headers` through, which covers all
call sites at once. The three live callers (`AuthForm`, `AddUser`, `Home`)
all set the token before downloading; the two in `Settings/AddNewForm` and
`AuthByPassForm` call `/forms/{id}`, which has no backend route and was
already dead.

Because of this the backend and the app must ship together.

### 3. Form-details membership check — dropped

Superseded by MT-003: `get_mobile_form_details` already resolves through
`Forms.objects.for_user(assignment.user)`, so a foreign tenant's form 404s.
The remaining `assignment.forms` membership check is same-tenant hardening
and is tracked separately.

### 4. Sync form-in-assignment validation — dropped

Same as above: `sync_pending_form_data` already scopes its `formId` lookup
by `for_user`, so a device cannot submit into another tenant's form.

### 5. Forms-tree scoping

`get_forms_tree`: route both the outer `registration_forms` query and the
`children` prefetch through `Forms.objects.for_user(request.user)`, so the
assignment-builder UI shows only the caller's tenant's published forms.

## Error handling

- SQLite download: a missing file is generated then served; an unknown or
  whitelist-failing filename returns 404; a missing or invalid mobile token
  returns 401. A tenant with no data yet yields an empty but valid file.
- Forms-tree: out-of-tenant forms are simply absent from the result.
- Tenant-less and test paths: all generation degrades to the current
  root-location behavior for `tenant=None`, so no seeder or test fixture
  changes.

## Testing

- SQLite generation: for two tenants with distinct administration,
  organisation, entity and entity-data rows, each tenant's file contains only
  its own rows; the tenant-less and test generation still writes the root
  artifacts.
- SQLite download: a device downloads only its tenant's file; a missing
  file is generated on first request; an unknown or `..` filename is rejected;
  an unauthenticated request returns 401 and a web JWT 403.
- Serializer routing: creating an administration writes the new row into its
  own tenant's file, not the root one.
- Forms-tree: the tree shows only the caller's tenant's published forms, and
  a second tenant's forms never appear.
- Regression: the full backend suite passes, since tenant-less generation and
  assignment-scoped fixtures are unchanged.

*Implemented:* `api/v1/v1_mobile/tests/tests_sqlite_tenant_isolation.py`
(14 tests) and `tests_forms_tree_tenant_isolation.py` (2). The pre-existing
`tests_sqlite_generation.test_sqlite_file_endpoint` asserted the endpoint
was reachable anonymously — it encoded the bug, so it now authenticates as
a device, with a sibling test pinning the 401.

The app-side assertion (`cascades.download` sends the token) is written in
`app/src/lib/__test__/cascades.test.js` but **could not be executed**: the
mobile jest environment is broken in this repo independently of this work —
`jest.config.js` omits `ts`/`tsx` from `moduleFileExtensions`, so
`jest-expo`'s preset cannot resolve `expo-modules-core/src/Refs`, and every
suite fails to load. Adding the extensions gets past that but then 63 of 69
suites fail on missing native modules. Worth its own issue.

## Out of scope

- APK endpoints (`download_apk_file`, `check_apk_version`, `upload_apk_file`),
  which serve the global app binary rather than tenant data. Protecting
  `upload_apk_file` is a separate security concern, not a tenancy one.
- The mobile sync and cascade wire format.
- Subdomain routing. This iteration keys off the mobile token's tenant rather
  than the host, and does not depend on it.
- The global passcode namespace. `MobileAssignment.objects.get(passcode=...)`
  (`v1_mobile/views.py:118`) is unscoped, and passcodes are 8 lowercase
  letters from `random` (not `secrets`) with no unique constraint. Across
  tenants that means a guessed passcode enrolls a device into whichever
  tenant owns it, and two tenants can collide into a 500. Tracked separately.
- Repairing the mobile jest environment (see Testing).
