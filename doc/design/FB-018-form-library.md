# Feature Design Document

> **Purpose**: Use this template when planning new features that require data model changes, API design, or architectural decisions. Complete this document BEFORE implementation begins. Claude can read this document for context during implementation.

---

## Feature: FB-018 — Form Library (curated, cross-tenant form catalog)

**Task ID**: FB-018
**Author**: Iwan Firmawan (with Claude)
**Date**: 2026-11-05 (implementation aligned 2026-11-09)
**Status**: Implemented (v1; see §12 for deferred items)

---

## 1. Context & Problem Statement

```
Currently:
- Each workspace builds its own forms from scratch. Forms are strictly
  tenant-scoped (Forms.tenant FK; Forms.objects.for_user() filters on the
  caller's tenant). There is no way to reuse a standard questionnaire
  (e.g. JMP WASH, agriculture living-income) across workspaces.
- The portability + copy machinery already exists:
    * duplicate_form(form, user)        -> deep draft copy, re-tenanted to user
    * import_form_definition(mode=create_copy) -> import forcing new IDs
    * FB-007 JSON + FB-014 XLSForm export + FB-016 XLSForm import
    * publish / unpublish / versions / activate lifecycle
- A platform-operator role above tenants already exists: User.is_platform_admin
  (tenant_id=None). It is deliberately NOT is_superuser. CONSEQUENCE
  (verified): a platform admin fails FormBuilderAccess (which passes only for a
  workspace super admin or a role holding form_builder access) and has NO form
  builder — the platform console today only does user/tenant management.
- Tenant-less (tenant=None) rows are, by default, editable by nobody: no super
  admin owns them and the platform admin has no builder. FB-018 resolves this
  with a narrow, `for_user`-bounded curator bypass (see D-1), so tenant-less
  rows become exactly the Library templates and only a curator can edit them.

Goal:
- Give Akvo a curated catalog ("Form Library") of reusable form templates that
  EVERY workspace can browse and import as a fresh draft.
- Templates are tenant-less `Forms` tagged `meta.template`, authored / edited
  with the EXISTING Form Builder by a curator (a tenant-less platform admin,
  reaching them via a `for_user`-bounded builder bypass) — no new editor, no
  console builder. (D-1)
- Curated, not free-for-all (v1): only a curator (platform admin) promotes
  forms into the library. Workspace users consume only. A user-submit →
  admin-approve flow is deferred to Phase 2. (D-2)
- Users reach it during onboarding AND later (a "Form Library" entry in the
  form builder): a paginated list page, filterable by category.
- Importing a library template DUPLICATES it into the user's tenant (new IDs),
  independent of the source (no back-reference). (D-3, D-6)
```

**Explicit non-goal / anti-duplication note.** This feature is a thin *scope +
browse* layer on top of machinery that already exists. It MUST NOT re-implement
form copying, importing, editing, versioning, or lifecycle — template editing is
just the ordinary Form Builder operating on tenant-less template rows. The only new
backend pieces are: a `meta.template` tag, a `FormCategory` table, an `import_count`,
a `for_user`-bounded curator bypass, and the browse/use/promote/category endpoints.
See §5 and the Reuse Map in §4.

---

## 2. Requirements

### User Acceptance Criteria
- [ ] A curator (tenant-less platform admin) authors templates in the **existing Form Builder** (reaching tenant-less template rows via the curator bypass), and promotes an existing workspace form into the library via one action.
- [ ] Editing a template uses the normal Form Builder edit/publish/version flow — no separate template editor.
- [ ] A user **with Form Builder access** (`form_view`) can open a **Form Library** page listing all **published** templates, paginated, filterable by category. Users without form-builder access do not see the library at all.
- [ ] Clicking **Use this form** (requires `form_create`) creates a **new draft in the user's own tenant** with fresh IDs; the source template is unchanged and unreferenced.
- [ ] The library is reachable both during onboarding and from the form builder.
- [ ] Workspace users (including instance super admins) cannot add, edit, or delete templates — they only browse and use within their own tenant.

### Technical Acceptance Criteria
- [ ] Templates are tenant-less `Forms` rows tagged `meta.template=true`; "available" = `status=published`.
- [ ] `Forms.objects.for_user()` semantics are **unchanged**; tenant-less templates stay out of workspace lists by normal tenant scoping (and the main form list also excludes `meta.template`). One deliberate cross-tenant read (the `/library` browse query, `meta__template=True`) serves published templates to everyone.
- [ ] "Use this form" reuses `duplicate_form()` — no new copy logic; template editing reuses the existing `FormBuilderViewSet`.
- [ ] **Access is gated on Form Builder feature grants** (`FeatureTypes.form_builder`): browse/preview require `FormBuilderAccess(form_view)`, use requires `form_create`, and template editing requires `form_edit` (a tenant-less curator passes via the bypass). Not merely `IsAuthenticated`.
- [ ] Promote + category-write actions are additionally gated on curator (`is_platform_admin`, tenant-less).
- [ ] No mobile sync or SQLite changes.

