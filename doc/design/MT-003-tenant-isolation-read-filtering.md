# Tenant isolation: read filtering design

## Problem

After the tenant-scoping iteration, ownership is *recorded* but not
*enforced*. Every current list/detail endpoint follows the pattern

    if request.user.is_superuser:
        return <all rows>          # ← the leak
    else:
        return <rows scoped by administration path>

so a tenant superadmin, which post-registration is what every registrant
is, sees and can read every other tenant's data, forms, users, and master
data. This iteration makes reads observe tenant ownership, which is the slice
that must land before the free tier can be promoted to real customers.

Scope is read filtering only: list endpoints return just the requester's
tenant's rows, and detail-by-id endpoints 404 on another tenant's object.
Write-path enforcement, subdomain routing, tenant management UI, and level
CRUD are separate future iterations (see Out of scope).

## Decisions (from brainstorming)

- One shared mechanism, applied to every leaking endpoint in a single
  iteration. The mechanism is the hard part; each endpoint reuses it.
- `for_user` manager methods, called explicitly, rather than middleware plus
  thread-local auto-filtering. Thread-locals are global mutable state, break
  in the Django-Q worker where there is no request, and hide the filter from
  readers. Explicit manager calls are greppable, Django-idiomatic, and
  unit-testable per model. The accepted cost is that every query site is
  touched and a forgotten site leaks silently, which is addressed by
  per-endpoint cross-tenant tests rather than just a mechanism test.
- `is_superuser` becomes tenant-admin. There is no cross-tenant
  platform-admin role in this iteration. Every `is_superuser → all rows`
  branch becomes `is_superuser → all rows *of my tenant*`.
- Uniform filter `tenant = user.tenant`. A tenant-less user (transitional
  only, since the invariant is that every user has a tenant) matches
  tenant-less rows through NULL = NULL, which keeps the full test suite green
  without migrating its seed data.
- Detail endpoints return 404, not 403, on another tenant's object. Existence
  is not revealed. This comes for free: scoping the lookup queryset makes the
  object simply not found.
- Levels delivery moves to a per-tenant runtime fetch. Without it the
  frontend still shows every tenant's levels from the global `window.levels`
  bake, so isolation would not be observable in the control center.

## The mechanism

### `for_user(user)` manager methods

Each tenant-owned model gains a manager method returning a queryset already
filtered to the user's tenant. Views change

    Model.objects.filter(...)  →  Model.objects.for_user(request.user).filter(...)

The manager is the single place that knows each model's path to a tenant.

Direct-FK models use `filter(tenant=user.tenant)`: `Levels`,
`Administration`, `Forms`, `Organisation`, `Entity`,
`AdministrationAttribute`, `SystemUser`.

Derived models use the same filter through the join path:

| Model | Path |
|---|---|
| `FormData` | `form__tenant` |
| `Answers` | `data__form__tenant` |
| `QuestionGroup`, `Questions` | `form__tenant` |
| `QuestionOptions` | `question__question_group__form__tenant` |
| `Role` | `administration_level__tenant` |
| `RoleAccess`, `RoleFeatureAccess` | `role__administration_level__tenant` |
| `UserRole` | `user__tenant` |
| `UserForms` | `user__tenant` |
| `EntityData` | `entity__tenant` |
| `AdministrationAttributeValue` | `administration__tenant` |
| `DataBatch`, `DataBatchComments`, `DataApproval` | `form__tenant` (via batch) |
| `MobileAssignment` | `user__tenant` |
| `Jobs` | `user__tenant` |

Only models backing an endpoint that currently returns cross-tenant rows
need the method; the coverage list below is the authority on which.

Implementation shape (each on the model's existing default manager, so
`objects.for_user(...)` works; `SoftDeletes`/`Draft` managers get it too so
their soft-deleted and draft variants stay scoped):

    class TenantScopedQuerySet(models.QuerySet):
        def for_user(self, user):
            return self.filter(**{self.model.TENANT_PATH: user.tenant})

Each model declares `TENANT_PATH` (`"tenant"` for direct-FK models,
`"form__tenant"` and so on for derived). A model without the attribute must
not get the method, which makes the opt-in explicit and greppable.

### The semantic shift

Every `if request.user.is_superuser:` branch that returns an unfiltered
queryset is rewritten to return the `for_user`-scoped queryset (the whole
tenant). Role-scoped branches already filter by administration path, which
stays within a tenant because administration subtrees are tenant-owned; the
tenant filter is added there too as defense in depth and to keep every code
path uniform.

## Coverage list

These are the endpoints that currently return tenant-owned rows and must be
scoped, grouped by app. Each is either an `is_superuser`-unfiltered leak or
an otherwise-unscoped list.

v1_data: `FormDataAddListView` (list), `PendingFormDataView`,
`DraftFormDataListView`, `DraftFormDataDetailView`, `DataDetailDeleteView`
(detail read), `DataAnswerDetailDeleteView`, `PendingDataDetailDeleteView`,
`PublishDraftFormDataView`, and the `@api_view` at `views.py:580`.

v1_forms: `list_form`, `list_published_forms`, the web-form and
export views keyed on a form id (`views.py:313,347,378,419`),
`FormBuilderViewSet.get_queryset`.

v1_users: `list_users`, `UserEditDeleteView` (detail),
`list_organisations`, `OrganisationEditDeleteView` (detail),
`list_organisation_options`, `list_levels`, `list_administration`.

