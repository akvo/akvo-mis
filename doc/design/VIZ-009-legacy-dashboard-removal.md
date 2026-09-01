# Legacy dashboard removal: design

> **Status: implemented.** This document was a plan; it now records what
> shipped. Where the plan and the implementation diverged, the implementation
> is described and the divergence is called out rather than quietly rewritten.
> The one design item that did *not* ship is §4, which explains why.
>
> Delivered: **65 files deleted** (63 frontend, 2 backend), 22 trimmed.
> `v1_visualization` 380 tests pass; frontend 270/272, the two failures being
> `ui-text` and `Login` snapshot drift that fails identically on a clean tree.
> `flake8`, `eslint` and `prettier` clean.

## Problem

The tenant-authored dashboard builder works end to end — `/control-center/dashboard`
lists and creates, `/control-center/dashboard/:slug` authors, `/dashboards/:slug`
views — and the Fiji dashboard is still sitting next to it. Two JSON configs in the
frontend bundle, a hand-maintained registry, a Fiji-specific compute layer, two
hand-written ECharts components, a second renderer, a second widget set, a second
hook family, and the anonymous `/dashboard/:slug` route.

Keeping both is worse than either: two renderers, two config schemas, two sets of
chart components, and a growing chance a fix lands in the wrong one.

This slice removes the old one. It comes last **on purpose**: nothing is deleted
until its replacement has shipped.

## What changed since this doc was first written

The original VIZ-009 assumed VIZ-006 and VIZ-008 would **re-point the legacy
renderers** at the new schema — that `DashboardRenderer`, `ChartRenderer`,
`KPICard`, `MetricCard`, `SectionTitleWidget`, `FilterBarWidget` and
`DashboardMap/` would survive as the new viewer's component tree, and this slice
would only delete what was Fiji-shaped around them.

**That is not what was built.** VIZ-006 and VIZ-008 built a parallel stack instead:

    pages/dashboards/          DashboardList, DashboardBuilder, DashboardViewer,
                               BuilderCanvas, BuilderInspector, BuilderPalette
    components/dashboard/      DashboardGrid.jsx, widgetLayout.js,
                               DashboardViewFilters.jsx
    components/dashboard/widgets/
                               WidgetRenderer.jsx + VizBar, VizLine, VizPie,
                               VizKPI, VizMap, VizTable, VizSectionTitle,
                               useChartResize.js
    util/                      dashboardApi.js, dashboardMeasure.js,
                               hooks/useWidgetData.js

Re-pointing was tried and abandoned for a reason recorded in
`useWidgetData.js:18-27`: the legacy hooks take an `apiBlock` from a file-based
config, and the legacy escalation serializers filter on `hide` and `computed`
flags that do not exist in the VIZ-001 schema. Adapting them would have tied the
new stack to modules scheduled for deletion.

The consequence is that the two trees share **exactly one module** —
`util/hooks/useVisualizationRequest.js`, which is endpoint-and-params generic and
carries the LRU cache and in-flight request sharing. Everything else in the
legacy tree has zero consumers outside itself.

So this slice is no longer a careful keep/delete split through a shared component
tree. It is a **scope delete**: an entire subgraph comes out in one cut, and the
survivors are the ones nothing in it touches. Nothing is added: the one piece of
net-new code the plan carried is deferred for the reason recorded in §4.

**VIZ-001 is deliberately left unedited.** Its §8 disposition table still reads
`DashboardRenderer, ChartRenderer, widget components → Keep, re-pointed at the
new schema` and `/visualization/progress → Defer (D-6)`. Both were reasonable
calls at design time and neither survived contact with what VIZ-006/008 actually
built. **This document is the amendment of record** — where the two disagree,
this one is current. VIZ-001 stays as the architecture it was approved as,
rather than being rewritten after the fact to look like it predicted the
outcome.

## Decisions

- **Scope delete, not a trim.** The legacy subgraph is removed whole. Nothing in it
  is adapted, re-pointed or partially kept. Because the dependency edge count
  between the two trees is one, there is no seam to argue about — the survivor list
  is derived, not negotiated.