---

## 3. Data Model Changes

### New Models

**`FormCategory`** — a managed lookup table so sectors/domains are rows with stable
IDs, not a hardcoded enum (Q4). Platform admins add/rename categories without a code
change or migration; forms reference them by ID.

```python
# api/v1/v1_forms/models.py
class FormCategory(SoftDeletes):
    name = models.CharField(max_length=100, unique=True)   # "WASH", "Agriculture"
    slug = models.SlugField(max_length=100, unique=True)   # "wash", stable key for URLs
    created = models.DateTimeField(auto_now_add=True, null=True)
    # No tenant: categories are platform-wide, like library forms.
```

### Modified Models

| Model | Change | Reason |
|-------|--------|--------|
| `Forms` | Add `categories = ManyToManyField(FormCategory, blank=True, related_name="forms")` | Browse/filter dimension as proper related rows (Q4); a form can carry several categories. |
| `Forms` | Add `import_count = PositiveIntegerField(default=0)` | Lightweight curation metric (Q3); incremented on each `use`. |
| `Forms` | Add `meta = JSONField(default=None, null=True)` | Extensible bag that both **flags a catalog template** (`meta.template = true`) and carries provenance: `source` (Path 1 source workspace) and `copied_from` (template a workspace copy came from — provenance only, no propagation). Future additions need no migration. |

```python
# api/v1/v1_forms/models.py (Forms) — no Tenant change
categories = models.ManyToManyField("FormCategory", blank=True, related_name="forms")
import_count = models.PositiveIntegerField(default=0)
meta = models.JSONField(default=None, null=True)
```

> **What a template IS.** A template is an **ordinary form with no owning
> tenant** (`tenant = NULL`) tagged `meta.template = true`. Curators are
> platform admins (no tenant), so a form they author is stamped tenant-less by
> the existing `TenantStampedSerializerMixin` automatically. Isolation is free:
> `for_user()` filters a workspace user to their own tenant, so tenant-null
> templates never appear for them — `for_user()` is untouched.
>
> **What stays real schema vs `meta`.** `status`, the `categories` M2M and
> `import_count` (atomic `F()+1`) are columns because the browse query
> filters/joins/orders on them. Template-ness lives in `meta.template` — one
> bit, no new column. The browse query is
> `Forms.objects.filter(meta__template=True, status=published, parent__isnull=True)`.
>
> `# ponytail:` template-ness in the `meta` JSON means no DB index on it;
> promote it to a real column only if the catalog ever needs heavy filtering.
> At dozens–hundreds of templates a JSON lookup is a non-issue.

### Migration Strategy

```python
# - Additive migration: FormCategory table + M2M join table + Forms.import_count
#   + Forms.meta. No changes to existing columns, no Tenant change.
# - Existing rows: import_count=0, meta=None, no categories. meta.template is
#   absent on every existing form, so none is mistaken for a template. No
#   backfill, no data loss.
# - Rollback = drop FormCategory, the join table, and the added columns.
# - One-time provisioning (seeder): seed starter categories WASH + Agriculture
#   (named in the planning call). No dedicated tenant to create. The curator
#   (platform admin) adds more categories and authors templates at runtime.
```

### Form family behaviour (parent → children)

A Monitoring form is not standalone — `Forms.parent` ties it to its Registration
and it pre-fills from the parent's submissions. So the library's unit is the whole
**family**, handled without changing shared code:

