# /manage/dashboards CRUD API: design

## Problem

VIZ-002 gives dashboards a place to live; nothing writes to it. The builder
needs a full CRUD surface, and — more importantly — it needs a server that
refuses to persist a dashboard that cannot render.

That second point is what makes this slice larger than a viewset. Under
file-based configs, a human reviewed every dashboard before it shipped. Under
tenant-authored ones nobody will, so every rule in VIZ-001 §4.5 has to be
enforced at save time. A dashboard that saves is a dashboard that renders.

## Decisions (from VIZ-001)

- Mirror `/manage/forms`. `DashboardBuilderViewSet(ModelViewSet)` follows
  `FormBuilderViewSet` (FB-002) — same namespace shape, same per-action
  permission factory, same `@transaction.atomic` on every write. A reviewer
  who knows the form builder knows this.
- **The widget array is replaced wholesale on `PUT`.** The builder's canvas
  treats add, remove and reorder as local edits until save, so the payload is
  the whole array: widgets carrying an `id` update in place, those without
  are created, omitted ones are deleted. Diffing on the client and sending
  patches would put the canvas's state model in two places.
- **One form family, enforced server-side, permanently (D-3).**
  `widget.form` must be `root_form` or a monitoring form whose `parent` is
  `root_form`. Cross-form dashboards are not allowed and this is not a
  deferral: `sum_by=parent_id` and `monitoring=latest` are defined relative to
  a known registration form, so a widget pointing outside the family produces
  numbers that look right and are not.
- **`root_form` is immutable after create.** Changing it would orphan every
  widget. A `PUT` that names a different `root_form` is a 400, not a
  cascading rewrite.
- `/sources` exists so the builder never guesses. Without it the frontend
  would re-derive §4.5 — the family rule, the four aggregatable question
  types, the option lists — and the two copies would drift.
- Tenant comes from `request.user.tenant`, never from the payload, and every
  form id in a payload is validated against it. A sequential `form_id` must
  not cross tenants (MT-004).

## Components

### 1. `DashboardBuilderViewSet`

Routed at `/api/v1/manage/dashboards`, gated per action by
`DashboardAccess`:

| Action | Method + URL | Permission |
|---|---|---|
| list | `GET /manage/dashboards` | `dashboard_view` |
| create | `POST /manage/dashboards` | `dashboard_create` |
| retrieve | `GET /manage/dashboards/{id}` | `dashboard_view` |
| update | `PUT /manage/dashboards/{id}` | `dashboard_edit` |
| destroy | `DELETE /manage/dashboards/{id}` | `dashboard_delete` |
| sources | `GET /manage/dashboards/{id}/sources` | `dashboard_view` |

`get_queryset` is `Dashboard.objects.for_user(self.request.user)` — no
action reaches a row outside the caller's tenant, so a foreign id is a 404.
`list` includes drafts; the published-read namespace is VIZ-007.

`create` accepts `name`, `description` and `root_form`, stamps `tenant` and
`created_by`, derives a slug from the name, and returns a draft. `destroy`
is a soft delete.

### 2. `validate_dashboard_payload()`

In `v1_visualization/dashboard_functions.py`, called before any DB mutation,
implementing every rule in VIZ-001 §4.5:

- `root_form.type == registration` and `root_form.parent is None`
- `root_form` unchanged on update
- `widget.form` is `root_form` or has `parent == root_form` — **the family
  rule**
- `widget.question.form == widget.form`
- `widget.question.type` is one of number, option, multiple_option, date
- `measure == current_state` only on a monitoring form
- `stack_by` requires `group_by` and `question`
- `1 <= col_span <= 24`
- `table.columns[].source` in `VALID_COLUMN_SOURCES`
- `slug` matches `^[a-z0-9]+(-[a-z0-9]+)*$`, unique per live row per tenant

Errors return 400 with the offending widget's index and field, so the
builder can highlight the widget rather than showing one global message.
Slug collision is a 409.

The question-type restriction is not arbitrary: `Answers` stores numerics in
`value`, choices in `options` and everything else in `name`, so only those
four types are aggregatable at all. `SUPPORTED_QUESTION_TYPES` in
`v1_visualization/constants.py` is the single source, imported rather than
restated.

### 3. Tenant enforcement on writes

`tenant` is stamped from `request.user.tenant` and any `tenant` key in the
payload is ignored. `root_form` and every `widget.form` and
`widget.question` resolve through `for_user`-scoped querysets, so a foreign
id fails validation before a row is written. This runs *before* the family
check — a foreign form is a 400 for being foreign, not for being outside the
family.

### 4. `GET /manage/dashboards/{id}/sources`

Returns the dashboard's family — `root_form` plus every monitoring form whose
`parent` is `root_form` — each with its questions already filtered to the
four aggregatable types and annotated with their option lists. Response shape
is VIZ-001 §6 verbatim.

This endpoint *is* the family boundary as the UI sees it. If a form is not in
`/sources`, the builder cannot offer it, and if the builder somehow does, the
family rule rejects it on save. Two barriers, same rule.

### 5. Writes are atomic

Every mutation runs in `@transaction.atomic`. A `PUT` that deletes four
widgets, updates two and creates one either does all of it or none — a
half-applied widget array is a dashboard that renders wrong.

## Data flow

    POST /manage/dashboards {name, root_form}
      → validate root_form is a registration form in my tenant
      → Dashboard(status=draft, tenant=me, slug=derived)

    PUT /manage/dashboards/{id} {name, description, default_filters, widgets[]}
      → validate payload in full (400 with widget index on failure)
      → atomic: update rows with id, create rows without, delete omitted
      → 200 with the reserialized dashboard

    GET /manage/dashboards/{id}/sources
      → root_form + monitoring children, aggregatable questions only

## Error handling

- Foreign dashboard id → 404. Foreign `root_form`, `widget.form` or
  `widget.question` → 400 at validation, before any write.
- A widget naming a form in the tenant but outside the family → 400 naming
  the family rule, with the widget index.
- `root_form` changed on update → 400: a dashboard's data source is fixed at
  creation.
- Slug collision within the tenant → 409 with a suggested alternative.
- Missing permission → 403, per action.
- Any validation failure leaves the stored dashboard byte-identical.

## Testing

- One test per §4.5 rule, each asserting 400 and the offending widget index.
- The family rule specifically: a widget on `root_form` passes; a widget on a
  monitoring child of `root_form` passes; a widget on a monitoring form whose
  parent is a *different* registration form is rejected; a widget on an
  unrelated registration form is rejected.
- `root_form` immutability on update.
- Wholesale replace: a `PUT` with one updated id, one new widget and one
  omitted id produces exactly those three effects and nothing else.
- Cross-tenant: a widget payload carrying tenant B's `form_id` is rejected
  for A; a `GET`, `PUT` or `DELETE` on B's dashboard id returns 404 for A.
- Permission: each action refused for a user lacking its access type.
- `/sources` returns only the family, and never a question of an unsupported
  type.
- Atomicity: a payload whose last widget fails validation leaves the stored
  widget rows unchanged.

## Out of scope

- Publish, unpublish, duplicate and the `/dashboards` read namespace — all
  VIZ-007. This slice's `status` is always draft.
- The broken-widget annotation. `question.deleted_at` is not consulted here;
  it is the read path's concern (VIZ-007).
- Rendering, and any expansion of `measure` into query parameters. The
  server stores `measure` as authored and never interprets it; VIZ-008 owns
  the expansion.
