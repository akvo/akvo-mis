# Dashboard data model and permissions: design

## Problem

VIZ-001 moves dashboards from JSON files in the frontend bundle to
tenant-owned database rows, but nothing in the schema exists yet. Before any
endpoint or screen can be written there has to be somewhere to put a
dashboard, a way to derive its tenant, and a permission vocabulary the role
editor can group.

This is the foundation slice. It ships no view, no serializer and no URL —
only the tables, the constants and the permission factory that the rest of
the backend track sits on. It should merge on day one, because VIZ-005 is
blocked until it does.

## Decisions (from VIZ-001)

- Normalized widget rows, per-widget JSON config (D-1). A dashboard is a
  `Dashboard` row plus N `DashboardWidget` rows, not one JSON blob. Five
  fields are promoted out of the blob — `form`, `question`, `order`, `type`,
  `col_span` — because they need referential integrity or need to be
  queried. Everything type-specific stays in `config`.
- The publish snapshot is a JSONField, not a version table (D-2).
  `Dashboard.published_config` gives the draft/publish split; a
  `DashboardPublishedVersion` table would be speculative, because no stored
  artifact is bound to a past version of a dashboard.
- `question` is a real FK even though `Questions` soft-deletes. `PROTECT`
  never actually fires on the normal delete path — a soft delete only sets
  `deleted_at`. The FK's job is to make "which dashboards reference this
  question?" a plain join, for the broken-widget annotation (VIZ-007) and the
  form-builder delete warning (VIZ-009).
- `root_form` is the family key and is immutable after create (D-3). It is
  enforced in the serializer, not the model, but it is recorded here because
  it is what `PROTECT` on `Dashboard.root_form` is protecting.

## Components

### 1. `Dashboard`

A `SoftDeletes` model, `db_table = "dashboard"`, with `TENANT_PATH = "tenant"`
and a direct `tenant_fk("dashboards")` — the MT-002 definition-root pattern,
same as `Forms`.

Fields: `tenant`, `root_form` (FK `Forms`, `PROTECT`), `name`, `slug`,
`description`, `status`, `published_config`, `published_at`,
`default_filters`, `created`, `updated`, `created_by`.

One constraint:

    UniqueConstraint(
        fields=["tenant", "slug"],
        condition=Q(deleted_at__isnull=True),
        name="unique_active_tenant_dashboard_slug",
    )

Scoped to live rows, so a soft-deleted dashboard does not hold its slug
hostage.

### 2. `DashboardWidget`

`db_table = "dashboard_widget"`, `TENANT_PATH = "dashboard__tenant"`,
`TenantManager` — the derived-path pattern for a row that has no tenant
column of its own.

Fields: `dashboard` (FK, `CASCADE`), `order`, `type`, `col_span` (default
24), `title`, `color`, `form` (FK `Forms`, `PROTECT`, nullable),
`question` (FK `Questions`, `PROTECT`, nullable), `config`.
`Meta.ordering = ["dashboard", "order"]`.

`form` and `question` are nullable because `section_title` has neither and a
count-only KPI has no question.

### 3. Constants

`DashboardStatus` (`draft = 1`, `published = 2`) and `WidgetTypes`
(`kpi = 1` … `section_title = 7`), both with the `FieldStr` map the codebase
uses everywhere else.

### 4. Permissions

In `api/v1/v1_profile/constants.py`, five access types continuing from the
existing `form_delete = 7`:

    dashboard_view = 8
    dashboard_create = 9
    dashboard_edit = 10
    dashboard_publish = 11
    dashboard_delete = 12

`2` stays a gap; the new values continue from `7` rather than filling it.
`FeatureTypes.dashboard_builder = 3` groups all five in `FieldGroup`, so the
role editor renders them as one block next to Form Builder.

`DashboardAccess(required_access)` lands in `utils/custom_permissions.py`, a
straight mirror of `FormBuilderAccess`.

### 5. Migration

Two new tables. No backfill, no column added to any existing table, nothing
in the codebase references them yet. `tenant` is nullable per the MT-002
`tenant_fk` convention, but every row created through the API stamps it from
`request.user.tenant`.

The two legacy JSON configs (EPS, RWS) are **not** migrated — they encode
compute modes this schema deliberately drops (D-5). Rollback is dropping both
tables.

`backend/db.dbml` is regenerated in the same commit.

## Testing

- Soft delete hides a dashboard from `objects` and keeps it in
  `objects_deleted`; its widgets remain, reachable through the manager.
- The slug constraint rejects a duplicate live slug within a tenant, permits
  the same slug in another tenant, and permits reusing the slug of a
  soft-deleted dashboard.
- `Dashboard.objects.for_user(user)` returns only the caller's tenant's rows;
  `DashboardWidget.objects.for_user(user)` resolves through
  `dashboard__tenant` and does the same.
- Deleting a `Dashboard` cascades its widgets; deleting a `Forms` row still
  referenced as a `root_form` raises `ProtectedError`.
- Soft-deleting a `Questions` row leaves the referencing widget intact —
  `PROTECT` does not fire, which is the behaviour VIZ-007 depends on.
- The role-editor feature payload includes `dashboard_builder` with its five
  access types.
- `makemigrations --check` is clean.

## Out of scope

- Any view, serializer, URL or validation. `root_form` immutability, the
  §4.5 rules and the family restriction are all enforced in VIZ-005.
- Publishing. `published_config` and `published_at` are columns here and
  nothing writes them until VIZ-007.
- Seeding. There are no default dashboards; a tenant starts with none.