- **`duplicate_form` is left unchanged** (it is shared with the existing single-form
  "duplicate" action). The library **use** action orchestrates the family copy:
  1. `duplicate_form(registration)` → new registration in the user's tenant
     (its `parent_id` is already `None`).
  2. for each published child in `registration.children`: `duplicate_form(child)`,
     then re-point `clone.parent_id = new_registration.id` (the one step
     `duplicate_form` can't do — it copies `parent_id` verbatim).
  3. stamp the new registration's `meta.copied_from = {form_id, name, at}`
     (provenance only; no link back to the template at runtime).
- **Family discovery = the `parent`/`children` FK**, not `meta`. `meta` only carries
  provenance, so child ids are never duplicated into it where they could drift.
- **Browse lists registration family-roots only** (`parent__isnull=True`). Monitoring
  forms never appear as their own catalogue entry; they are cloned silently with the
  parent on "Use". This removes the invalid "monitoring template with no parent" case.

---

## 4. API Contract

All routes live on the existing `FormBuilderViewSet`
(`/api/v1/manage/forms/...`). New actions only.

### Endpoints

| Method | URL | Purpose | Auth |
|--------|-----|---------|------|
| GET | `/api/v1/manage/forms/library` | List published **registration** templates (family roots), paginated, `?category={id}`, `?search=` | `FormBuilderAccess(form_view)` |
| GET | `/api/v1/manage/forms/library/{id}/preview` | Read-only preview of a template **family** (registration + its monitoring forms) before use | `FormBuilderAccess(form_view)` |
| POST | `/api/v1/manage/forms/library/{id}/use` | Clone the template **family** into the caller's tenant as new drafts; `import_count += 1` | `FormBuilderAccess(form_create)` |
| GET | `/api/v1/manage/library/source-forms?tenant={id}&search=` | **Curator-only** source picker (Path 1): list a chosen workspace's published registration families to promote. Bypasses `for_user` by design; excludes existing templates | `IsCurator` |
| POST | `/api/v1/manage/library/promote` | **Curator-only** (Path 1): snapshot a selected source family (from any workspace) into the Library (tenant-less, published, `meta.template=true`), record `meta.source`, set `categories` | `IsCurator` |
| GET/POST/PATCH/DELETE | `/api/v1/manage/form-categories[/{id}]` | Manage categories (list for the browse filter; writes curator-only) | list `FormBuilderAccess(form_view)`; writes `IsCurator` |

> **Template authoring/editing has no new endpoints.** Templates are ordinary
> tenant-less forms, so curators create / edit / publish / delete them with the
> **existing `FormBuilderViewSet`** (D-4). Two mechanisms make that work:
> (1) `FormBuilderAccess` grants a tenant-less platform admin builder access —
> bounded by `for_user`, which scopes a tenant-less caller to tenant-null rows,
> i.e. templates only; (2) `create` stamps `meta.template=true` on a
> registration root authored by such a curator (Path 2 "from scratch"). Only
> *browse*, *preview*, *use*, *promote* and *category* management are new endpoints.

> **Why promote is NOT plain `FormBuilderViewSet` CRUD.** That viewset's
> `get_object()`/`list` are `for_user`-scoped, so a curator only sees tenant-null
> templates through them. Path 1 (select from *any* workspace) must read
> cross-tenant, so `source-forms` and `promote` are curator-only actions that
> deliberately bypass `for_user`, gated by `IsCurator` (platform admin) — never
> exposed to workspace users.

> **Access requires Form Builder grants, not just a login.** The *browse / preview*
> endpoints require `FormBuilderAccess(form_view)` and *use* requires `form_create`
> (`FeatureTypes.form_builder`, i.e. `is_superuser` **or** a role holding that grant —
> see `v1_profile/constants.py`). A user without form-builder access never sees the
> library. `IsCurator` (a tenant-less `is_platform_admin`) gates the library writes
> (promote, category writes) and, via the `FormBuilderAccess` bypass, template
> authoring/editing. Deleting a category only unlinks it from forms (M2M) — never
> deletes a form.

### Reuse Map (the point of this feature)

| New action | Delegates to (existing) | Location |
|---|---|---|
| `library` list | `Forms.objects.filter(meta__template=True, status=published, parent__isnull=True)` — NOT `for_user()` | services/form_library.py |
| `library/{id}/preview` | `_to_editor_format(FormDetailSerializer(...))` over the registration **and its `children`** | views.py (`duplicate` / `version_detail` pattern) |
| `library/{id}/use` | **family clone**: `duplicate_form` per form + re-point child `parent_id`, stamp `meta.copied_from`, then `F("import_count") + 1` | functions.py:471 + §3 "Form family" |
| `library/promote` | family deep-copy of the chosen source via `duplicate_form`, leave tenant-less, set `status=published` + `meta.template` + `meta.source` + `categories` | services/form_library.py |
| template edit / publish / delete | **existing** `FormBuilderViewSet` CRUD (curator passes via the `FormBuilderAccess` bypass; `for_user` scopes them to tenant-null templates) | views.py |

### Request/Response Examples

```json
// GET /api/v1/manage/forms/library?category=4&page=1  (registration roots only)
// Response 200
{
  "current": 1, "total": 12, "total_page": 2,
  "data": [
    {
      "id": 901, "name": "JMP Core WASH Household", "version": 3,
      "import_count": 42, "monitoring_count": 1,
      "categories": [ { "id": 4, "name": "WASH", "slug": "wash" } ]
    }
  ]
}

// POST /api/v1/manage/forms/library/901/use
// Response 201  (the whole family, now owned by the caller's tenant)
{
  "registration": { "id": 1457, "name": "JMP Core WASH Household (Copy)", "status": "draft" },
  "monitoring": [ { "id": 1458, "name": "JMP WASH — Routine Monitoring (Copy)", "status": "draft" } ]
}
```

### UI & per-type actions (as built)

**Console (curator)** — `/admin/form-library`, a tab on the platform console
(`AdminLayout`, gated on `is_platform_admin`). A table of the published **registration**
templates with monitoring forms as **nested, indented sub-rows** (antd
`childrenColumnName`, expanded by default): columns Template, Categories, Status, *Used*,
*Monitoring forms*, Actions. Each registration row shows its **description** and, for a
promoted template, a provenance line *"Promoted from {workspace} · {date}"* from
`meta.source`. Features:
- **Search** + **multi-category filter** (any-of; `?category=1,2`).
- **Preview** per form — registration *and* each monitoring sub-row have their own
  Preview (single-form, no tab bar; see §Preview below).
- **Promote from workspace** (Path 1) — a dedicated **page** (`/admin/form-library/promote`),
  not a modal: pick a workspace → pick one of its published registration families
  (curator-only `source-forms`) → the chosen family **previews live** in the page body as
  the dropdown changes → assign categories → promote. The family is **snapshotted** into
  the Library (tenant-less, published, tagged `meta.template`; source untouched), source
  recorded in `meta.source`:
  ```json
  "meta": { "template": true, "source": { "tenant_id": 12, "tenant_name": "Bantul", "form_id": 884, "promoted_at": "2026-11-06" } }
  ```
  (`source` is descriptive provenance — not shown to consumers, never joined/filtered.)
- **Manage categories**: a modal to add/delete categories (the browse filter).
- **Delete** (*Remove from library*) per registration — soft-deletes the template;
  existing copies are unaffected.

> **Deferred (v1 scope, chosen with the team).** Per-row *Edit in Form Builder*,
> *Publish/Unpublish*, *+ Add monitoring form*, and **Path 2 "from scratch"** authoring
> are not surfaced on the console yet. The **backend supports them** — `create` stamps
> `meta.template=true` on a curator-authored registration, and the `FormBuilderAccess`
> curator bypass (D-4) lets a tenant-less curator wield the builder on tenant-null
> template rows — but wiring the builder from the `/admin` host to the workspace-host
> `/control-center/form-builder` is a follow-up. For v1, **Promote is the template
> creation path.**

**Preview (shared).** `FormLibraryPreview` renders a read-only, **paper-like** outline:
section header per question group, each question a label beside a faux underline/box
input whose shape hints at the answer type (radio/checkbox placeholders for option
types, taller box for long text, distinct boxes for geo/photo/attachment/signature). It
has two modes: **family** (`templateId` → registration + monitoring tabs, used by the
consumer) and **single form** (`formId` → one form, no tabs, used by the console per-row
Preview). The single-form read uses the ordinary `/manage/forms/{id}` detail — a template
form is tenant-less, so the tenant-less curator's `for_user` matches it, no new endpoint.

**Workspace (consumer)** — `/control-center/form-builder/library`, reached from a
**Form Library** button on the Form Builder list (and the onboarding tour, §11). A
responsive **card grid** (1 / 2 / 3 / 4 columns by breakpoint), **multi-category filter**
and search. Each card shows categories, *Used* count and monitoring-form count with
**Preview** and **Use this form** (gated on `form_create`; others see *View only*).
Preview opens the paper-like family modal; *Use* is also available from inside it. Draft
templates never appear here.

> **"Use this form" redirects to the Form Builder list** (`/control-center/form-builder`),
> not the new registration's edit page: the clone is a whole **family** (registration +
> monitoring forms), each published separately, so the list is where the user works
> through them one by one — landing on just the registration's editor hid the children
> and implied publishing the parent published the family.

