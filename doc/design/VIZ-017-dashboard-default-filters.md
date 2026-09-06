# Dashboard default filters: design

**Status:** shipped — GitHub [#347], PR [#348], commit `9f23f3a5`.
Frontend only, 4 files, 8 insertions.

## Problem

An author turned on the date and location filters in the builder, saved,
published, and the viewer showed no filter bar at all. It reproduced on
every install and was initially suspected to be tenant-scoping — it was
not.

The bug was two mismatched defaults meeting across a save.

The inspector rendered each toggle as `defaultFilters?.date?.enabled
!== false`, so an *absent* value read as ON. A dashboard whose
`default_filters` was `{}` therefore showed both switches on.

The save payload tried to compensate with
`dashboard?.default_filters || { date: {enabled: true}, administration:
{enabled: true} }`. But `{}` is truthy in JavaScript, so the fallback
never fired. The API returns `default_filters: {}` for a new dashboard,
so the payload saved `{}` — forever.

The viewer, correctly, showed nothing:
`DashboardViewFilters` requires `Boolean(defaultFilters?.date?.enabled)`
and renders `null` when neither is enabled, rather than an empty white
strip.

So the author saw two switches on, the database held `{}`, and the viewer
honoured the database. Every layer was self-consistent; only the pair was
wrong.

## Decisions

- **The control reflects stored truth, not a guess.**
  `Boolean(defaultFilters?.date?.enabled)` — absent means off, and the
  switch says off. Turning it on writes `{date: {enabled: true}}`, which
  is what the viewer reads.
- **Delete the payload fallback rather than fix it.** With the toggle
  honest, there is nothing for a default to paper over. Making the
  fallback work (`Object.keys(...).length` instead of `||`) would have
  restored the "on unless saved off" behaviour and left two places
  encoding the default.
- **A filter defaults to off.** The alternative — defaulting on and
  migrating existing rows — changes what already-published dashboards
  show without their author asking.
- **"Monitoring period" is renamed "Date"**, in the builder and on the
  dashboard (`uiText.dashboardFilterPeriod`). The control filters
  submission dates on any form, monitoring or not.

## Testing

`DashboardViewer.test.js` asserts `default_filters` passes through to the
filter bar; `DashboardBuilder.test.js` asserts the saved payload. The
ui-text snapshot pins the rename.

Manually: a dashboard saved before this change keeps `{}` and shows no
filters — correct, and matches what its viewers already saw. Its author
turns the toggles on once.

## Out of scope

Custom per-question filters. The `default_filters` schema (VIZ-001 §4.4)
has two keys, `date` and `administration`, and adding a third would mean
inventing a persistence format this slice cannot save.
