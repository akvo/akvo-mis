# Tenant scoping: database foundation design

## Problem

After the free-tier registration iteration, tenants exist as rows and users
are linked to them, but every piece of business data (hierarchy, forms,
organisations, master data) is still global. Tenant #2's superadmin sees and
can modify tenant #1's data.

This iteration is the minimal database adjustment that makes tenant
ownership *recorded* correctly for everything a tenant can create. It is
deliberately not full isolation: query filtering, permission enforcement, and
subdomain routing are later slices. After this iteration, isolation becomes a
mechanical "add `.filter(tenant=…)`" exercise because every table has a
derivation path to a tenant.

## The scoping analysis

Almost every table already reaches a scoping root through existing FKs. Only
the definition roots, meaning tables with no FK path upward, need a direct
`tenant` FK. Everything else derives through joins:

| Direct `tenant` FK | Derivation for everything else |
|---|---|
| `Levels` | `Role` → level |
| `Administration` | `FormData`, `EntityData`, `AdministrationAttributeValue`, `UserRole` → administration |
| `Forms` | `QuestionGroup`, `Questions`, `QuestionOptions`, `QuestionAttribute`, `FormPublishedVersion`, `UserForms`, `DataBatch` → form |
| `Organisation` | `OrganisationAttribute` → organisation |
| `Entity` | `EntityData` → entity |
| `AdministrationAttribute` | values → attribute |
| `SystemUser` *(already done)* | `Jobs`, `MobileAssignment`, `Answers`, approvals → user |

`Administration` technically only needs the FK on its root (descendants
derive via `path`), but the FK is denormalized onto every row so the existing
path-filter queries stay cheap and future filtering is a plain column match.

`MobileApk` stays global, since it is the platform's APK registry rather than
tenant data. `ViewDataOptions` derives via its question/form references.

## Decisions (from brainstorming)

- Users and organisations are tenant-owned. Each tenant has their own
  collaborators; `Organisation` gets a direct FK.
- One tenant per user. The `SystemUser.tenant` FK stays a single FK;
  `email` stays globally unique. One email is one account is one tenant. A
  cross-tenant consultant uses a second email address. The alternative, a
  membership join table with tenant switching, changes the whole session and
  permission model and is out of scope.
- `Entity` and `AdministrationAttribute` are tenant-owned too. Both are
  tenant-created master data; a water-sector tenant and a health-sector
  tenant want different entity types and attributes.
- Per-tenant hierarchy from registration. With the FKs in place, the
  shared-hierarchy behavior from the registration iteration is retired:
  every registration creates the tenant's own level 0 and root unit.
- Nullable FKs with an in-migration backfill, rather than
  non-null-with-default or schema-per-tenant. Existing deployments migrate
  with zero downtime and zero behavior change.

## Components

### 1. Schema changes

Each of `Levels`, `Administration`, `Forms`, `Organisation`, `Entity`,
`AdministrationAttribute` gains:

    tenant = models.ForeignKey(
        "v1_users.Tenant", null=True, default=None,
        on_delete=models.PROTECT, related_name="<plural>",
    )

(String reference avoids new cross-app imports; `v1_profile` already imports
from `v1_users`, and `v1_forms` can use the lazy reference.)

Constraint changes in the same migrations:

- `Levels`: `UniqueConstraint(fields=["tenant", "level"])`. Today the
  `level` integer has no DB uniqueness at all, so this is a tightening
  rather than a relaxation.
- `Administration`: partial `UniqueConstraint` on `tenant` where
  `parent IS NULL`, giving one root per tenant.
- `Organisation.name`: `unique=True` is replaced by
  `UniqueConstraint(fields=["tenant", "name"])`, so two tenants may both have
  a "Ministry of Health".
- `Entity.name` and `AdministrationAttribute.name`: never unique; unchanged.

### 2. Backfill

One data migration in `v1_users` (where `Tenant` lives), ordered after all
schema migrations via `dependencies`:

1. `get_or_create` a tenant with subdomain `default`.
2. Stamp it onto every existing row of the six tables and onto every
   existing `SystemUser` with `tenant IS NULL`.

Idempotent (re-running changes nothing) and reversible (null the FKs, delete
the `default` tenant). Existing single-tenant deployments (mohhs, unicef-fsm)
become the `default` tenant with no behavior change.

### 3. The two behavior changes

Registration (`register` view): the get-or-create conditionals are dropped.
Every registration now creates, inside the existing transaction:

    Tenant(subdomain=…)
    SystemUser(is_superuser=True, tenant=…)
    Levels(level=0, name="", tenant=…)          — always, tenant's own
    Administration(parent=None, name=<subdomain>, tenant=…)  — always, tenant's own

This is *simpler* than the shared-hierarchy version, and the second
registration test inverts: two registrations now produce two disjoint
hierarchies.

Profile resolution (`UserSerializer.get_administration`): the superuser
root lookup becomes tenant-aware:

    Administration.objects.filter(parent__isnull=True, tenant=user.tenant)

with a fallback to the unscoped `parent__isnull=True` lookup when
`user.tenant` is NULL, so legacy superusers on existing deployments keep
resolving the (now `default`-tenant) root exactly as before.

### 4. Explicitly not in this iteration

- Query filtering anywhere else: data lists, form lists, user lists,
  master-data screens still show all rows regardless of tenant.
- Permission enforcement across tenants.
- Subdomain routing.
- Tenant management UI.

Tenants are correctly recorded after this iteration, not yet isolated.
Cross-tenant visibility remains an accepted, known state: the free tier must
not be promoted to real customers until the filtering slice lands.

## Error handling

- Registration keeps its atomic transaction; the per-tenant hierarchy rows
  are inside it, so a failed registration leaves no partial tenant.
- The new unique constraints turn silent convention violations into database
  errors: a duplicate level number within a tenant, a second root within a
  tenant, a duplicate organisation name within a tenant.
- `PROTECT` on every tenant FK: a tenant that owns any data cannot be
  deleted by accident.

## Testing

- Migrations: on a database with pre-existing data, the backfill stamps
  every row with the `default` tenant; re-running is a no-op.
- Registration: two registrations produce two disjoint hierarchies, each
  tenant with its own level 0 and its own root; profile resolution
  returns each superadmin their own root.
- Legacy: a superuser with `tenant IS NULL` still resolves a root
  administration through the fallback path.
- Constraints: the same `level` integer is allowed across tenants and
  rejected within one; a second root is rejected within a tenant, allowed
  across tenants; duplicate organisation names allowed across tenants,
  rejected within one.
- Regression: the full backend suite passes. Seeders and the 137
  `administration_seeder --test` call sites create tenant-less rows, which
  remain valid (`null=True`).