### Implementation note — NULL-safe template exclusion

Every place that must keep templates out of a list filters with
`NOT_A_TEMPLATE = Q(meta__template__isnull=True) | Q(meta__template=False)`
(main form list, promote `source-forms`, promote source lookup), **not**
`.exclude(meta__template=True)`. A plain `exclude` drops rows whose `meta` is a
non-null JSON object lacking the key — e.g. a form cloned from a template
(`meta.copied_from`) — because SQL evaluates `NOT(NULL = true)` as NULL. The positive
filter keeps every non-template form (null meta, missing key, or `false`).

Promote also sets `tenant = None` **explicitly** on each copied form: `duplicate_form`
tenants a copy to `user.tenant or source.tenant`, and the curator is tenant-less, so
without the reset the template would inherit the *source workspace's* tenant and be
unreachable by any curator (whose `for_user` is tenant-NULL).

**Source-family preview reuses `source-forms`.** The promote page previews a candidate
via `GET /manage/library/source-forms?preview=<id>` — the same `IsCurator`-gated,
deliberately cross-tenant endpoint, parameterised to return one family's editor-format
definition. No new route: `/manage/forms/{id}` is `for_user` scoped (FB-015) and 404s
for a tenant-less curator reading a *workspace* form, so reusing the curator endpoint is
the one sanctioned cross-tenant read rather than weakening that isolation. (A *template*
form, being tenant-less, is still read via the plain detail endpoint — that's the
console's single-form Preview above.)

**`LibraryFormSerializer`** carries `status`, the `monitoring` children (id/name/type/
status, for the console sub-rows), and `source` (`meta.source`, or null) so the console
can show provenance. `library_list` accepts a comma-separated `category` (match any).

---

## 5. Decision Log

### D-1: Where do library templates live (cross-tenant scope)?

**Options Considered**:
1. New `LibraryForm` model duplicating the form schema.
2. Weaken `Forms.objects.for_user()` to also return `tenant IS NULL` rows.
3. A **dedicated internal "Library" tenant** (`Tenant.is_form_library=True`) that owns templates as ordinary forms; its super admin edits them.
4. **Tenant-less templates tagged `meta.template`**, with a narrow curator bypass so a tenant-less platform admin can author/edit them via the existing builder; browse is one explicit cross-tenant read; `for_user()` untouched.

**Decision**: Option 4.

**Rationale**: Option 1 forks the whole question/group/option tree and every
serializer. Option 2 edits the exact boundary FB-015 just hardened — any slip
re-leaks *all* forms across tenants. Option 3 works, but a "Library tenant" is a
singleton-disguised-as-data: a mystery row every new developer must learn, plus a
provisioning step and a flag on `Tenant`. Its whole job was to give templates an
owner that could edit them — but **curators are platform admins, not per-workspace
super admins**, so there is no per-tenant admin we actually want to empower. Once
the curator is a platform admin, the owning tenant is dead weight.

Option 4 drops it: a template is a tenant-less form tagged `meta.template`.
Isolation is unchanged — `for_user()` scopes a workspace user to their tenant, so
tenant-null templates never appear for them. Editing is solved by the same
`for_user` gate working *for* the curator: a tenant-less platform admin's
`for_user` returns exactly the tenant-null rows (templates), and a narrow
`FormBuilderAccess` bypass lets them wield the existing builder on those rows only
— never any workspace's forms. This is the "`tenant=None` editable by nobody"
dead-end resolved by a scoped permission, which is where the problem always lived.

**Impact**: `Forms.categories`/`import_count`/`meta` only (no `Tenant` change, no
dedicated tenant to provision); a `for_user`-bounded curator bypass in
`FormBuilderAccess`; `create` stamps `meta.template` for curator-authored roots;
no change to tenant isolation or to `duplicate_form`.

### D-2: Who curates the library?

**Options Considered**:
1. Any instance admin (`is_superuser`) — Kobo's free-for-all model.
2. Only **platform admins** (`is_platform_admin`, tenant-less), i.e. the MIS operators above all workspaces.

**Decision**: Option 2 (matches the meeting: "MIS admins, not instance admins").

**Rationale**: `is_superuser` means "owns this workspace", so option 1 lets every
tenant owner write to the shared catalog — the quality-control problem joy flagged.
Platform admins already exist as the above-tenant operator role and are the natural
curators. `IsCurator` is simply a tenant-less `is_platform_admin`; a workspace admin
(who has a tenant and is not a platform admin) can neither promote, manage categories,
nor author/edit templates.

### D-3: Import semantics — copy vs link.

**Decision**: Copy. `library/{id}/use` calls `duplicate_form`, producing a new
draft with fresh IDs re-tenanted to the caller. The shared original is never
mutated and the new form has no runtime dependency on it. (Directly reuses the
behaviour Deden described, 26:09–27:09 of the planning call.)

### D-4: Where templates are authored and edited.

**Decision**: With the **existing Form Builder**, by a curator — no new editor and no
console form-builder. Templates are tenant-less forms tagged `meta.template`; a
curator (tenant-less platform admin) reaches exactly those rows via `for_user` and
wields the builder through the `FormBuilderAccess` curator bypass. A new
management/browse page lists templates and routes "Edit in Form Builder"; authoring,
publishing, versioning and family (parent/child) handling all reuse the current
builder unchanged.

### D-5: Sector as a managed category table, not a hardcoded enum.

**Options Considered**:
1. `FormSectors` constant enum + a `sector` CharField on `Forms`.
2. A `FormCategory` lookup table + M2M; forms reference categories by stable ID.

**Decision**: Option 2 (per product — Q4).

**Rationale**: An enum means every new sector is a code change + deploy, and the
stored value is a loose string ("WASH" vs "wash") prone to filter drift. A category
table gives stable IDs, lets platform admins add/rename categories at runtime,
and naturally supports a form belonging to several sectors. It also matches
Kobo's category-based library browsing.

**Impact**: one small new model + a join table; browse filter keys on `category` id.

### D-6: Promote keeps the source form.

**Decision**: Promoting a form to the library **snapshots** it (deep copy via
`duplicate_form`); the originating workspace form stays intact and independent
(per product — Q1). Later edits to either side do not affect the other.

### D-7: Two creation paths; cross-tenant promote is curator-only.

**Decision**: An MIS admin creates a template two ways — **(1) Select from an existing
workspace** (promote a family from *any* workspace), or **(2) From scratch** in the
existing Form Builder (which stamps `meta.template` on a curator-authored root).

**Rationale**: Path 1 is the high-value case (reuse a proven real form) and resolves the
earlier "promote from any workspace?" question: it is allowed **because the curator is
the MIS / platform admin above tenants**, not a per-workspace admin — so a deliberate,
audited cross-tenant read does not violate isolation. The source workspace is stored in
`meta.source` so curators can trace where a template came from. Path 2 covers net-new
templates and reuses the builder unchanged.

**Impact**: a curator-only `source-forms` list + `promote` action that bypass `for_user`
(gated by `IsCurator`); one `meta` key. Workspace users get neither endpoint.

---

## 6. Type/Constant Mappings

No hardcoded sector enum (D-5). Categories are **data**, not constants: each is a
`FormCategory` row with a stable `id` and `slug`. The frontend filters by `category` id
and displays `name`.

| Frontend/Editor | Backend | DB |
|-----------------|---------|----|
| category chip `"WASH"` | `FormCategory(name="WASH", slug="wash")` | row `id=4` |
| filter `?category=4` | `Forms.categories` M2M → `FormCategory(id=4)` | join table row |

> Starter categories **WASH** and **Agriculture** (the sectors named in the planning
> call) ship as **seed data**, not code, so the catalog has filters on day one;
> admins extend the list at runtime. Ordinary (non-library) forms simply have no
> categories — unaffected.

---

## 7. Compatibility & Migration

### Backward Compatibility
- [x] Existing API consumers unaffected (additive columns, new actions only).
- [x] Existing data preserved (`import_count=0`, `meta=None`, no categories; no existing form carries `meta.template`).
- [x] `for_user()` and all tenant-scoped lists behave identically — templates are tenant-less, so they already fall outside any workspace tenant's `for_user()` result; the main form list also excludes `meta.template` so a tenant-less operator never sees them mixed with workspace forms.
- [x] CLI tools / seeders unaffected.

### Mobile App Impact
- [x] Sync endpoints affected: none.
- [x] SQLite schema changes: no.
- [x] Version detection: n/a (web-only feature).

### Seeder/CLI Compatibility
- [x] Existing seeders work unchanged.
- [ ] Optional later: a `form_library_seeder` to ship standard templates (JMP, agriculture). Not required for v1.

---

## 8. Security Considerations

- [x] **Permission model**: browse/preview = `FormBuilderAccess(form_view)`, use = `FormBuilderAccess(form_create)`, template edit = `form_edit` — i.e. only users with Form Builder feature grants (`is_superuser` or the role grant), never merely authenticated. Author/promote/category-write add `IsCurator` (tenant-less `is_platform_admin`). Never a foreign tenant's `is_superuser`.
- [x] **Tenant isolation preserved**: library reads are one explicit query scoped to `meta__template=True`; `for_user()` is unchanged, so no regression of FB-015. The curator builder bypass is bounded by `for_user` (a tenant-less admin only ever reaches tenant-null template rows).
- [x] **Copy-on-use**: the family clone (`duplicate_form`) stamps each new form with the *caller's* tenant (never trusts a tenant from the payload), so a user can only create forms in their own workspace.
- [x] **No cross-tenant write by workspace users**: a workspace user (who has a tenant, is not a platform admin) can neither reach template rows via `for_user` nor pass `IsCurator`.
- [x] **Curator cross-tenant read is deliberate and narrow**: only the `source-forms` list and `promote` action bypass `for_user`, both gated by `IsCurator`. They are read-only on the source (snapshot copy; the source form is never modified) and are the *only* paths that cross tenants — the rest of the feature keeps `for_user` intact.
- [x] **Input validation**: `categories` validated as existing `FormCategory` ids; `use`/`preview` resolve the target via the library query (`meta__template=True, status=published`) so any non-template id 404s.

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | The library query returns only `meta__template=True, status=published, parent__isnull=True`; excludes workspace forms, drafts, and monitoring children. |
| Unit | `promote-to-library` deep-copies the family as tenant-less + `meta.template` (published), attaches `categories`; source family untouched. |
| Unit | Family clone: `use` creates the registration + each published child, re-points child `parent_id` to the new registration, all in the caller's tenant. |
| Integration | `GET /library` 200 for a normal tenant user; `?category=` + search work; pagination shape matches existing list; monitoring forms absent from the list. |
| Integration | `POST /library/{id}/use` → 201 with the family, each new form `tenant = caller.tenant`, new IDs, `status=draft`, `import_count` incremented; template untouched. |
| Integration (authz) | A workspace `is_superuser` (not a curator) → 403 on promote / category writes. |
| Integration (Path 1) | `source-forms` / `promote` → 403 for a workspace user, 201 for a curator; promote snapshots the chosen family as a tenant-less template, writes `meta.source`, and leaves the source form untouched. |
| Integration (Path 2) | A curator POST to `/manage/forms` yields a tenant-less `meta.template` registration; a workspace user's POST does not. |
| Integration (authz) | Unauthenticated → 401/403 on `/library`. |
| Integration (isolation) | A template never appears in `GET /manage/forms` (excluded by `meta.template`, and by tenant scoping for workspace users). |
| E2E | Browse → filter by category → Preview → Use → redirected to the new registration draft (with its monitoring form) in the form builder. |

Run: `./dc.sh exec backend python manage.py test api.v1.v1_forms.tests.tests_form_library --verbosity=2`

---

## 10. Resolved Questions

All four resolved with product; kept as the rationale record.

- [x] **Q1 — Publish-to-library: copy or move? → Copy (snapshot); source stays.** Promoting deep-copies the form into the library; the originating workspace keeps its form, intact and independent. Later edits to either side don't affect the other. (See D-3, D-6.)
- [x] **Q2 — Multilingual: carry all translations? → Carry as-is.** `use` copies every `label::*` / `translations` value unchanged; the user prunes unused languages in the editor. Free — `duplicate_form()` already copies `translations` verbatim.
- [x] **Q3 — Track "imported N times"? → Yes (cheap).** `Forms.import_count`, incremented atomically (`F("import_count") + 1`) in `use` — one UPDATE, negligible cost. Surfaces real usage for curation (e.g. "JMP WASH used 42×, Agriculture 1×").
- [x] **Q4 — Sector values? → A managed `FormCategory` table, not a fixed enum.** Categories are rows with stable IDs, managed by platform admins at runtime (no deploy to add a category); a form can carry several; browse filters by `category` id. Starter categories ship as seed data. (See D-5, §3.)

### Also resolved

- [x] **Starter category set → seed `WASH` and `Agriculture`.** The two sectors named in the planning call (JMP/WASH and agriculture/living-income). Shipped as seed data (§3); platform admins add more at runtime.
- [x] **Template version history for consumers → latest published snapshot only (v1).** The library exposes only the current published version of a template; full version history is not surfaced to consumers.

- [x] **Origin-tracking scope → provenance only, no propagation.** A copied form keeps a
  "where it came from" reference in `meta.copied_from` (template id + name + date); edits
  to a template never notify or update its copies — copies are fully independent (D-3/D-6).
  So `use` writes `meta.copied_from` and nothing else links the two.

---

## 11. Onboarding Tour Integration (reuses TOUR-001)

**Decision: do NOT build a new tour.** The Form Library is introduced through the
existing onboarding tour engine ([TOUR-001](TOUR-001-first-login-onboarding-tour.md):
`frontend/src/components/onboarding-tour/`), which already handles workspace-user
targeting, role/permission filtering, `localStorage` completion, and the sidebar
"Take a Tour" relauncher. No backend, no new tour component, no new persistence.

**Why this covers "tour for workspace user" automatically:**
- The tour is mounted workspace-host-only (`!onAdminHost()`) and suppressed in
  operator inspection mode — so it is already *workspace-user-facing* by construction.
- The Form Library belongs to the **`setup` goal (Path A)**, whose steps only render
  for users with form-create ability (`ability.can("read"/"create", "form-builder")`)
  — exactly the audience that would start from a template.

**What this feature added to the existing tour (as built, frontend only):**

The `setup` path's first step already spotlights the Form Builder
(`[data-tour="sidebar-form-builder"]`, gated on `read form-builder` — the same
audience as the library). Rather than inserting a **new** step targeting the Form
Library button (which lives on the form-builder *page*, not the always-present
sidebar, so a spotlight would miss it off-page), the step's **description was
enriched** (EN + FR in `lib/ui-text.js`, key `tourSetupStep1Desc`) to tell the user
they can *"skip the blank page and start from a ready-made template in the Form
Library."* No new step, no step-count change, no `tourConfig.js` change.

A `data-tour="form-library-entry"` anchor is present on the Form Builder list's
**Form Library** button for any future dedicated step.

**Explicit non-goals (held):** no change to `OnboardingTour.jsx` engine, no new
goal/path, no change to the `localStorage` completion key, no backend.

---

## 12. Implementation Status

Implemented on `feature/fb-018-form-library`. State vs. the original plan:

- [x] **Backend** — `Forms.categories`/`import_count`/`meta` (migration 0010);
  `services/form_library.py` (browse, family clone, promote); `IsCurator` =
  tenant-less `is_platform_admin`; `FormBuilderAccess` curator bypass; `create`
  stamps `meta.template`; NULL-safe `NOT_A_TEMPLATE` filter (§4); seeder (categories).
- [x] **Frontend consumer** — `/control-center/form-builder/library` (card grid,
  category filter, search, Preview modal, Use → Form Builder list).
- [x] **Frontend console** — `/admin/form-library`: template table with **nested
  monitoring sub-rows**, search + **multi-category filter**, **per-form Preview**
  (paper-like), **description + `meta.source` provenance** per template, **Promote from
  workspace** as a dedicated **page with live preview** (`/admin/form-library/promote`,
  via `source-forms?preview=<id>`), **Manage categories**, Delete.
- [x] **Access gate** — `FormBuilderAccess(form_view)` to browse, `form_create` to
  use, `IsCurator` for promote/category writes; the library entry and the tour step
  both gate on `ability.can("read", "form-builder")`.
- [x] **Onboarding tour** — enriched `setup` step-1 copy (§11), EN + FR.
- [x] **Lint + tests green** — backend `flake8` clean, `tests_form_library` (12 tests)
  green; frontend `eslint` clean per changed file.
- [ ] **Deferred to a follow-up** (agreed scope, §4): console per-row *Edit in Form
  Builder* / *Publish* / *+ Add monitoring form*, and **Path 2 "from scratch"**
  authoring from the console host (backend already supports it).

> **Divergences from the original prototype**, by decision: the console omits the
> per-row ⋯ builder menu and the `+ New template` from-scratch path (backend-ready,
> deferred); "Use" lands on the Form Builder list rather than the editor; the tour
> reuses the existing step instead of adding one. Prototype for reference:
> <https://claude.ai/artifact/8U4pQBQh6QGZFyVPa8jSGX>.

---

## 13. References

- Planning call (2026-11-05): "library of questionnaires" discussion (16:23–17:35, 24:39–27:30).
- Prior art — reuse, do not rebuild:
  - `duplicate_form()` / `duplicate` action: [functions.py](../../backend/api/v1/v1_forms/functions.py), [views.py](../../backend/api/v1/v1_forms/views.py)
  - `import_form_definition(mode="create_copy")`, `normalize_form_definition()`
  - Tenant scoping: [tenant_scoped_model.py](../../backend/utils/tenant_scoped_model.py), [tenant_model.py](../../backend/utils/tenant_model.py)
  - Platform-admin role: `User.is_platform_admin` ([v1_users/models.py](../../backend/api/v1/v1_users/models.py))
- Interactive prototype (the UI the implementation must match): <https://claude.ai/artifact/8U4pQBQh6QGZFyVPa8jSGX> (`#console` curator view, `#workspace` consumer view).
- Permission model: `FeatureAccessTypes` / `FeatureTypes.form_builder` + `FormBuilderAccess` ([v1_profile/constants.py](../../backend/api/v1/v1_profile/constants.py), [utils/custom_permissions.py](../../backend/utils/custom_permissions.py)).
- Related design docs:
  - [FB-007-form-import-export.md](FB-007-form-import-export.md) — JSON import/export
  - [FB-014-xlsform-export.md](FB-014-xlsform-export.md) / [FB-016-xlsform-import.md](FB-016-xlsform-import.md) — XLSForm round-trip (the portability mechanism)
  - [FB-015-form-import-tenant-isolation.md](FB-015-form-import-tenant-isolation.md) — why `for_user()` must stay a strict boundary
  - [TOUR-001-first-login-onboarding-tour.md](TOUR-001-first-login-onboarding-tour.md) — the tour engine this feature plugs into (§11)
- **Separate features (do not fold into this spec)**:
  - "Create with AI" in the form builder — reuse `v1_visualization/ai/ai_service.py` (OpenAI + heuristic fallback), not the standalone Claude skill.

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-11-06 | Approved |
| Tech Lead | | | |
| Product | | | |
