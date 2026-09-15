# v1_jobs export/download tenant scoping: design

## Problem

An audit of every upload and download endpoint found that the read- and
write-isolation iterations covered `v1_data`, `v1_forms`, `v1_users`,
`v1_profile`, `v1_mobile`, and `v1_visualization`, but not `v1_jobs`, the
async export/download system. That app has real, unaddressed cross-tenant
leaks:

1. `download_file/{file_name}` does `get_object_or_404(Jobs, result=file_name)`
   then streams the file, with no ownership check. Any authenticated user
   can download any tenant's exported data file by its result filename.
   It is the web analog of the mobile SQLite leak.
2. `download_status/{task_id}` does `get_object_or_404(Jobs, task_id=…)` with
   no ownership check, leaking another tenant's job status and existence.
3. `upload_excel/{form_id}` does `get_object_or_404(Forms, pk=form_id)` with
   no tenant check, so a user can bulk-upload submission data into another
   tenant's form.
4. `download_generate` and `download_data_report` take a request-supplied
   `administration_id` and `form_id` and hand them to the async export task,
   which builds `FormData` queries from them. If those ids aren't
   tenant-validated, a user can export another tenant's data by passing its
   ids.

`Jobs` has a `user` FK (`related_name="user_jobs"`), so its tenant path is
`user__tenant`. The scoping key is available; these endpoints simply don't
use it.

## Decisions (from brainstorming)

- Per-user ownership on downloads. `download_file` and `download_status`
  scope by `user=request.user`, so you can only reach jobs you created. This
  matches the existing `download_list` (`request.user.user_jobs`) and treats
  an export as a personal artifact; a same-tenant colleague cannot grab your
  file by guessing its name.
- Two independent barriers for exports. Reject a foreign form or
  administration id at request time via tenant-scoped serializer fields (400),
  and scope the worker's `FormData` query by the job's tenant, so a
  slipped-through id or a future export caller can't leak.
- `upload_excel` (and `upload_bulk_entities` if it shares the gap) validate
  the target form against the tenant.

## Components

### 1. Ownership on the download-serving endpoints

- `download_file(file_name)` becomes
  `get_object_or_404(Jobs.objects.filter(user=request.user), result=file_name)`,
  so a file whose job belongs to another user returns 404 before any storage
  read.
- `download_status(task_id)` becomes
  `get_object_or_404(Jobs.objects.filter(user=request.user), task_id=task_id)`.
- `download_list` is already `request.user.user_jobs` and is unchanged. It is
  the per-user boundary the other two now match.

### 2. Tenant-scope the export-request FK inputs

`download_generate` uses `DownloadDataRequestSerializer`; the data-report
endpoint uses its own request serializer. In both, the fields referencing
tenant-owned objects (`form_id`, `administration_id`, `child_form_ids`,
`selection_ids`) become tenant-scoped, via `TenantScopedPrimaryKeyRelatedField`
or a `for_user`-scoped queryset for the list fields, so a foreign id fails
validation with a 400 before a `Jobs` row is created. `selection_ids`, meaning
specific datapoints, resolve through a `FormData` queryset scoped by
`for_user`.

### 3. Validate the bulk-data-upload form

- `upload_excel(form_id)`: scope the form lookup to
  `get_object_or_404(Forms.objects.for_user(request.user), pk=form_id)`, so a
  bulk data upload against another tenant's form returns 404 and writes
  nothing.
- `upload_bulk_entities`: audit for the same pattern; if it fetches a
  form, entity or administration by id without scoping, apply the same
  `for_user` guard. Its administration and entity stamping is already handled
  by write-enforcement; this covers the *input* validation.

### 4. Belt-and-suspenders async export scoping

The export tasks build `FormData` queries in the worker
(`job_generate_data_download`, `job_generate_data_report`, and the monitoring
export). Each already receives the job, and therefore `job.user`. Scope their
`FormData` querysets by that user's tenant, using
`FormData.objects.for_user(job.user)` as the base before the existing form,
administration and date filters, so even an id that slipped past component 2,
or a new caller of the task, cannot export cross-tenant rows.

## Error handling

- A `download_file` or `download_status` request for a job the caller did not
  create returns 404, so ownership is not revealed.
- A foreign `form_id`, `administration_id` or `selection_id` in an export
  request returns 400 at validation, before a job exists.
- An `upload_excel` or bulk-entities request against a foreign form returns
  404 and writes nothing; the import is atomic.
- The worker scopes to `job.user`'s tenant; a tenant-less job (test or legacy)
  scopes on NULL, matching the isolation model.

## Testing

- Downloads: a user downloads and polls their own job; another user's file
  name or task id returns 404. `download_list` still shows only the caller's
  jobs.
- Export inputs: an export request naming the caller's form or administration
  succeeds; naming another tenant's form, administration, or datapoint
  selection returns 400 and creates no `Jobs` row.
- Bulk-data upload: an upload against the caller's form runs; against another
  tenant's form it returns 404 and writes nothing.
- Async defense in depth: invoking the export task directly with a foreign
  form or administration id still produces a file with no cross-tenant rows,
  because the worker-side `for_user(job.user)` scope holds independently of the
  request validation.
- Regression: the full backend suite passes. Tenant-less jobs and
  seed data scope on NULL, so no fixture changes.

## Out of scope

- `v1_files` object-storage access control. Uploaded photos and attachments are
  served via storage URLs rather than a DB queryset; whether one tenant can
  fetch another's file by URL is a storage-layer concern, worth its own review.
- APK endpoints, which serve the global app binary.
- Subdomain routing. This keys off the job's or request's user tenant, not the
  host.
