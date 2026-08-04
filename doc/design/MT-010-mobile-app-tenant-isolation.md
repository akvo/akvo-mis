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
through a scoped queryset. This iteration closes all four.

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
  caller (`tenant=None`) and the test path keep writing to the current root
  location (with the `test_` prefix), so seeders and the existing suite are
  unchanged.
- The `generate_sqlite` management command loops over tenants, and still emits
  the tenant-less and test artifacts its callers expect.

`update_sqlite(model, data, tenant=None, id=…)`:

- Resolve the same per-tenant file path and upsert the single row there. The
  Administration, Organisation and Entity serializer callers pass the
  instance's tenant.
- The administration bulk-upload handler (a follow-through owned by the
  bulk-upload iteration) regenerates the uploading tenant's file, passing
  `user.tenant`. That is noted here for cross-reference, not implemented in
  this iteration.

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
The app's request must carry it. Its api client likely attaches the token to
all requests, but confirm this, or the download 401s.

### 3. Form-details membership check

`get_mobile_form_details(form_id)`: after resolving the assignment, reject a
`form_id` that is not in `assignment.forms` with a 404, so existence is not
revealed, before serializing the form. This mirrors the guard
`get_datapoint_download_list` already applies.

### 4. Sync form-in-assignment validation

`sync_pending_form_data`: validate that the submitted `formId` is in
`assignment.forms` before building and saving the submission, returning 404 on
a non-member form. This blocks a device submitting data against another
tenant's form.

### 5. Forms-tree scoping

`get_forms_tree`: route both the outer `registration_forms` query and the
`children` prefetch through `Forms.objects.for_user(request.user)`, so the
assignment-builder UI shows only the caller's tenant's published forms.

## Error handling

- SQLite download: a missing file is generated then served; an unknown or
  whitelist-failing filename returns 404; a missing or invalid mobile token
  returns 401. A tenant with no data yet yields an empty but valid file.
- Form-details and sync: a form not in the assignment returns 404, revealing
  nothing about other tenants' forms.
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
  an unauthenticated request returns 401.
- Form-details: a device gets details for a form in its assignment; a
  form_id outside the assignment returns 404.
- Sync: a submission against an in-assignment form succeeds; one against an
  out-of-assignment form returns 404 and nothing is written.
- Forms-tree: the tree shows only the caller's tenant's published forms, and
  a second tenant's forms never appear.
- Regression: the full backend suite passes, since tenant-less generation and
  assignment-scoped fixtures are unchanged.

## Out of scope

- APK endpoints (`download_apk_file`, `check_apk_version`, `upload_apk_file`),
  which serve the global app binary rather than tenant data. Protecting
  `upload_apk_file` is a separate security concern, not a tenancy one.
- The mobile sync and cascade wire format.
- Subdomain routing. This iteration keys off the mobile token's tenant rather
  than the host, and does not depend on it.
