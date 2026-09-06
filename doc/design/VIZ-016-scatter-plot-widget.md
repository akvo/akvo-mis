# Scatter plot widget: design

**Status:** shipped — GitHub [#364], PR [#365], commit `00e22b91`.
Backend and frontend, 13 files.

## Problem

Every widget answered a question about one variable. Nothing let an
author ask whether two measurements move together — population against
water points, distance against downtime — which is the first question an
analyst asks of a dataset with two numeric columns.

## Decisions

- **Extend `/visualization/values` rather than add an endpoint.** A
  scatter is selected with `mode=scatter`, an explicit parameter rather
  than inference from "two question ids are present". Everything the
  endpoint already does — tenant scoping, the public allowlist, date and
  administration filters, latest-vs-all monitoring — applies unchanged.
- **`WidgetTypes.scatter = 8`**, appended. Widget type ints are stored in
  `dashboard_widget.type` and in every published snapshot, so they are
  append-only.
- **The X axis reuses `widget.question`; Y lives in `config.question_y`.**
  The FK gives referential integrity and makes "which dashboards use this
  question" a plain join. A second FK column for one widget type is not
  worth the migration, so Y is a config id — which is why
  `allowlist_from` collects `config.question_y` explicitly
  ([`public_scope.py`](../../backend/api/v1/v1_visualization/public_scope.py)).
- **Either axis may be empty, meaning "count".** An unset axis gives every
  point the value 1, so a scatter with one axis set degrades to a strip
  plot rather than to an error. The inspector says so: "Default: each
  datapoint counts as 1".
- **Only number questions are offered** on both axes. `Answers` stores
  numerics in `value`; an option or date axis has no defined coordinate.

## Components

`handle_scatter` ([`scatter_functions.py`](../../backend/api/v1/v1_visualization/scatter_functions.py))
builds the base queryset through `get_base_monitoring_qs`, so a scatter
respects `measure` exactly as a bar does. It maps `data_id → value` per
axis and returns one point per datapoint that has *both* answers —
points missing the non-null axis are dropped rather than plotted at zero,
which would invent a correlation.

Point names come from `latest_id → name` under `monitoring=latest` and
from `FormData.name` otherwise, so a hovered point identifies the site.

`VizScatter` renders through akvo-charts' `ScatterPlot`, with axis labels
pre-filled from the selected questions and overridable. Legend off; the
axis labels carry the meaning.

## Testing

Renders identically in canvas, preview and published view
(`viewerPreviewParity.test.js`). Respects date and administration
filters. A public dashboard containing a scatter serves both axes to an
anonymous reader.

## Out of scope

Bubble size as a third variable, trend lines, and log axes.
