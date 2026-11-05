# Feature Design Document

> **Purpose**: Use this template when planning new features that require data model changes, API design, or architectural decisions. Complete this document BEFORE implementation begins. Claude can read this document for context during implementation.

---

## Feature: FB-018 — Form Library (curated, cross-tenant form catalog)

**Task ID**: FB-018
**Author**: Iwan Firmawan (with Claude)
**Date**: 2026-11-05
**Status**: Draft

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
- Tenant-less (tenant=None) rows are editable by nobody: no super admin owns
  them and the platform admin has no builder. So tenant=None is a dead end for
  anything that must be EDITED, like a template.

Goal:
- Give Akvo a curated catalog ("Form Library") of reusable form templates that
  EVERY workspace can browse and import as a fresh draft.
- Templates live in ONE dedicated internal "Library" tenant and are authored /
  edited with the EXISTING Form Builder by that tenant's curator (a super admin
  of the Library tenant) — no new editor, no console builder. (D-1, D-7)
- Curated, not free-for-all (v1): only the curator / platform admin promotes
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
just the ordinary Form Builder operating inside the Library tenant. The only new
backend pieces are: a flag marking the Library tenant, a `FormCategory` table, an
`import_count`, and three read/use endpoints. See §5 and the Reuse Map in §4.

---

## 2. Requirements

### User Acceptance Criteria
- [ ] A curator (Library-tenant super admin / platform admin) authors templates in the **existing Form Builder** inside the Library tenant, and promotes an existing workspace form into the library via one action.
- [ ] Editing a template uses the normal Form Builder edit/publish/version flow — no separate template editor.
- [ ] Any authenticated workspace user can open a **Form Library** page listing all **published** templates, paginated, filterable by category.
- [ ] Clicking **Use this form** creates a **new draft in the user's own tenant** with fresh IDs; the source template is unchanged and unreferenced.
- [ ] The library is reachable both during onboarding and from the form builder.
- [ ] Workspace users (including instance super admins) cannot add, edit, or delete templates — they only browse and use.

### Technical Acceptance Criteria
- [ ] Templates are ordinary `Forms` rows owned by the single tenant flagged `Tenant.is_form_library=True`; "available" = `status=published`.
- [ ] `Forms.objects.for_user()` semantics are **unchanged**; the Library tenant's rows stay out of other tenants' lists by normal tenant scoping. One deliberate cross-tenant read (the `/library` browse query, `tenant__is_form_library=True`) serves published templates to everyone.
- [ ] "Use this form" reuses `duplicate_form()` — no new copy logic; template editing reuses the existing `FormBuilderViewSet`.
- [ ] Promote + category-management actions are gated on curator/platform-admin.
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
| `Tenant` | Add `is_form_library = BooleanField(default=False)` | Marks the single internal tenant that owns library templates. The library lives in a real tenant so templates are editable with the existing Form Builder (D-1, D-7). |
| `Forms` | Add `categories = ManyToManyField(FormCategory, blank=True, related_name="forms")` | Browse/filter dimension as proper related rows (Q4); a form can carry several categories. |
| `Forms` | Add `import_count = PositiveIntegerField(default=0)` | Lightweight curation metric (Q3); incremented on each `use`. |
| `Forms` | Add `meta = JSONField(default=None, null=True)` | Extensible bag for descriptive/provenance data (e.g. `promoted_from`, and `copied_from` once origin-tracking scope is confirmed) so future additions need no migration. Never holds filtered/joined fields. |

```python
# api/v1/v1_users/models.py (Tenant)
is_form_library = models.BooleanField(default=False)

# api/v1/v1_forms/models.py (Forms)
categories = models.ManyToManyField("FormCategory", blank=True, related_name="forms")
import_count = models.PositiveIntegerField(default=0)
meta = models.JSONField(default=None, null=True)
```

> **What stays real schema vs `meta`.** The handful of things the library query
> filters or joins on stay as columns: the Library-tenant flag
> (`Tenant.is_form_library`), `status`, the `categories` M2M, `import_count`
> (atomic `F()+1`). Everything descriptive/future goes in `meta` so it needs no
> migration. **No `is_library` flag on `Forms`, no `tenant=None`, no FK for
> provenance** — a template is just a **published form owned by the Library
> tenant**; the browse query is
> `Forms.objects.filter(tenant__is_form_library=True, status=published, parent__isnull=True)`.

### Migration Strategy