- **EPS and RWS are dropped.** VIZ-001 §12 Q3 left "rebuilt in the builder, kept
  alive on a pinned deploy, or dropped" as a product decision. **The answer is
  dropped.** There is no rebuild gating this slice and no pinned deploy to
  maintain. The two configs encode compute modes the VIZ-001 schema deliberately
  does not have (D-5), so there was never a mechanical migration path; if those
  dashboards are wanted again they are authored in the builder like any other
  tenant's, from a blank canvas.
- **`/visualization/progress` is deleted, reversing D-6.** D-6 deferred it —
  retained, hardened, exposed to nobody. Under scope delete, retaining a route whose
  only caller is being deleted in the same commit means shipping an anonymous
  endpoint (see the blocker below) that nothing reaches. `progress_functions.py`
  is not lost work: it is in git, and D-6's own rationale says revisit "once a
  second tenant asks for staged-progress tracking". Reviving 271 lines from history
  is cheaper than carrying an unreachable public endpoint. **This amends VIZ-001
  D-6 and the "Defer" row in §8.**
- **`/maps/datapoint/{data_id}` is deleted, for the same reason as progress.**
  Its only consumer is `DashboardMap/MapPopupCard.jsx`, which this slice removes;
  the replacement `VizMap` renders `renderPopup={(point) => point?.label}` from
  the geolocation payload and never fetches detail. `DatapointDetailView` carries
  `# public, same as GeolocationListView` in its own source, so leaving it is
  leaving a second unreferenced anonymous endpoint standing. It is generic enough
  that a future map popup may well want it back — and that is a one-view, one-
  serializer revival from git, not a rewrite.
- **Keep `/values`, `/escalation`, `/values/formula` and `/maps/geolocation`.**
  Unlike progress and datapoint, these have a live caller: `useWidgetData.js`
  hits all four. `values_functions.py`, `escalation_functions.py` and
  `formula.py` stay. `formula.py` is exactly where VIZ-001 predicted it would end
  up — the map widget's status colouring, `useWidgetData.js:210`.
  **`/escalation` in particular is not project-specific**: it backs the `table`
  widget type (`WidgetTypes.table = 5`), which is in the builder palette as
  "Table / Rows of records" and reachable by any tenant. `useWidgetData.js:115`
  is its caller.
- **The question-delete warning is deferred** (§4). It was meant to ship here —
  deleting the tracked configs is what removes the safety net that caught "this
  question is used by a dashboard" in review. It does not ship, because the
  confirmation step it was designed to attach to does not exist. §4 records what
  the delete path actually does; the warning is a follow-up.
- **No `echarts` under `components/dashboard/` afterwards** (D-10). Enforced by
  `pages/dashboards/__test__/noEchartsInViewer.test.js`, which already exists.

## Blocker: VIZ-003 has not shipped

This is not a design question, it is a fact about the current tree.

    backend/mis/settings.py:153      REST_FRAMEWORK has no DEFAULT_PERMISSION_CLASSES
    dashboard_views.py               no permission_classes on any of the three views
    dashboard_views.py:315,441       get_object_or_404(Forms, pk=form_id) — unscoped
    views.py:32,259,410              IsAuthenticated imports and decorators still
                                     commented out

So `/api/v1/visualization/values`, `/escalation/{form_id}` and `/progress/{form_id}`
are anonymous and take a sequential id straight from the URL. The `for_user`
scoping landed in `views.py` (lines 56, 329, 425, 514) but the authentication
never did, in either file.

**The new dashboard viewer is calling those endpoints.** VIZ-008 shipped on top of
an unauthenticated aggregation surface. VIZ-003 was specified to merge first,
gated on nothing, precisely so this could not happen.

VIZ-009 does not fix it — deleting `/dashboard/:slug` removes the anonymous *route*
but not the anonymous *endpoints*, and after this slice they are reachable by the
authenticated app, which is not the same as being authenticated. **VIZ-003 must
merge before or with VIZ-009.** Deleting progress here shrinks the exposed surface
from three endpoints to two; it does not close it.

## Components

### 1. Frontend deletions

