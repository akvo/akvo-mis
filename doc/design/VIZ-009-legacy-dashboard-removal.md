# Legacy dashboard removal: design

## Problem

By this point the tenant-authored dashboard works end to end, and the old one
is still there: two JSON configs in the frontend bundle, a hand-maintained
registry, roughly forty-five files of Fiji-specific compute, and the
`/dashboard/:slug` route that CLEANUP-001 flagged. Keeping both is worse than
either — two renderers, two config schemas, two sets of chart components,
and a growing chance that a fix lands in the wrong one.

This slice removes the old one. It comes last **on purpose**: nothing is
deleted until its replacement has shipped, so Fiji's dashboards keep working
through the whole build.

## Prerequisite decision

**Whether the EPS and RWS dashboards are rebuilt in the builder, kept alive
on a pinned deploy, or dropped is a product decision, not a technical one**
(VIZ-001 §13.4). It must be answered before this slice starts. The two legacy
configs are not migrated — they encode compute modes this schema
deliberately drops (D-5), so there is no mechanical path from one to the
other. If the answer is "rebuild", that is separate work by whoever owns
those dashboards, and it happens before this deletion, not after.

## Decisions (from VIZ-001 §8)

- **Delete what is Fiji-shaped.** The compliance and water-quality layer,
  `accessibility_bucket`, `cross_tab`, `kpi_stack`, `custom_component`, the
  EPS and RWS individual-overview screens, the file-config registry, and the
  anonymous route. This is the bulk of CLEANUP-001's forty-five files.
- **Keep what is generic.** `/visualization/values` and `/escalation` and
  their function modules stay — that query grammar is the correct general
  aggregation vocabulary over `Answers`, and it implements the
  latest-monitoring semantics (D-5). They were hardened in VIZ-003 and are
  not touched again here.
- **Keep `formula.py`.** A generic, Django-free bucket evaluator that
  classifies a datapoint by conditions. It is what the map widget's status
  colouring should be built on, and it is not Fiji-specific despite living
  next to code that is.
- **Delete the bespoke chart components** (D-10). `DotStripChart` and
  `DotsChart` are hand-written ECharts; every chart now comes from
  `akvo-charts`. After this slice, no module under `components/dashboard/`
  imports `echarts` or `echarts-for-react`.
- **Warn before breaking a dashboard.** Under file-based configs a human
  caught "this question is used by a dashboard" in review. Nobody will now,
  so the form builder asks.

## Components

### 1. Frontend deletions

    src/config/visualizations/            both JSON configs, index.js, README
    src/components/dashboard/compute/     compliance, crossTab, accessibility,
                                          kpiStack, progressHistogram,
                                          fiscalMonthRotation,
                                          valueHistogramBins, and __test__
    src/components/dashboard/custom-components/
                                          IndividualEPSOverview,
                                          IndividualRWSOverview,
                                          individual-overview/
    src/components/dashboard/DotStripChart.jsx
    src/components/dashboard/DotsChart.jsx
    src/components/dashboard/widgets/CustomComponentWidget.jsx
    src/components/dashboard/widgets/TabsWidget.jsx
    src/pages/dashboard/                  the legacy screen and its styles
    src/util/hooks/useDashboardConfig.js  reads the deleted registry
    src/util/hooks/useDashboardProgress.js
                                          backs /progress, which has no widget

And the route `App.js:162`, `/dashboard/:slug`.

### 2. Frontend survivors

`DashboardRenderer`, `ChartRenderer`, `EscalationTable`, `DashboardMap/`,
`KPICard`, `MetricCard`, `SectionTitleWidget`, `FilterBarWidget` — all
re-pointed at the new schema during VIZ-006 and VIZ-008. This slice only
confirms nothing left behind still imports a deleted module.

`useDashboardValues`, `useDashboardEscalation`, `useDashboardFilters`,
`useVisualizationRequest` and `dashboardFilterHints` stay.

### 3. Backend

Nothing is deleted. `/visualization/progress` and `progress_functions.py`
are retained and already hardened (D-6, VIZ-003); they simply have no caller
after the frontend deletions. `formula.py` stays. The aggregation engine is
untouched — which is why the `v1_visualization` suite is the check that this
slice broke nothing.

### 4. Question-delete warning in the form builder

The form builder's delete path counts referencing widgets:

    DashboardWidget.objects.filter(question=q).count()

and, when non-zero, warns *"This question is used by 3 dashboards"* before
soft-deleting. The delete still proceeds if confirmed — the dashboards
degrade per D-9 rather than blocking form edits — but it is no longer
silent. The count is scoped through the tenant path, so it reports only
dashboards the caller could actually see.

This is a plain join precisely because `question` is a real FK (D-1). Against
a JSON blob it would be a JSONB scan.

### 5. End-to-end pass

The integration coverage VIZ-001 §10 asks for, run once the old system is
gone: create → add widgets → publish → render via `/dashboards/{slug}`, and
the two-tenant isolation matrix across both namespaces.

## Error handling

- A confirmed question delete that breaks widgets is not an error. The
  affected widgets carry `is_broken` on the next read and render the D-9
  placeholder.
- Any import of a deleted module is a build failure, which is the intended
  behaviour — it is caught by the frontend build, not at runtime.

## Testing

- `grep -rn "config/visualizations" frontend/src` returns nothing.
- No module under `components/dashboard/` imports `echarts` or
  `echarts-for-react`.
- `/dashboard/:slug` is gone; `/dashboards/:slug` serves.
- The form-builder warning appears with the right count, is scoped to the
  tenant, and the delete proceeds on confirm.
- Integration: create → widgets → publish → render.
- Two tenants: neither sees nor can fetch the other's dashboards, and a
  cross-tenant `form_id` in a widget payload is rejected.
- **Regression: the `v1_visualization` suite still passes.** The aggregation
  engine was never touched, so if it fails, something in this slice reached
  further than it should have.
- `./dc.sh exec backend flake8` and `./dc.sh exec frontend npm run lint` both
  clean.

## Out of scope

- Rebuilding the EPS and RWS dashboards in the builder. Separate work,
  gated on the product decision above.
- Removing `/visualization/progress`. Retained (D-6); revisit when a second
  tenant asks for staged-progress tracking.
- Any change to the aggregation engine.