```python
# - Additive migration: FormCategory table + M2M join table + Forms.import_count
#   + Forms.meta + Tenant.is_form_library. No changes to existing columns.
# - Existing rows: import_count=0, meta=None, no categories; every existing
#   tenant is_form_library=False. No backfill, no data loss.
# - Rollback = drop FormCategory, the join table, and the added columns/flag.
# - One-time provisioning (data migration or seeder): create the internal
#   "Library" tenant with is_form_library=True and a curator super admin, then
#   seed starter categories WASH + Agriculture (named in the planning call). This is
#   data, not schema; the curator/platform admin adds more categories at runtime.
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
  3. record provenance in `meta`.
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
| GET | `/api/v1/manage/forms/library` | List published **registration** templates (family roots), paginated, `?category={id}`, `?search=` | `IsAuthenticated` |
| GET | `/api/v1/manage/forms/library/{id}/preview` | Read-only preview of a template **family** (registration + its monitoring forms) before use | `IsAuthenticated` |
| POST | `/api/v1/manage/forms/library/{id}/use` | Clone the template **family** into the caller's tenant as new drafts; `import_count += 1` | `IsAuthenticated` + `FormBuilderAccess(form_create)` |
| POST | `/api/v1/manage/forms/{id}/promote-to-library` | Snapshot an existing form **family** into the Library tenant (published) + set `categories` | curator / `IsCurator` |
| GET/POST/PATCH/DELETE | `/api/v1/manage/form-categories[/{id}]` | Manage categories (list open to all; writes curator-only) | list `IsAuthenticated`; writes `IsCurator` |

> **Template editing has no new endpoints.** Templates are ordinary forms owned by
> the Library tenant, so curators create / edit / publish / delete them with the
> **existing `FormBuilderViewSet`** while working in that tenant (D-1, D-4). Only
> *browse*, *preview*, *use*, *promote* and *category* management are new actions.

> `IsCurator` gates write access to the library: a super admin **of the Library
> tenant** (or a platform admin). The *browse / preview / use* endpoints stay open
> to any authenticated workspace user, since published templates are shared. The
> category list is open; category writes are curator-only, and deleting a category
> only unlinks it from forms (M2M) — it never deletes a form.

### Reuse Map (the point of this feature)

| New action | Delegates to (existing) | Location |
|---|---|---|
| `library` list | `Forms.objects.filter(tenant__is_form_library=True, status=published, parent__isnull=True)` — NOT `for_user()` | models.py |
| `library/{id}/preview` | `_to_editor_format(FormDetailSerializer(...))` over the registration **and its `children`** | views.py (`duplicate` / `version_detail` pattern) |
| `library/{id}/use` | **family clone**: `duplicate_form` per form + re-point child `parent_id`, then `F("import_count") + 1` | functions.py:471 + §3 "Form family" |
| `promote-to-library` | family deep-copy into the Library tenant via `duplicate_form`, set `status=published` + `categories` | functions.py:471 |
| template edit / publish / delete | **existing** `FormBuilderViewSet` CRUD, run in the Library tenant | views.py |

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

### UI & per-type actions

**Console (curator).** The library management page lists each family as a
**Registration** row with its **Monitoring** form(s) as indented sub-rows. Actions
sit in a single **⋯ menu** per row:
- Registration: *Edit in Form Builder*, *Preview*, *Publish/Unpublish*, *+ Add
  monitoring form* (creates a child under this registration), *Remove from library*.
- Monitoring: *Edit in Form Builder*, *Publish/Unpublish*, *Delete*.

A monitoring template is never standalone — it is always added from its
registration's *+ Add monitoring form*. Both types open the **same Form Builder**.

**Workspace (consumer).** One card per registration family-root (monitoring hidden),
each with **Preview** and **Use this form**. Preview opens a read-only modal showing
the registration and its monitoring form(s) before the user commits; *Use* is also
available from inside the preview. Draft templates never appear here.

---

## 5. Decision Log

### D-1: Where do library templates live (cross-tenant scope)?

**Options Considered**:
1. New `LibraryForm` model duplicating the form schema.
2. Weaken `Forms.objects.for_user()` to also return `tenant IS NULL` rows.
3. Tenant-less library forms (`tenant=None`) read via a separate manager.
4. A **dedicated internal "Library" tenant** (`Tenant.is_form_library=True`) that owns the templates as ordinary forms; browse is one explicit cross-tenant read; `for_user()` untouched.

**Decision**: Option 4.

**Rationale**: Option 1 forks the whole question/group/option tree and every
serializer. Option 2 edits the exact boundary FB-015 just hardened — any slip
re-leaks *all* forms across tenants. Option 3 looked clean until the editing
question: `tenant=None` forms are **editable by nobody** — no super admin owns them
and a platform admin has no Form Builder — so templates could never be maintained.
A real Library tenant fixes that: its super admin edits templates with the
**existing Form Builder**, versioning and lifecycle all reused, and `for_user()`
stays the single strict tenant gate (the Library tenant's rows simply belong to
another tenant). Browse is the one deliberate cross-tenant read.

**Impact**: `Tenant.is_form_library` flag + `Forms.categories`/`import_count`/`meta`;
one provisioning step (create the Library tenant + curator); no change to tenant
isolation or to `duplicate_form`.

### D-2: Who curates the library?

**Options Considered**:
1. Any instance admin (`is_superuser`) — Kobo's free-for-all model.
2. Only the **Library tenant's curator(s)** (its super admin, designated by a platform admin).

**Decision**: Option 2 (matches the meeting: "MIS admins, not instance admins").

**Rationale**: `is_superuser` means "owns this workspace", so option 1 lets every
tenant owner write to the shared catalog — the quality-control problem joy flagged.
Scoping curation to the Library tenant keeps it to a small, designated group while
reusing the ordinary Form Builder permissions inside that tenant. A workspace admin
has no access to the Library tenant, so cannot add or edit templates.

### D-3: Import semantics — copy vs link.

**Decision**: Copy. `library/{id}/use` calls `duplicate_form`, producing a new
draft with fresh IDs re-tenanted to the caller. The shared original is never
mutated and the new form has no runtime dependency on it. (Directly reuses the
behaviour Deden described, 26:09–27:09 of the planning call.)

### D-4: Where templates are authored and edited.

**Decision**: Inside the **Library tenant, with the existing Form Builder** — no new
editor and no console form-builder. A new management/browse page lists templates and
routes "Edit in Form Builder" into that tenant; authoring, publishing, versioning and
family (parent/child) handling all reuse the current builder unchanged.

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

### D-6: Publish-to-library keeps the source form.

**Decision**: Promoting a form to the library **snapshots** it (deep copy via
`duplicate_form`); the originating workspace form stays intact and independent
(per product — Q1). Later edits to either side do not affect the other.

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
- [x] Existing data preserved (`import_count=0`, `meta=None`, no categories; every existing tenant `is_form_library=False`).
- [x] `for_user()` and all tenant-scoped lists behave identically — the Library tenant's forms belong to a different tenant, so they already fall outside any real tenant's `for_user()` result.
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

- [x] **Permission model**: browse/preview/use = any authenticated user; author/edit/promote = `IsCurator` (Library-tenant super admin / platform admin). Never a foreign tenant's `is_superuser`.
- [x] **Tenant isolation preserved**: library reads are one explicit query scoped to `tenant__is_form_library=True`; `for_user()` is unchanged, so no regression of FB-015.
- [x] **Copy-on-use**: the family clone (`duplicate_form`) stamps each new form with the *caller's* tenant (never trusts a tenant from the payload), so a user can only create forms in their own workspace.
- [x] **No cross-tenant write by workspace users**: promote/edit run only inside the Library tenant by its curator; workspace users have no endpoint that writes into the Library tenant.
- [x] **Input validation**: `categories` validated as existing `FormCategory` ids; `use`/`preview` resolve the target via the library query (`tenant__is_form_library=True, status=published`) so any non-template id 404s.

---

## 9. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | The library query returns only `tenant__is_form_library=True, status=published, parent__isnull=True`; excludes other tenants' forms, drafts, and monitoring children. |
| Unit | `promote-to-library` deep-copies the family into the Library tenant (published), attaches `categories`; source family untouched. |
| Unit | Family clone: `use` creates the registration + each published child, re-points child `parent_id` to the new registration, all in the caller's tenant. |
| Integration | `GET /library` 200 for a normal tenant user; `?category=` + search work; pagination shape matches existing list; monitoring forms absent from the list. |
| Integration | `POST /library/{id}/use` → 201 with the family, each new form `tenant = caller.tenant`, new IDs, `status=draft`, `import_count` incremented; template untouched. |
| Integration (authz) | A workspace `is_superuser` (not a Library-tenant curator) → 403 on promote / category writes. |
| Integration (authz) | Unauthenticated → 401 on `/library`. |
| Integration (isolation) | A Library-tenant template never appears in `GET /manage/forms` for any other tenant's user. |
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

**What this feature adds to the existing tour (frontend only):**

| Touchpoint | Change | Where |
|---|---|---|
| Tour step | Add **one step** to the `setup` path: *"Start from a template"* spotlighting the Form Library entry, before/after "Build a form". `permission: (ability) => ability.can("read", "form-builder")`. | `components/onboarding-tour/tourConfig.js` → `TOUR_PATHS[GOALS.SETUP]` |
| Anchor | Add `data-tour="form-library"` to the Form Library entry point (sidebar/form-builder button). | the Form Library UI element |
| i18n | Add EN + FR keys for the new step title/body/CTA (CTA route → the library page). | `lib/ui-text.js` |
| Step count | Automatic — `getTotalStepsForGoal()` already derives the count from the (permission-filtered) path length. | no change |

**Explicit non-goals:** no change to `OnboardingTour.jsx` engine, no new goal/path,
no change to the `localStorage` completion key, no backend. The standalone
**"Form Library" entry link** (joy's "like Take a Tour" link) is ordinary nav in the
form builder/onboarding area, independent of whether the tour step is shown.

---

## 12. References

- Planning call (2026-11-05): "library of questionnaires" discussion (16:23–17:35, 24:39–27:30).
- Prior art — reuse, do not rebuild:
  - `duplicate_form()` / `duplicate` action: [functions.py](../../backend/api/v1/v1_forms/functions.py), [views.py](../../backend/api/v1/v1_forms/views.py)
  - `import_form_definition(mode="create_copy")`, `normalize_form_definition()`
  - Tenant scoping: [tenant_scoped_model.py](../../backend/utils/tenant_scoped_model.py), [tenant_model.py](../../backend/utils/tenant_model.py)
  - Platform-admin role: `User.is_platform_admin` ([v1_users/models.py](../../backend/api/v1/v1_users/models.py))
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
| Developer | | | |
| Tech Lead | | | |
| Product | | | |