63 files, ~14,800 lines.

    config/visualizations/                      both JSON configs, index.js, README

    pages/dashboard/                            Dashboard.jsx, style.scss

    components/dashboard/
      DashboardRenderer.jsx                     the legacy renderer
      ChartRenderer.jsx                         785 lines of hand-tuned ECharts
      DashboardFilters.jsx
      EscalationTable.jsx
      DotStripChart.jsx  DotsChart.jsx          bespoke ECharts (D-10)
      DashboardMap.jsx  DashboardMap/           superseded by widgets/VizMap.jsx
      compute/                                  compliance, crossTab, accessibility,
                                                kpiStack, progressHistogram,
                                                fiscalMonthRotation,
                                                valueHistogramBins, __test__
      custom-components/                        IndividualEPSOverview,
                                                IndividualRWSOverview,
                                                individual-overview/
      widgets/                                  CustomComponentWidget, TabsWidget,
                                                KPICard, MetricCard,
                                                SectionTitleWidget, FilterBarWidget,
                                                __test__/
      __test__/                                 ChartRenderer, CustomComponentWidget,
                                                TabsWidget

    lib/dashboardFilterHints.js                 + lib/__test__/
    util/hooks/                                 useDashboardConfig, useDashboardValues,
                                                useDashboardEscalation,
                                                useDashboardProgress,
                                                useDashboardFilters
    util/__test__/                              useDashboardConfig, useDashboardFilters,
                                                dashboardHooks

Trimmed, not deleted:

- `App.js` — the `/dashboard/:slug` route and the `Dashboard` import. The three
  builder routes are untouched: `/control-center/dashboard` (list),
  `/control-center/dashboard/:slug` (builder), `/dashboards/:slug` (viewer).
- `pages/index.js` — `export { default as Dashboard } from "./dashboard/Dashboard"`.
- `util/hooks/index.js` — the five legacy hook re-exports. `useVisualizationRequest`
  and `useWidgetData` are imported by path, not through the barrel, so the barrel
  ends at `useNotification` / `useResendActivation` — two lines.
- `components/layout/Header.jsx` — `listVisualizations` import, `dashboardForms`,
  `showDashboardsMenu`, the `DashboardMenu` dropdown. The nav loses the legacy
  Dashboards menu; the builder is reached from control-center. Four imports
  (`Space`, `FaChevronDown`, `getForms`, `listVisualizations`) became unused with
  it and went too; `Dropdown` stays for the user menu.
- `lib/config.js` — `allowedGlobal: ["/dashboard/", "/glaas/"]` becomes `[]`.
  `/dashboard/` goes because the feature is gone; `/glaas/` because it is already
  dead — no page, route or endpoint anywhere in the repo, just this stale string.
  `App.js`'s `public_state` / `isPublic` checks are `allowedGlobal.map(...).filter(...)`
  and work unchanged on an empty array.

Three edits the plan did not anticipate, all forced by the deletion:

- `util/__test__/dashboardMeasure.test.js` — its `ALLOWED` list carried
  `components/dashboard/DashboardMap/useMapByParent.js` with the comment
  *"Deleted with the legacy renderer in VIZ-009 (#313)"*. The test was written
  anticipating this commit and fails the moment the file goes, by design
  ("the allow-list has no stale entries"). The entry is removed, leaving
  `util/dashboardMeasure.js` as the sole writer of `monitoring=` — which is what
  VIZ-008 specified.
- `util/hooks/useVisualizationRequest.js` and `util/hooks/useWidgetData.js` —
  docstring and comment blocks that described the deleted hooks in the present
  tense. Rewritten to describe what is actually there; no code change.
- `backend/.../tests/tests_geolocation_list.py` — a comment pointing at
  `/maps/datapoint/{id}` as the place two fields are fetched from. That endpoint
  is deleted below, so the comment now says what the list response actually is.

### 2. Frontend survivors

