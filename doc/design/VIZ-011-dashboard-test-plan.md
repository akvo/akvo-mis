# Dashboard visualisation test plan: design

**Status:** not started — Asana "[VIZ-011] Overall Dashboard Visualisation
Test Case" sits in To Do. No GitHub issue, no branch. This document
records the plan so it survives outside Asana.

## Problem

The dashboard builder ships as eight merged slices (VIZ-002..VIZ-010)
with unit coverage on each. Nothing walks the whole thing end to end as a
workspace admin would, and the failures that reached QA — default filters
not rendering, tables returning zero rows, widgets counting zero on every
tenant but the first — were all *integration* failures that no unit test
was positioned to catch.

## Preconditions

A workspace with a published registration form, at least one monitoring
form under it, and submitted data. A dashboard is bound to one form
family, so without that there is nothing to chart. The tester's role must
carry dashboard permissions; without them the Dashboards menu is absent
by design and there is nothing to test.

## Scope

Seven passes, in this order:

1. **Creating.** The list explains itself when empty. Create asks for a
   name and a data source, and offers only published *registration*
   forms. The data source cannot be changed afterwards and the editor
   says so.
2. **Building.** Add every widget type. An unconfigured widget prompts
   rather than drawing. The question list offers only aggregatable types
   (number, option, multiple_option, date) from the caller's own forms.
   On a monitoring form, "Current status of each site" and "Every
   submission over time" give different numbers *on purpose* — the first
   counts sites, the second counts submissions. Check both.
3. **Tables.** The widget that has caught the most problems. A new table
   picks a monitoring form by itself. Columns come from both forms and
   each checkbox says which. Headings read as words, not codes. No
   criteria means every datapoint, not none. Row cap and pager work.
   Known gap: the "Last submission" column does not work yet — a known
   issue, not a regression.
4. **Saving, previewing, publishing.** Save works on a brand-new
   dashboard with no widget touched. A validation failure names the
   widget. Preview matches the editor. Editing a published dashboard and
   saving does not change what colleagues see until Publish.
5. **Viewing.** Filters look and behave like Manage Data's. Changing one
   updates every widget. A failing widget shows its own retry and the
   rest of the page still loads.
6. **The list.** Name, description, widget count, last-updated,
   draft/published badge. Preview, Edit, Delete-with-confirm.
7. **Permissions and separation.** No dashboard permission means no menu.
   View-only means no Create/Edit/Delete. Another workspace's dashboards
   are invisible in the list *and* by pasting the URL.

## Out of scope

Load and performance. This is a correctness pass.

## Notes

Items 1–6 are UI acceptance and belong in a manual QA script. Item 7 is
the one worth automating: cross-tenant separation is already asserted at
the API level in `tests_public_dashboard_access.py` and
`tests_dashboard_read.py`, and a Cypress-level check would mostly
re-cover it. Prefer extending the API suites over building browser
automation for this.
