# Tenant write-path enforcement: design

## Problem

Read isolation stops a tenant from *seeing* another tenant's data, but every
write endpoint is still open. Today, outside the registration flow, no create
sets a `tenant` at all: the six direct-FK tables are created with
`tenant = NULL`. A tenant superadmin can therefore create rows that land
tenant-less (or, by crafting a payload, under another tenant's form or
hierarchy), and can `PUT` or `DELETE` another tenant's objects.

This iteration closes the write side. After it, isolation is complete, with
reads *and* writes observing tenant ownership, which is the milestone that
makes the free tier safe to promote.

## The three threats and their mechanisms

Write enforcement is not one change; it is three threats, each with its own
mechanism.

### (a) Stamping: new rows must be owned by the creator's tenant

The six direct-FK models (`Levels`, `Administration`, `Forms`,
`Organisation`, `Entity`, `AdministrationAttribute`, plus `SystemUser` via
add-user) get their `tenant` set to the creator's tenant at every create
site.

The mechanism is `TenantStampedSerializerMixin`. Its `create()` injects
`tenant = self.context["user"].tenant` into `validated_data` before calling
`super().create()`. Views already pass `context={"user": request.user}`
widely, so most create serializers need only mix it in. Serializers with a
bespoke `create()`, such as `AddEditOrganisationSerializer` and
`AddEditUserSerializer`, instead set `tenant` explicitly inside that method
from `self.context["user"].tenant`; the mixin is not forced onto them.

Derived models are not stamped. `FormData`, `Answers`, `QuestionGroup`,
`EntityData`, `Role` and the rest have no `tenant` column; their ownership
follows their parent. They are protected by threat (c), not by stamping.

### (b) Guarding updates and deletes of existing objects

A `PUT`, `PATCH` or `DELETE` addressed to an object by URL id must fail if
that object belongs to another tenant.

The mechanism is a scoped lookup. Write detail views route their object
lookup through `for_user`, exactly as read detail views were changed:
`get_object_or_404(Model.objects.for_user(request.user), pk=...)`. A foreign
target is simply not found, so the response is 404 and reveals nothing.

### (c) Input-FK validation: payloads referencing another tenant's object

A create or update whose payload references a tenant-owned object must be
rejected. That covers a `FormData` under tenant B's `form`, a child
`Administration` under B's `parent`, a user assigned B's `role`, or data
tagged with B's `organisation` or `entity`.

The mechanism is `TenantScopedPrimaryKeyRelatedField`. Extending the existing
`CustomPrimaryKeyRelatedField`, it overrides `get_queryset()` to return
`base_queryset.for_user(self.context["user"])`. Every serializer FK input
that references a tenant-owned model swaps to this field. An out-of-tenant pk
then fails validation with the field's existing `does_not_exist` message, a
400 produced for free. Fields that reference non-tenant models, such as a
question type enum, are left unchanged.

## Error semantics: a deliberate split

- A URL-path object of another tenant returns 404. Existence is not revealed,
  consistent with read detail endpoints.
- A payload FK reference to another tenant returns a 400 validation error
  ("Invalid pk … object does not exist"). It is payload validation, and the
  scoped field yields this naturally.

The two are not unified because they are genuinely different: one is "the
thing you addressed isn't yours" (indistinguishable from "doesn't exist"),
the other is "a value you submitted is invalid."

## Async write path

Bulk administration and entity upload run in Django-Q with no request. The
task signatures already carry the uploader:
`handle_administrations_bulk_upload(filename, user_id, upload_time)` and
`handle_entities_bulk_upload(filename, user_id, upload_time)`.

The handlers load that user and stamp every created `Administration` and
`EntityData` with `user.tenant`. No signature change is needed, only the
row construction inside the handler. This closes the single largest
data-entry path, spreadsheet onboarding. Without it, bulk-created rows would
stay tenant-less exactly where onboarding happens.

## Coverage

These are the write endpoints that touch tenant-owned rows, grouped by
concern. The implementation plan turns this into a per-endpoint checklist; a
reviewer signs off completeness, and a grep of every `POST`, `PUT`, `PATCH`
and `DELETE` handler is the exit check.

Stamp on create (a):

- `Forms` create (form builder), in `v1_forms`.
- `Administration` create (single plus the bulk-upload handler), in
  `v1_profile` and `v1_jobs`.
- `Organisation` create (`AddEditOrganisationSerializer`), in `v1_users`.
- `Entity` create, `AdministrationAttribute` create, `EntityData` create
  (single plus bulk handler), in `v1_profile` and `v1_jobs`.
- `SystemUser` create (`AddEditUserSerializer`, add-user), in `v1_users`.
  Registration already stamps; add-user does not yet.

Scope FK inputs (c):

- `FormData` submission serializers, on `form` and `administration`, in
  `v1_data` and `v1_mobile`.
- Add-user serializer, on `role` and `administration`. These already validate
  administration reachability for non-superusers; the scoped field makes it
  tenant-uniform and covers the superuser path too.
- Administration create/edit, on `parent`.
- Mobile assignment create, on `administration` and `forms`.
- Any data or approval serializer taking a `form`, `administration`,
  `organisation`, or `entity` id.

Guard update/delete (b):

- Every write detail view already listed in the read-isolation coverage
  whose verb set includes `PUT`, `PATCH` or `DELETE`: data, form (builder),
  user, organisation, administration, role, entity, attribute, mobile
  assignment. Route the lookup through `for_user`.

## Error handling

- Stamping is unconditional and derived from the authenticated user. There is
  no client-supplied `tenant` field on any write serializer; a submitted
  `tenant` key is ignored, never trusted.
- Scoped FK fields reject foreign references at validation time (400) before
  any write.
- Scoped detail lookups 404 foreign targets before any mutation.
- The async handlers must resolve `user.tenant` once and reuse it. A
  tenant-less uploader (transitional) stamps `NULL`, matching the read-side
  NULL = NULL behavior, with no special case.
- Transactions already wrapping bulk upload and multi-row creates are
  retained, so a validation failure mid-batch stamps nothing.

## Testing

For a two-tenant fixture (A and B):

- Stamping: A's superadmin creates a form, organisation, entity,
  administration or user; each new row has `tenant = A`, never `NULL` or `B`.
- Input-FK (c): A submits form data referencing B's `form` and gets 400; A
  adds a user with B's `role` or B's `administration` and gets 400; A creates
  a child administration under B's `parent` and gets 400.
- Guard (b): A `PUT`s or `DELETE`s B's form, user, organisation, or
  datapoint and gets 404, with B's object unchanged.
- Async: a bulk administration upload run as A's user produces A-owned
  units, and an entity upload does the same.
- No trust of client tenant: a create payload that includes
  `"tenant": <B.id>` is ignored and the row is stamped to A.
- Regression: full backend suite green. Tenant-less seed data and the
  tenant-less test admin stamp and scope on `NULL`, so existing fixtures need
  no migration.

## Out of scope

- Subdomain routing and per-tenant URLs.
- Level management (create, update, delete of tiers). That is net-new and
  gets its own iteration.
- Tenant management UI and a platform-admin role.
- Retroactive re-stamping of any rows left tenant-less by earlier iterations
  beyond the default-tenant backfill. Nothing new creates them after this.