v1_profile: `AdministrationViewSet`, `AdministrationAttributeViewSet`,
`EntityViewSet`, `EntityDataViewSet`, `RoleViewSet`, `list_entity_data`.
`PublicAdministrationViewSet` is deleted rather than scoped; see
"Deleting the public administration endpoint" below.

v1_mobile: `MobileAssignmentViewSet`, `DraftFormDataViewSet`, and the
assignment/data `@api_view` reads.

v1_visualization: `GeolocationListView`, `DatapointDetailView`, and the
chart/map `@api_view` endpoints (`views.py:53,202,486`).

Public and unauthenticated endpoints are not scoped and must stay reachable:
`config.js`, `register`, `login`, `setup/status`, `forgot-password`,
`invitation/{id}`. Any endpoint whose data must remain public is called out
during implementation rather than scoped by reflex.

The implementation plan will convert this into a per-endpoint checklist; a
reviewer signs off completeness against it.

## Deleting the public administration endpoint

`PublicAdministrationViewSet` (`/api/v1/public/administrations`, `AllowAny`)
returns the administration cascade unscoped, meaning every tenant's units. It
looks like a public read, but investigation showed it has exactly one
consumer: the authenticated form-builder (`FormBuilderCreate.jsx` and
`FormBuilderEdit.jsx` via the `ARF_CASCASE_URLS` constant). Data-entry forms
already use a user-scoped cascade (the per-form `get_api` endpoint,
`v1_forms/serializers.py`, pointing at the authenticated `list_administration`).
No genuinely public page consumes it.

It was made `AllowAny` only because the form-builder pointed the
akvo-react-form cascade at a token-less URL. But the library does support
auth on the cascade: its fetch threads `headers: (q.api.headers) || {}` into
the `axios.get` call. So the endpoint is unnecessary.

Rather than scope a public endpoint, this iteration deletes it:

- The form-builder's `ARF_CASCASE_URLS` gains
  `headers: { Authorization: "Bearer <token>" }` and points `endpoint` at the
  authenticated `/api/v1/administration` (`list_administration`), the same
  cascade data-entry forms use, which this iteration already scopes with
  `for_user`. Because the constant now needs the live token, it becomes a
  value built at render time (from the store) rather than a module constant.
- `initial` (the cascade's starting administration id) is resolved to the
  tenant's own root id dynamically, not the hardcoded `1`. Otherwise the
  builder would start at another tenant's root.
- `PublicAdministrationViewSet` and its two routes are removed.

This closes the last cross-tenant read with a deletion, needs no host-based
resolution, and removes a public surface rather than securing one.

## Levels delivery

This mirrors the `forms` runtime-fetch migration already in the tree:

- `generate_config.py` stops emitting `var levels`.
- `GET /api/v1/levels` returns `Levels.objects.for_user(request.user)` with
  `no-cache`, so a tenant sees only its own tiers.
- Frontend `lib/store.js` initialises `levels: []`, populated by a bootstrap
  fetch; a `getLevels()` accessor returns `store.getRawState().levels || []`.
- The direct `window.levels` readers that bypass the store,
  `AdministrationChart.jsx` and `ApproversTree.jsx`, repoint to the store.
- `setupTests.js` seeds levels through `store.update`, not a window global.

`appConfig` and `roleFeatures` stay baked in `config.js`: they are
per-deployment and per-code-release, not per-tenant.

## Error handling

- List endpoints: an out-of-tenant row is simply absent from the
  queryset; no error, just an empty or reduced list.
- Detail-by-id endpoints: the lookup runs against the `for_user`-scoped
  queryset, so another tenant's object is not found and the endpoint returns
  404. Existence is not revealed, and no 403 path is added.
- The worker (Django-Q): background jobs run without a request and must
  pass the acting user (or their tenant) explicitly to any `for_user` call.
  They can never rely on ambient request state, which the manager approach
  deliberately does not provide.
- Transitional tenant-less users: match tenant-less rows by NULL = NULL, with
  no special-case branch.

## Testing

- Mechanism, per model: `for_user` on each scoped model returns exactly
  the rows reachable through its `TENANT_PATH`; a two-tenant fixture proves
  the join.
- Per endpoint: seed tenant A and tenant B with their own data; assert
  A's user sees only A's rows on every list endpoint, and receives 404 on a
  GET of B's object on every detail endpoint.
- Levels delivery: the frontend renders from an empty levels array and
  populates from the endpoint; `AdministrationChart` and `ApproversTree`
  read from the store; the endpoint returns only the caller's tenant's
  levels.
- Public administration deletion: `/api/v1/public/administrations` no
  longer resolves; the form-builder cascade loads administrations through the
  authenticated, tenant-scoped `list_administration` and shows only the
  caller's tenant's units, starting at that tenant's root.
- Regression: the full backend suite passes unchanged. Tenant-less seed
  data and the tenant-less test admin match by NULL, so no seeder or login
  fixture needs migrating.

## Out of scope

- Write-path enforcement: stamping new rows with the requester's tenant
  and rejecting cross-tenant writes. This iteration is reads only.
- Level management (CRUD). This is net-new functionality, since no
  create/update/delete endpoint exists today. It gets its own future
  iteration, with append-only and freeze rules.
- Subdomain routing and per-tenant URLs.
- Tenant management UI.
- A cross-tenant platform-admin role. Deliberately absent; it can be added
  later as an explicit flag rather than implied by `is_superuser`.
