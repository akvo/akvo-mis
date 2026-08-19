# Visualization endpoint hardening: design

## Problem

`CLEANUP-001` found that several `/api/v1/visualization/*` endpoints carry no
permission class at all, so DRF's default `AllowAny` applies, and they take a
sequential `form_id` straight from the URL. `/visualization/progress/1`,
`/2`, `/3` walks another tenant's forms; the anonymous `/dashboard/:slug`
route is what made that reachable without a login. The read isolation and
write enforcement iterations (MT-003, MT-004) covered `v1_data`, `v1_forms`,
`v1_users`, `v1_profile` and `v1_mobile`, but the visualization app kept its
open surface because the Fiji dashboard depended on it.

This slice closes that. It is **gated on nothing** — it does not need the
dashboard model, the CRUD API, or any frontend work — so it merges first,
independently of the rest of the milestone.

It is also the milestone's regression gate. VIZ-001 preserves the
latest-monitoring semantics rather than rewriting them (D-5), so the existing
`v1_visualization` suite must pass with nothing changed but the added auth.
If it does not, something was rewritten that should not have been.

## Decisions (from VIZ-001)

- Keep `/values` and `/escalation` and harden them (D-5). That query grammar
  is not Fiji-specific; it is the correct general aggregation vocabulary over
  `Answers`, and `values_functions.py` already implements the
  latest-monitoring subquery across count, number, option and stacked modes.
  Reimplementing it is the riskiest thing this milestone could do.
- Keep and harden `/visualization/progress`, but expose it to nobody (D-6).
  Its `components=` string grammar is not something a builder UI can
  reasonably author, and its formulas were shaped around EPS construction
  tracking. It keeps working, gains the same auth as everything else, and has
  no caller after VIZ-009.
- No anonymous surface anywhere (D-7). Both the endpoints here and the two
  dashboard namespaces added later require authentication. Public sharing, if
  it is ever wanted, is a deliberate feature with its own token model.
- A foreign id returns 404, not 403. Confirming that a form exists in another
  tenant is itself a leak.

## Components

### 1. Authentication on every view

`IsAuthenticated` on every view in `api/v1/v1_visualization/`:

- `views.py` — `monitoring_stats`, `formdata_stats`, `GeolocationListView`,
  `DatapointDetailView`, `visualization_values_formula`
- `dashboard_views.py` — `visualization_values`, `visualization_escalation`,
  `visualization_progress`

After this, `grep -rn "AllowAny" backend/api/v1/v1_visualization/` returns
nothing. The `@api_view` function-based endpoints get an explicit
`@permission_classes([IsAuthenticated])` rather than relying on a settings
default, so the guarantee is visible at the call site.

### 2. Tenant validation on every id taken from a URL or query string

Each endpoint resolves its `form_id` / `data_id` through a `for_user`-scoped
queryset instead of a bare `get_object_or_404`:

    form = get_object_or_404(
        Forms.objects.for_user(request.user), pk=form_id
    )

This applies to `formdata_stats`, `maps/geolocation/{form_id}`,
`maps/datapoint/{data_id}`, `values`, `values/formula`, `escalation` and
`progress`. A form or datapoint belonging to another tenant is not found, so
the response is a 404 before any aggregation runs.

### 3. Tenant-scope the querysets, not only the lookup

Validating the id is not sufficient on its own — the aggregation functions
build their own `FormData` and `Answers` querysets from that form. Those base
querysets are scoped by the caller's tenant as well, so a future caller that
skips the id check still cannot produce a cross-tenant row. Two independent
barriers, the same pattern MT-009 used for the export path.

`get_base_monitoring_qs` (`functions.py:342`) is where the registration-side
universe is built, and it is the natural place for the scope. **Its
latest-monitoring logic itself is not touched.**

### 4. Question ids in the query grammar

`/values` and `/escalation` accept question ids in `question_id`, `stack_by`,
`criteria[].question` and `columns[].question`. Each is validated to belong
to the already-validated form, so a foreign question id cannot ride in on an
otherwise valid request.

## Data flow

    GET /visualization/values?form_id=X&question_id=Q   (anonymous)
      → 401

    GET /visualization/values?form_id=X   (authenticated, X is tenant B's)
      → Forms.objects.for_user(A) has no X → 404, nothing aggregated

    GET /visualization/values?form_id=X&question_id=Q   (X and Q are A's)
      → unchanged behaviour, byte for byte

## Error handling

- Anonymous → 401 on every endpoint in the app.
- A `form_id`, `data_id` or `question_id` belonging to another tenant → 404.
  Never 403; existence is not confirmed.
- A question id that exists in the tenant but not on the requested form →
  400, as today.
- A tenant-less form (seed or test fixture) scopes on NULL, matching the
  isolation model used everywhere else.

## Testing

- Anonymous request to each of the eight endpoints returns 401.
- Authenticated request naming another tenant's `form_id` returns 404, for
  each endpoint that takes one. `/progress/1`, `/2`, `/3` enumeration is
  covered explicitly, since it is the reported hole.
- A `stack_by` or `criteria[].question` naming another tenant's question is
  rejected.
- Defense in depth: calling the aggregation function directly with a foreign
  form id still returns no cross-tenant rows, because the queryset scope
  holds independently of the view's id check.
- **Regression, and the one that matters most: the existing
  `v1_visualization` test suite passes with only authentication added to its
  requests.** `monitoring=latest` + `sum_by=parent_id` output is unchanged
  for the existing parameter set.

## Out of scope

- Deleting anything. The Fiji compute layer, the file configs and the
  `/dashboard/:slug` route all survive this slice and are removed in VIZ-009,
  after their replacement has shipped. This slice only makes them require a
  login.
- Rate limiting.
- `/visualization/monitoring-stats` and `/formdata-stats` behaviour. They back
  the manage-data screens, are unrelated to dashboards, and are hardened here
  but otherwise untouched.