The new stack, plus the one shared module:

    pages/dashboards/*                          all of it
    components/dashboard/DashboardGrid.jsx
    components/dashboard/widgetLayout.js
    components/dashboard/DashboardViewFilters.jsx
    components/dashboard/widgets/WidgetRenderer.jsx + Viz*.jsx + useChartResize.js
    components/dashboard/__test__/              DashboardGrid, DashboardViewFilters,
                                                VizMap, VizTable, widgetLayout
    util/dashboardApi.js  util/dashboardMeasure.js
    util/hooks/useWidgetData.js
    util/hooks/useVisualizationRequest.js       the single shared edge — untouched
    components/filters/AdministrationDropdownLocal.js
    components/map-view/MapView.jsx             manage-data, unrelated

`pages/manage-data/MonitoringOverview.jsx` and `ManageDataMap.jsx` are untouched.
They use `akvo-charts` and `/maps/geolocation` directly and were never part of
either dashboard tree.

### 3. Backend deletions

Two endpoints, and only those two. Every other route in `v1_visualization` has a
live caller after the frontend deletions — the audit is the table below, run by
tracing each route to its consumer rather than by reading the old plan.

| Endpoint | Caller after this slice | |
|---|---|---|
| `visualization/monitoring-stats` | `MonitoringOverview.jsx` | keep |
| `visualization/formdata-stats/{id}` | `ManageDataMap.jsx` | keep |
| `maps/geolocation/{id}` | `useWidgetData.js:142`, `ManageDataMap.jsx` | keep |
| `maps/datapoint/{data_id}` | **none** | **delete** |
| `visualization/values/formula` | `useWidgetData.js:210` | keep |
| `visualization/values` | `useWidgetData.js:170` | keep |
| `visualization/escalation/{id}` | `useWidgetData.js:115` (table widget) | keep |
| `visualization/progress/{id}` | **none** | **delete** |

Progress:

    progress_functions.py                       deleted whole (271 lines)
    tests/tests_visualization_progress.py       deleted (304 lines)
    dashboard_views.py                          visualization_progress and its
                                                @extend_schema block removed, with
                                                the imports of
                                                ProgressFilterSerializer,
                                                ProgressResponseSerializer,
                                                PROGRESS_EXAMPLES and
                                                handle_progress. 486 -> 346 lines
    dashboard_serializers.py                    ProgressFilterSerializer,
                                                ProgressHistogramBucketSerializer,
                                                ProgressDetailItemSerializer,
                                                ProgressResponseSerializer removed
    dashboard_examples.py                       PROGRESS_EXAMPLES removed

`split_criteria_by_form` was imported by `dashboard_views.py` only for progress,
so the import goes — but the function itself stays in `functions.py`, because
`escalation_functions.py:253` still calls it. `resolve_default_administration_id`
keeps both its callers (values and escalation).

Datapoint detail:

    views.py                                    DatapointDetailView and its
                                                DatapointDetailSerializer import
                                                removed
    serializers.py                              DatapointDetailSerializer removed
    tests/tests_geolocation_include_monitoring.py
                                                DatapointDetailTestCases removed;
                                                the geolocation tests in the same
                                                module stay. 161 -> 113 lines
    api/v1/v1_mobile/tests/tests_tenant_isolation.py
                                                test_datapoint_detail_404_on_foreign_object
                                                removed. The rest of the mobile
                                                isolation matrix is untouched and
                                                still passes.

    urls.py                                     both routes removed, with the
                                                visualization_progress and
                                                DatapointDetailView imports

**One deletion the plan did not list**, surfaced by `flake8` rather than by
tracing: `VALID_PROGRESS_FORMULAS` in `constants.py`, whose only consumer was
`ProgressFilterSerializer`. Removing the serializer left the import unused
(`F401`) and the constant unreachable, so both went. The plan said `constants.py`
was untouched; that was wrong, and this is the correction.

`functions.py`, `values_functions.py`, `escalation_functions.py`, `formula.py`,
`models.py` and every dashboard-builder module are untouched. `views.py` and
`serializers.py` are trimmed, not deleted — `monitoring_stats`, `formdata_stats`,
`GeolocationListView`, `visualization_values_formula` and their serializers all
have live callers. No migration: nothing DB-backed was removed.

`ValuesFilterSerializer`, `EscalationFilterSerializer` and the values/escalation
response serializers stay — `useWidgetData.js` is their caller.

### 4. Question-delete warning — deferred, and why

This slice was to replace a safety net it removes. Under file-based configs the
dashboard config was a tracked file, so deleting a question it referenced showed
up in a diff and a human caught it in review. Tenant-authored dashboards are rows
in a table nobody reviews — delete a question and every widget bound to it
silently becomes a placeholder, discovered by whoever built the dashboard the
next time they open it. The count itself is trivial, and is the payoff VIZ-001 §8
"Widget health" predicted, because `question` is a real FK (D-1):

    Dashboard.objects.for_user(request.user).filter(
        widgets__question=q
    ).distinct().count()

**It is not implemented here, because the design assumed a confirmation step the
form builder does not have.** The plan said the count would ride back "on the
request that already backs the confirmation". Tracing the delete path finds no
such request:

    FormBuilderEdit.jsx:100    api.put(`/manage/forms/${formId}?allow_delete=true`)

`onSave` sends `allow_delete=true` unconditionally. There is no preflight, no
confirm dialog, and no 400 for the UI to catch. A consequence worth recording
separately: the backend's existing answered-question guard
(`functions.py:107`, *"Can't delete question|Question {id} has answers"*) is
therefore unreachable from the form builder — the UI bypasses it on every save.

Warning "before" the delete requires building that confirmation step, which
changes how form saving works and would revive the answered-question guard as a
side effect. That is a real change to the form builder, not a consequence of
removing the legacy dashboard, so it is not smuggled into a deletion slice.

**Follow-up, in this order:** decide whether the form builder should confirm
destructive saves at all (it currently does not, by construction); if yes, the
dashboard count is one more line in the 400 body next to the answers guard. If
no, the fallback is a post-save warning carrying the same count. Until then a
question delete that breaks widgets stays silent, exactly as it is today — this
slice does not make it worse, it just does not make it better.

### 5. End-to-end pass

The integration coverage VIZ-001 §10 asks for, run once the old system is gone:
create → add widgets → publish → render via `/dashboards/{slug}`, and the
two-tenant isolation matrix across both namespaces.

### 6. Landed on this branch, outside the plan

Two changes not in any VIZ-009 decision above. Both are adjacent cleanup that
the deletion made visible; recorded here so the branch's diff has no unexplained
files.

**Swagger tags on the dashboard namespaces.** All eleven dashboard routes were
grouped under a meaningless `v1` tag, because neither viewset carried any
`extend_schema`. They now carry `Manage Dashboards` (authoring, mirroring the
existing `Manage Forms`) and `Dashboards` (published reads), with summaries and
descriptions.

Two things worth knowing, both caught by reading the *generated* schema rather
than the source:

- A class-level `@extend_schema_view` silently dropped `publish`, `unpublish`,
  `duplicate` and `sources` — *"argument was not found on view … will be
  ignored"*. Those four are plain methods wired through `as_view({...})` in
  `urls.py`, not `@action`-decorated, so drf-spectacular does not treat them as
  registered actions. `FormBuilderViewSet` can use the class-level form precisely
  because its custom actions go through the router. The four now carry
  `@extend_schema` on the method itself.
- `/dashboards` and `/dashboards/{slug}` both derived the operationId
  `v1_dashboards_retrieve` and collided, which spectacular was resolving by
  appending a numeral. Both now set `operation_id` explicitly.

Verified against `manage.py spectacular`: eleven routes, correct tags, no
dashboard-related warnings. The only route still tagged `v1` anywhere in the
schema is `POST /api/v1/chatbot/message`, which is unrelated and untouched.

**README.** Its "Dashboard Visualizations" section documented the file-config
system this slice deletes — every path it linked was gone. Rewritten for the
builder. Four other stale claims fixed while there: `./dc.sh log` (not a valid
subcommand — it is `logs`), a container list missing `worker` and `mailpit`,
"two docker images" where `ci/build.sh` builds three, and a line crediting the
`view_data_options` materialized view to dashboard queries when its only reader
is `monitoring_stats`, behind Manage Data's monitoring overview.

## Error handling

- Any import of a deleted module is a build failure, which is the intended
  behaviour — caught by the frontend build, not at runtime.
- `/dashboard/anything` falls through to the router's 404. It is not a
  tenant-scoped 404 from a live feature; the feature is gone.
- `/api/v1/visualization/progress/1` and `/api/v1/maps/datapoint/1` 404 from the
  URL resolver.
- A confirmed question delete that breaks widgets is not an error — the widget
  carries `is_broken` on the next read and renders the D-9 placeholder.

## Testing — results

Static checks, all confirmed after the cut:

- `grep -rn "config/visualizations" frontend/src` — nothing.
- `grep -rnE "^import .*echarts" frontend/src/components/dashboard frontend/src/pages/dashboards`
  — nothing. `noEchartsInViewer.test.js` still passes.
- `grep -rnE "useDashboard(Config|Values|Escalation|Progress|Filters)" frontend/src`
  — nothing, including the comments that used to name them.
- `grep -nEi "progress|datapoint" backend/api/v1/v1_visualization/urls.py` —
  nothing. `grep -rn "DatapointDetail" backend --include='*.py'` — nothing.
- `/maps/geolocation/{id}` still routed — it is the map widget's data source and
  is *not* what `maps/datapoint` was. Deleting one did not touch the other.
- `App.js` has no `/dashboard/:slug`; the three builder routes serve.
- `allowedGlobal` is `[]` and `public_state` is unaffected.

Suites:

- **`v1_visualization`: 380 tests pass**, minus the deleted progress module. The
  values, escalation, formula, geolocation and dashboard-builder test modules
  were untouched, so this is the evidence the cut did not overreach.
- `v1_mobile.tests.tests_tenant_isolation` passes, minus the one datapoint
  assertion.
- **Frontend: 270 of 272 pass.** The two failures are `lib/__test__/ui-text` and
  `pages/login/__test__/Login`, both snapshot drift in antd markup and trailing
  whitespace. Verified pre-existing by stashing this branch and re-running them
  on a clean tree, where they fail identically. Not caused by, and not fixed by,
  this slice.
- The seven `pages/dashboards/__test__/` modules and the five surviving
  `components/dashboard/__test__/` modules all pass — the regression gate for
  "did the cut reach into the new stack".
- `flake8` clean, `eslint` clean, `prettier --check` clean.

Not run, and honestly so:

- The end-to-end pass in §5 (create → widgets → publish → render) and the
  two-tenant isolation matrix are covered at the unit and API level by
  `tests_dashboard_*`, but were not exercised as a manual click-through. That is
  the remaining manual verification before merge.

> **A note on method.** The first frontend run was `npx react-scripts test`
> without `CI=true`, which let jest *rewrite* the two failing snapshot files
> instead of reporting them. That churn was reverted and the suite re-run with
> `CI=true` and the project's own `--transformIgnorePatterns`. Worth recording
> because the wrong invocation turns a pre-existing failure into a silent commit
> of unrelated snapshot changes.

## Out of scope

- **VIZ-003's authentication.** It is a hard prerequisite (see the blocker) but it
  is its own task and its own doc. This slice does not add `permission_classes` to
  anything.
- The question-delete warning, and the form-builder confirmation step it needs.
  Deferred per §4.
- Rebuilding EPS and RWS. Dropped, per the decision above. If either is wanted
  again it is a new dashboard authored in the builder, not a migration.
- Any change to the aggregation engine, to `useVisualizationRequest.js` (comment
  block aside), or to manage-data's map and monitoring overview.
- The two pre-existing snapshot failures (`ui-text`, `Login`). They fail on a
  clean tree; fixing them is unrelated work and would hide whether this slice
  broke anything.
- `doc/claude/iwsims-dashboard-config-example.md`, which documents the deleted
  file-config schema in detail and is now orphaned. The README no longer links
  it. Deleting it is a reasonable follow-up but was not in this plan.
- Reconciling the shipped routes with VIZ-004 §1, which specified `/dashboards`,
  `/dashboards/:slug` and `/dashboards/:slug/edit`. VIZ-006/008 shipped
  `/control-center/dashboard`, `/control-center/dashboard/:slug` and
  `/dashboards/:slug` instead — so authoring sits under a singular path and
  viewing under a plural one. Pre-existing divergence, nothing to do with this
  deletion, and changing it now would touch routes, navigation and four test
  modules.
