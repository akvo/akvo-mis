# VIZ-027 Frontend: Global dashboard question filter

**Task ID**: VIZ-027 (GitHub [#478](https://github.com/akvo/akvo-mis/issues/478)), frontend part
**Parent design**: [VIZ-027-global-question-filter.md](VIZ-027-global-question-filter.md)
**Sibling**: [VIZ-027-backend-global-question-filter.md](VIZ-027-backend-global-question-filter.md)
**Branch**: `epic/478-viz-global-question-filter`
**Date**: 2026-10-06 (FE-4 revised 2026-10-07: Filters panel, D-16)
**Status**: Draft

---

## 1. Scope

This document covers **how** the frontend implements VIZ-027. The parent
holds the **why**: context, requirements, the API contract, and decisions
D-1 to D-21. Decision IDs (D-x) and findings (A-x) refer to the parent.

The frontend owns:

- **Viewer**: a "Filters" button in the filter bar that opens a
  checklist per filter question, ticked = shown (D-16, D-21). The
  ticked options of each touched question are serialized into one
  sorted `global_criteria` list of `option_in` entries, plus
  `global_match` when it is "any", that every widget request carries.
- **Builder**: picking which questions the filter bar offers, by form
  and name (D-20).
- **A7**: the cross-form series request's wrong parameter name.
- **Date question** (FE-7, D-18): the builder control for the date the
  dashboard's range uses.
- **Defaults** (FE-8, D-19): new dashboards start with the date and
  administration filters on.

**Show only (D-21, 2026-10-07).** The checklist means what it shows:
the ticked options are sent as `option_in`, as in the WAI portal, and
datapoints without an answer to a filtered question are hidden. Before
D-21 the plan sent the unticked options as `option_not_in`, which kept
unanswered datapoints and could show no cloudy point after ticking only
"Cloudy". Not in this phase: a "(No answer)" row that keeps unanswered
datapoints.

Not in this phase either: FE-6, option codes without `:`, `,` or `|` in
`akvo-react-form-editor`. The backend enforces the rule (backend BE-7).

Line numbers are as of 2026-10-06 on the epic branch.

## 2. What the backend provides

| Contract | Shape | From backend task |
|---|---|---|
| `global_criteria` query parameter on `/visualization/values`, `/values/formula`, `/escalation/:id`, `/maps/geolocation/:id` | **Repeated**, one `option_in:<form_id>:<name>:<value>` per ticked value (D-15, D-20, D-21); optional `global_match=all\|any` | BE-1, BE-9, BE-10 |
| Published snapshot `default_filters.questions[]` | `{form, name, label, options: [{value, label}]}` | BE-4, BE-9 |
| Saved `default_filters.questions[]` | `{form, name}`: the registration form means the whole family, a monitoring form that form only (D-20). A 400 names `field: "default_filters.questions…"` | BE-4, BE-9 |
| `/manage/dashboards/<pk>/sources` question rows | gain `name` | BE-4 |

The viewer never reads form definitions. Everything the filter bar shows
comes from the snapshot, so it works on public dashboards (D-7).

## 3. Delivery order

```mermaid
flowchart LR
    FE1[FE-1 serializeGlobalCriteria] --> FE3[FE-3 Viewer state]
    FE2[FE-2 useWidgetData plumbing + A7] --> FE3
    FE3 --> FE4[FE-4 Filter bar]
    FE5[FE-5 Builder picker]
    FE7[FE-7 Date question picker]
    FE8[FE-8 Default filters on create]
    BE8([backend BE-8]) -.-> FE7
    BE1([backend BE-1]) -.-> FE2
    BE4([backend BE-4]) -.-> FE4
    BE4 -.-> FE5
```

FE-1, FE-2 and FE-5's UI can start at once; their tests mock the
network. Checking against a running backend needs BE-1 for FE-2/FE-3
and BE-4 for FE-4/FE-5.

---

## 4. Tasks

### FE-1: `serializeGlobalCriteria` (new `util/dashboardGlobalFilter.js`)

**Goal**: one canonical list for a selection, so equal selections share
cache keys.

**User acceptance criteria**
- [x] Picking the same options in a different order shows the same
      results at once, from cache, without reloading the charts.
- [x] "Clear all", or ticking every option of a question back, returns
      the dashboard to exactly its unfiltered view.
- [x] An option whose value contains `:` or `,` filters like any other.

**Technical acceptance criteria**
- [x] Takes `{"<form>:<name>": [values]}` and returns an **array** of
      `option_in:<form>:<name>:<value>`, one entry per value (D-15,
      D-20): keys sorted (numeric-aware), values sorted within a key.
- [x] Questions with an empty list are dropped. Returns `null` for `{}`,
      `null`, `undefined` or all-empty input.
- [x] Values are not escaped or split: `pump:_broken,_leaking` is passed
      through as is.
- [x] Does not mutate its input. A pure function with no imports.
- [x] `util/__test__/dashboardGlobalFilter.test.js` green.

```js
// VIZ-027 (D-15, D-20): {"<form>:<name>": [values]} -> one
// "option_in:<form>:<name>:<value>" per value, or null. Sorted, so
// equal selections give equal lists and widgets keep sharing cache keys.
// null lets compact() drop the parameter, so an unfiltered dashboard
// sends exactly what it sends today.
export const serializeGlobalCriteria = (selections) => {
  const entries = Object.entries(selections || {})
    .filter(([, values]) => values?.length)
    .sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }))
    .flatMap(([key, values]) =>
      [...values].sort().map((v) => `option_in:${key}:${v}`)
    );
  return entries.length ? entries : null;
};
```

`[...values]` copies before sorting: the viewer's selection must not be
reordered in place. That is a test case.

**Turns green**: `util/__test__/dashboardGlobalFilter.test.js`.

---

### FE-2: Every request carries `global_criteria` (`util/hooks/useWidgetData.js`)

**Goal**: no widget type can miss the filter.

**User acceptance criteria**
- [x] Every widget type reflects the filter: KPI, bar, pie, line,
      scatter, table, map pins, map colours, map sizes, and the
      cross-form stacked bar.
- [x] Cross-form stacked bars load on public dashboards (A7). They fail
      there today.
- [x] A dashboard without filter questions behaves exactly as before,
      with the same requests and the same cache hits.
- [x] A table on page 3 goes back to page 1 when a filter changes, as
      the WAI portal does (parent §15).

**Technical acceptance criteria**
- [x] All eight builders send `global_criteria: filters?.global_criteria`
      and `global_match: filters?.global_match`. `compact()` drops both
      when `null`; `global_match` is set only for "any" (FE-3).
- [x] `buildSeriesRequest` sends `dashboard_slug`, not `dashboard`.
- [x] The three map requests (`buildRequest` map branch,
      `buildStatusRequest`, `buildValueRequest`) send
      `date_question_id: filters?.date_question_id` too (backend BE-8,
      D-18). The comment "It has no date_question_id either" (line 168)
      is removed.
- [x] The number of requests per widget is unchanged.
- [x] The request URL repeats `global_criteria=` once per value, with no
      `[]`. Other parameters are encoded exactly as before.
- [x] The table's page resets on a filter change. `useWidgetData`
      already resets `page` when `filters` changes; the test "a filter
      change sends the table back to page 1" guards it.
- [x] `util/__test__/useWidgetData.globalCriteria.test.js` green, and
      `util/__test__/useWidgetData.test.js` stays green.

The endpoints silently drop parameters they do not know (header comment
above `buildRequest`, line 85). A builder that forgets the parameter
does not fail; it shows unfiltered data. Add
`global_criteria: filters?.global_criteria` to each of these:

| Builder | Line | Endpoint |
|---|---|---|
| `buildRequest`, scatter branch | 96 | `/visualization/values` |
| `buildRequest`, table branch | 115 | `/visualization/escalation/:root` |
| `buildRequest`, map branch | 147 | `/maps/geolocation/:root` |
| `buildRequest`, line branch | 190 | `/visualization/values` |
| `buildRequest`, default (kpi, bar, pie) | 219 | `/visualization/values` |
| `buildStatusRequest` (map colours) | 259 | `/visualization/values/formula` |
| `buildValueRequest` (map quantity/range) | 344 | `/visualization/values` |
| `buildSeriesRequest` (cross-form stack) | 401 | `/visualization/values` |

`compact()` (line 65) drops `null`, so nothing changes for a dashboard
without filter questions. The "no request names it when no filter is
set" tests guard that.

**Repeated keys (D-15).** `global_criteria` is an array. Axios 0.25
sends arrays as `global_criteria[]=…`, which Django's `getlist`
("global_criteria") does not read. The backend (as built) also ignores
`global_criteria[0]=…` and `global_criteria[]=…` on purpose, so a
bracketed key silently filters nothing. On a public dashboard only the
`(form, name)` pairs in the published filter bar are allowed; any other
pair is a 404. Give the one call in
`useVisualizationRequest.js` (line 48, `api.get(endpoint, { params })`)
a `paramsSerializer` that repeats the key without brackets:

```js
const toQuery = (params) => {
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === null || typeof value === "undefined") {
      return; // axios skips these too
    }
    (Array.isArray(value) ? value : [value]).forEach((v) =>
      query.append(key, v)
    );
  });
  return query.toString();
};
```

The other parameters are scalars, so their encoding does not change. No
new dependency. The request cache key is unaffected: the array is
already sorted (FE-1).

**A7, same task**: `buildSeriesRequest` sends `dashboard: dashboardSlug`
(line 415). Rename it to `dashboard_slug`. Without the slug, the
cross-form series request on a public dashboard is anonymous with no
dashboard named, and returns 404.

**Turns green**: `util/__test__/useWidgetData.globalCriteria.test.js`
(9 widget kinds, 3 checks each, plus A7).

---

### FE-3: Viewer state (`pages/dashboards/DashboardViewer.jsx`)

**Goal**: the viewer holds the selection and hands every widget the same
serialized filter.

**User acceptance criteria**
- [x] Applying a filter updates all widgets together.
- [x] Opening another dashboard starts with no filter.
- [x] Clearing a filter restores the unfiltered numbers.

**Technical acceptance criteria**
- [x] `EMPTY_FILTERS` has `selections: {}` and `match: "all"`, and is
      reset on slug change.
- [x] The grid's filters come from one `useMemo` over `filters`.
      `global_criteria` is derived only through `serializeGlobalCriteria`.
- [x] `selections` and `match` never appear as request parameters;
      `global_match` is sent only as "any" with at least one filter.
- [x] One filter change re-renders the grid once.
- [x] `pages/dashboards/__test__/DashboardViewer.globalFilter.test.js`
      green, and `DashboardViewer.test.js` stays green.

1. `EMPTY_FILTERS` (line 21) gains `selections: {}`. It is already
   reset when the slug changes (line 59).
2. The filter bar keeps writing the whole `filters` object through
   `onChange={setFilters}` (line 201). The grid (line 204) gets a
   derived object:

   ```js
   const gridFilters = useMemo(() => {
     const global_criteria = serializeGlobalCriteria(filters.selections);
     return {
       ...filters,
       global_criteria,
       // D-21: only meaningful with a filter, and only sent for "any".
       global_match:
         global_criteria && filters.match === "any" ? "any" : null,
     };
   }, [filters]);
   ```

   `filters` only changes identity when the filter bar emits a real
   change (FE-4 contract), so the request builders recompute once per
   change. `global_criteria` is an array or `null` (FE-1, D-15). `DashboardGrid` is already `React.memo` (line 187 there).

3. `selections` stays out of the request params: the builders read
   named keys only, and `global_criteria` is the only one added.

**Turns green**: `pages/dashboards/__test__/DashboardViewer.globalFilter.test.js`.

---

### FE-4: Filters panel (`components/dashboard/DashboardViewFilters.jsx`)

**Goal**: the viewer hides options from a "Filters" panel, using the
common checklist idiom (ticked = shown), with one reload per Apply
(D-16).

```
[📅 From → To] [All locations ▾]                         ( ⏷ Filters  1 )
                                   ┌──────────────────────────────────────┐
                                   │ Is the infrastructure operational?   │
                                   │   ☑ Operational                      │
                                   │   ☐ Non-operational                  │
                                   │ What is the water source?            │
                                   │   ☐ Ground water                     │
                                   │   ☐ Surface water                    │
                                   │   ☐ Rainwater                        │
                                   │ Tick options to show only the ticked │
                                   │ ones. Data without an answer to a    │
                                   │ filtered question is hidden.         │
                                   │                [Clear all] [Apply]   │
                                   └──────────────────────────────────────┘
```

**User acceptance criteria**
- [x] When the dashboard offers filter questions, the filter bar shows a
      "Filters" button on its right, as in the builder mockup
      (`VIZ-Example/index.html:387`), even when the date and
      administration filters are off. Without filter questions it is
      not shown.
- [x] The button opens a panel listing each question by its label, with
      a checkbox per option. Nothing is ticked at first (no filter);
      ticking options shows only those (D-16 revised 2026-10-07: every
      option ticked by default read backwards).
- [x] Unticking options does not reload the charts. "Apply" reloads
      them once and closes the panel.
- [x] Closing the panel without "Apply" (click outside, Esc) discards
      the changes.
- [x] "Apply" is disabled while nothing changed, and past 50 ticked
      values in all (the backend's cap); the panel says why. Unticking
      every option of a question removes its filter.
- [x] The button shows how many questions are filtered (badge "1").
- [x] Each applied value shows as a chip in a section of its own under
      the bar: its option label, with an info icon whose tooltip names
      the question, as the WAI portal's tags do ("Yes" alone does not say
      what it answers; the tooltip keeps the chip short). The icon's
      accessible name is the question, and the close button's names the
      question and the value. The section is set off
      by a top border. The row is one line: what does not fit collapses
      into "+N", whose popover (hover or click, below) lists the rest.
      Closing any chip removes that value at once, as the WAI portal's
      tags do (added 2026-10-07; `ActiveFilterChips.jsx`, measured by
      `rc-overflow`, the library behind antd's
      `maxTagCount="responsive"`, now declared in `package.json` at the
      range `yarn.lock` already holds).
- [x] "Clear all" unticks every option and applies at once.
- [x] The panel says that data without an answer to a filtered
      question is hidden (D-21).
- [x] With two or more filtered questions, the panel shows "Match: all
      filters / any filter" (`global_match`, default all) (D-21).
- [x] It works on a public dashboard, without logging in.
- [x] Copy is in English and French.
- [x] The button, checkboxes and actions work with the keyboard; a
      screen reader announces each question as the group's name, and
      the button's active count.

**Technical acceptance criteria**
- [x] `data-testid`s: `question-filters-button`, `question-filter-<form>-<name>`
      (one group per question), `question-filters-apply`,
      `question-filters-clear`.
- [x] State is `value.selections = {"<form>:<name>": [ticked values]}`
      for questions with something ticked; a question with nothing ticked
      is absent (no filter). Ticking every option is a filter too: only
      datapoints that answered. `value.match` is `"all"` or
      `"any"`; `global_match` is sent only when it is `"any"`.
- [x] Ticks hold option `value`s; labels are display only. A renamed or
      translated label must not change what is filtered (the WAI portal
      matches lower-cased names and breaks on renames, parent §15).
- [x] `onChange` fires only on Apply with a real change, or on Clear
      all when something was filtered. It emits
      `{...value, selections: next, match}`, where `next` keeps only
      questions with at least one option unticked (their ticked values).
- [x] The badge counts keys of `value.selections` (applied state, not
      the draft).
- [x] The header comment (lines 33–35) no longer says the "Filters"
      pill is not built.
- [x] New `uiText` keys exist in `en` and `fr`.
- [x] In the builder canvas (`disabled`), the button is rendered but
      disabled.
- [x] `VizMap`'s `colorKey` is untouched, so maps do not remount on a
      filter change.
- [x] `components/dashboard/__test__/DashboardViewFilters.questions.test.js`
      green, and `DashboardViewFilters.test.js` stays green.

1. **Show the bar** when `defaultFilters.questions` is non-empty, even
   with date and administration off. Today the early return (line 53)
   checks only those two.
2. **Update the header comment** (lines 33–35). It says the "Filters"
   pill is "not built" because no format existed to save per-question
   filters. Now one does: `default_filters.questions`.
3. **The button**: an antd `Button` with `FilterOutlined`, pushed right
   in the `dashboard-view-filters-card` row (line 78), wrapped in a
   `Badge` whose count is the number of filtered questions. Its
   `aria-label` includes the count.
4. **The panel**: an antd `Popover` (`trigger="click"`,
   `placement="bottomRight"`), body scrollable past about 60 vh. One
   `<fieldset>` per question with a `<legend>` holding the snapshot's
   `label`, and a `Checkbox.Group` of the snapshot's `options`. For a
   name group (D-14) the snapshot already holds the merged options,
   with labels such as "Fine / Clear sky"; render them as they are.
5. **Draft and apply**: copy `value.selections` into a local draft when
   the panel opens; ticking edits the draft only.
   - **Apply**: emit if the draft differs from `value.selections`, then
     close.
   - **Close** without Apply: drop the draft.
   - **Clear all**: emit `selections: {}` if anything was filtered, then
     close.
   - A question with nothing ticked is no filter; Apply removes it.
6. **Text**: add keys to `lib/ui-text.js` in `en` (line 14) and `fr`
   (`uiText.fr`, around line 1440); `de` is empty and falls back. At
   least: "Filters", "Apply", "Clear all", the unanswered note, "Tick at
   least one option", and the button's `aria-label` with the count. The
   question and option labels come from the snapshot, not from
   `uiText`.

**Turns green**: `components/dashboard/__test__/DashboardViewFilters.questions.test.js`,
rewritten for D-16 before the implementation (§6). The existing
`DashboardViewFilters.test.js` must stay green: "both disabled renders
no bar at all" still holds when there are no questions.

**Export (added 2026-10-07)**: the PNG/PDF export leaves the filter bar
out (`data-html2canvas-ignore` on `.dashboard-view-filters`): controls
mean nothing on paper. When a filter is active, a one-line summary takes
its place, so a filtered export does not read as the whole, for example
"Filtered by Date: 2026-10-01 – 2026-10-07 · Location: Jakarta · Type of
Project?: School, Households". With nothing active there is no line.
`components/dashboard/ExportFilterSummary.jsx` renders it with the class
`dashboard-export-only` (`display: none` on screen); `dashboardExport`'s
`showExportOnly` reveals it in the copy html2canvas draws. The question
values come from `ActiveFilterChips.appliedItems`, the same as the
chips; the administration's name is kept by `DashboardViewFilters` when
the cascade reports it, since the requests carry only the id. Tests:
`ExportFilterSummary.test.js`, `dashboardExport.test.js`.

---

### FE-5: Builder picker (new `pages/dashboards/DashboardQuestionFilters.jsx`)

**Goal**: the author chooses which questions the filter bar offers.

**User acceptance criteria**
- [x] In the dashboard settings, next to the date and administration
      toggles, the author finds a control to add filter questions.
- [x] It offers only questions with options, from the dashboard's own
      forms, each shown by its question text and its scope: "All forms"
      (the registration form: every form of the family that asks it) or
      one monitoring form (that form only) (D-20).
- [x] Questions already used by a widget on the canvas are listed first,
      under "Used in your widgets"; every other option question of the
      form family stays available under "Other questions in this form
      family" (D-17). Adding or removing a widget updates the groups,
      before saving.
- [x] The author can add and remove questions. The choice is saved with
      the dashboard and reaches viewers on Publish.
- [x] A refused save shows an error message.
- [x] Picking "What is the weather?" for "All forms" shows "Covers:
      Water quality visit, Quick status check": the forms that ask it
      under that name (D-20).
- [x] If the visit form's weather question has an option the check form
      lacks ("Stormy"), an "All forms" entry warns which forms have it.
      The author can still save.

**Technical acceptance criteria**
- [x] New file `pages/dashboards/DashboardQuestionFilters.jsx` with props
      `{sources, widgets, value, onChange}`; `BuilderInspector.jsx` only
      mounts it. `DashboardBuilder` passes its `widgets` state to the
      inspector (it already passes it to `AISuggestionDrawer`).
- [x] The suggested group is computed from `widgets` alone, with no
      request: `widget.question`, and in `widget.config`: `question_y`,
      `stack_question`, `category_question_id`, `value_question`,
      `criteria[].question` and `columns[].question`. Kept only when the
      question is an option or multiple-option question of
      `sources.forms`. A suggestion is the question's **name** at the
      "All forms" scope. An entry is listed once, in one group.
- [x] `question-filter-entry-<form>-<name>` with a "Remove" button per
      entry; a "Choose questions…" button opens the modal, whose rows are
      `question-filter-option-<form>:<name>` (the first version's
      `question-filter-picker` Select is gone, see the revision below).
- [x] Offers only types `option` and `multiple_option`, one entry per
      name at "All forms" (the root form id) and one per monitoring form
      asking it; never an entry already picked. Names containing `:`
      are not offered (the backend refuses them).
- [x] Saves through
      `onDashboardChange("default_filters", {...defaultFilters, questions})`,
      keeping `date`, `administration` and `toolbox`.
- [x] "Covers" hint for an "All forms" entry: the forms that ask the
      name, listed by form name. No warning role: it is information.
- [x] Copy in `uiText` for `en` and `fr`.
- [x] `pages/dashboards/__test__/DashboardQuestionFilters.test.js` green,
      and `BuilderInspector.test.js` stays green.

A new file because `BuilderInspector.jsx` is already 2,353 lines. Mount
it in the inspector's dashboard-level panel, after the date and
administration toggles (around lines 406–430):

```jsx
<DashboardQuestionFilters
  sources={sources}
  widgets={widgets}
  value={defaultFilters?.questions || []}
  onChange={(questions) =>
    onDashboardChange("default_filters", { ...defaultFilters, questions })
  }
/>
```

**Revision (2026-10-07): the picker is a modal.** The inspector column
was too narrow to tell questions apart: the same label sits in several
question groups (a monitoring form asks "Type of Power Supply" under
both "Borehole Inspection" and "Desalination Inspection", with different
names). The inspector now lists the picked entries (each with its
group) and a "Choose questions…" button that opens
`DashboardQuestionFilterModal.jsx`:

- A scope select ("Answers from": "All forms" or one monitoring form)
  and a search over label, name and group.
- Rows under section headers: "Used in your widgets" first (D-17), then
  one per question group in form order. Under "All forms", a group from
  a monitoring form reads "<group> — <form>". Each row shows the label,
  the question `name` and its options; an "All forms" row also shows
  "Covers:". A suggested row tags its group.
- Ticks are a draft: Apply calls `onChange(next)`, Cancel discards.
  Entries no longer in the forms are kept. The modal mounts only while
  open, so every opening starts from the saved value.
- Backend: `/sources` questions now carry `group` (the question group's
  label, else its name) and are ordered by group order, then question
  order. Question order restarts in every group, so ordering by it
  alone interleaved the groups.

The "Picker" item below describes the first version, which used a `Select`.

**Contract** (the tests are written against it):

- **Picker** (first version, replaced by the modal above): an antd `Select` in `data-testid="question-filter-picker"`.
  It offers option and multiple-option questions from every form in
  `sources.forms`, in two `OptGroup`s: "Used in your widgets" first,
  then "Other questions in this form family" (D-17). Each option is
  titled with the question label and shows its scope ("All forms" or a
  monitoring form's name). Entries already picked are not offered
  again. Picking calls `onChange([...value, {form, name}])`, where
  `form` is the root form id for "All forms" (D-20). The groups are a ranking,
  never a restriction: a filter on a question no widget shows (the
  status question while the charts show water samples) is the main use
  case.
- **Entries**: each picked filter renders in
  `data-testid="question-filter-entry-<form>-<name>"`, with a button
  whose accessible name is "Remove".
- **No swap warning**: D-8's "use the visit question instead" is gone;
  "All forms" already includes the visit form (D-20).
- **Covers (D-20)**: an "All forms" entry shows "Covers: <form names>",
  the forms of `sources.forms` with a live option question of that
  `name`. The filter reads the latest answer across them.
- **Option mismatch warning (D-14)**: when the questions an "All forms"
  entry covers do not all have the same option values, the entry shows a
  `role="alert"` warning listing each value that is missing from some
  forms, with its label and the forms that have it, for example
  "Stormy: only on Water quality visit". It does not block saving.
- **Errors**: a save that returns `field: "default_filters.questions…"`
  should be shown on this control. `DashboardBuilder.handleSave` today
  highlights widgets by `widget_index` and falls back to a global
  message; the global message is acceptable for a first version.

Builder copy (warning text, button labels, the picker placeholder) goes
into `lib/ui-text.js` in `en` and `fr`. The tests match the English
strings "Remove", "All forms" and "Covers:".

**Turns green**: `pages/dashboards/__test__/DashboardQuestionFilters.test.js`,
with the D-17 tests added before the implementation (§6).

---

### FE-7: Date question picker in the builder (D-18)

**Goal**: the author chooses which date the dashboard's date range uses.

```
Default filters
  Date                         [●  ]
    Date to filter on
    [ Submission date                          ▾ ]
       Submission date
       Visit date            Water quality visit, Quick status check
       Registration date     Water point registration
  Location (administration)    [●  ]
```

**User acceptance criteria**
- [x] Under the Date switch, while it is on, the author picks "Submission
      date" (the default) or a date question of the form family.
- [x] A date question asked on several forms under the same name shows
      once, with the forms that ask it.
- [x] The viewer's date range then bounds every widget by that date
      (backend BE-8).
- [x] Copy in English and French.

**Technical acceptance criteria**
- [x] In the `BuilderInspector.jsx` "Default filters" block (lines
      395–431), a `Select` in `data-testid="date-question-picker"`
      writes `onDashboardChange("default_filters", {...defaultFilters,
      date: {...defaultFilters?.date, date_question: id | null}})`.
- [x] Options come from `sources.forms`: questions of type `date`,
      grouped by `name`. The stored id is the first question of the
      group, registration form first, then by form order; the backend
      resolves the rest by name.
- [x] Hidden while Date is off; the stored value is kept.
- [x] `DashboardViewFilters` keeps sending it as `date_question_id`
      (line 67, unchanged).
- [x] `pages/dashboards/__test__/BuilderInspector.dateQuestion.test.js`
      green, and `BuilderInspector.test.js` stays green.

---

### FE-8: New dashboards start with date and administration on (D-19)

**Goal**: a new dashboard has a filter bar without extra steps.

**User acceptance criteria**
- [x] After creating a widgets dashboard, the builder shows Date and
      Location switched on; the author can switch them off.
- [x] Creating an embed dashboard is unchanged.

**Technical acceptance criteria**
- [x] `CreateDashboardModal.jsx` `createPayload` (line 184) gains
      `default_filters: {date: {enabled: true}, administration:
      {enabled: true}}`, for the AI and the empty starter alike. The
      embed branch (line 141) does not send it.
- [x] A test in `pages/dashboards/__test__/CreateDashboardModal.test.js`
      checks both payloads.
- [x] `CreateDashboardModalAI.test.js` asserts the exact create payload
      (lines 127 and 167); add `default_filters` there. That is an
      expected change, not a regression.

---

### FE-6 (deferred, optional): the form editor drops `:`, `,` and `|`

**Not in this phase** (decided 2026-10-06). The backend enforces the
rule at every entry point (backend BE-7), so `akvo-react-form-editor`
does not need a release for VIZ-027.

What the author sees without it: typing the label "Type A: hand pump"
makes the editor propose the code `type_a:_hand_pump`. Saving shows an
error naming the option and the code; the author edits the code to
`type_a_hand_pump` and saves again. Local data had 0 such values in
1,211, so this should be rare.

If it proves annoying, the change is small and lives in the editor
repository: `snakeCase` in
`src/components/question-type/SettingOption.jsx` (line 20) applies the
backend rule (lower-case, remove `:` `,` `|`, whitespace runs → `_`).
Two cautions for whoever picks it up:
- Line 137 normalizes **every** option's code on blur. It must change
  only the code being edited, or opening an old form would rewrite codes
  that answers already use.
- Line 150 compares `opt.value === snakeCase(opt.label)`; after the
  change an old code such as `a:_b` stops following label edits, which
  keeps stored codes stable.

---

## 5. Keeping re-renders cheap

Already in place: `DashboardGrid` is `React.memo`, the request builders
recompute only when `filters` changes, requests are cached by their
parameters, and a loading widget keeps its previous data. On top of
that:

- Emit only real changes (FE-4: Apply with a change, Clear all when
  filtered). A new `filters` object with the same content re-runs every
  builder and re-renders every chart.
- Sort before serializing (FE-1), so `a|b` and `b|a` share a cache key.
- Do not remount maps. `VizMap`'s `MapCluster` key is `colorKey`
  (`VizMap.jsx:202-214`): colours, `map_mode`, `map_aggregate`,
  thresholds and ranges. Nothing filter-related may be added to it.

## 6. Tests

| File | Task | Before implementation |
|---|---|---|
| `util/__test__/dashboardGlobalFilter.test.js` | FE-1 | Rewrite for `form:name` keys and `option_in` (D-20, D-21) |
| `util/__test__/useWidgetData.globalCriteria.test.js` | FE-2 | `GLOBAL` becomes `option_in` entries; add `global_match` |
| `pages/dashboards/__test__/DashboardViewer.globalFilter.test.js` | FE-3 | `selections`, `match`, `option_in` |
| `components/dashboard/__test__/DashboardViewFilters.questions.test.js` | FE-4 | Rewrite for the Filters panel (D-16, D-21), table below |
| `pages/dashboards/__test__/DashboardQuestionFilters.test.js` | FE-5 | Rewrite for `{form, name}`, "All forms", "Covers:", D-17 groups |
| `util/__test__/useVisualizationRequest.paramsSerializer.test.js` | FE-2 (D-15 repeated keys) | Unchanged |
| `pages/dashboards/__test__/BuilderInspector.dateQuestion.test.js` | FE-7 | New |
| `pages/dashboards/__test__/CreateDashboardModal.test.js`, `CreateDashboardModalAI.test.js` | FE-8 | Add `default_filters` |

The tests use the backend fixture's questions and ids (sibling §5):
700301 "Is the infrastructure operational?" (Operational,
Non-operational), and 700101 "What is the water source?" (Ground water,
Surface water, Rainwater).

### Test changes for D-20 (to make before FE-1, FE-4, FE-5)

The frontend tests still use question ids (`700301`, `700101`). Move
them to `form:name` keys before implementing: `serializeGlobalCriteria`
expects `option_in:<form>:<name>:<value>` (D-21); the viewer and filter bar
key selections by `"<form>:<name>"`; the builder saves `{form, name}`,
offers "All forms" and per-monitoring-form entries, and the D-8 swap
test is replaced by a "Covers:" test.

### Test changes for D-17 (to make before FE-5)

Add to `DashboardQuestionFilters.test.js`, with a bar widget on 700201
("Were you able to take a water sample?") and a table criterion on
700101:

| Test | Checks |
|---|---|
| Widget questions are suggested first | 700201 and 700101 sit under "Used in your widgets", 700301 under its question group (first version: "Other questions in this form family") |
| Nothing is restricted | 700301, used by no widget, can still be picked |
| Suggestions follow the canvas | Re-rendering without the bar widget moves 700201 to the other group |
| Non-option widget questions are not suggested | A KPI on a number question adds nothing to either group |

### Test changes for D-16 (to make before FE-4)

`DashboardViewFilters.questions.test.js` was written for one
multi-select per question. Rewrite it against the panel, keeping the
fixture (questions 700301 and 700101):

| Test | Checks |
|---|---|
| The button shows only with questions | No questions and both toggles off renders nothing; questions with both toggles off show the bar and the button |
| The panel lists every option, none ticked | Opening shows both questions by label; no option ticked |
| Applied state shows as ticked | `selections: {"7003:infrastructure_status": ["operational"]}` → only "Operational" ticked, badge 1 |
| Tick two, Apply once | Ticking Surface water and Ground water calls `onChange` once, on Apply, with `{"7001:water_source": ["ground_water", "surface_water"]}` |
| A second question keeps the first | The existing status selection stays when the water source changes |
| Unticking everything removes the filter | The key disappears from `selections` |
| Match toggle | Hidden with one filtered question; with two, "any" emits `match: "any"` |
| Close without Apply discards | Untick, click outside: no `onChange`; reopening shows the applied state |
| Apply disabled when unchanged or past 50 values | Both cases; the cap shows a hint |
| Clear all | Calls `onChange` once with `selections: {}`; not called when nothing was filtered |
| Disabled in the builder | `disabled` renders the button disabled |

### Test changes for D-15 (made 2026-10-06)

| File | Change |
|---|---|
| `util/__test__/dashboardGlobalFilter.test.js` | Expect arrays: one `option_not_in:<qid>:<value>` per value, sorted; add a value containing `:` and `,` |
| `util/__test__/useWidgetData.globalCriteria.test.js` | `GLOBAL` becomes an array |
| `pages/dashboards/__test__/DashboardViewer.globalFilter.test.js` | `BOTH` becomes `["option_not_in:700301:non_operational", "option_not_in:700301:operational"]` |
| New `util/__test__/useVisualizationRequest.paramsSerializer.test.js` | `paramsSerializer`: an array repeats the key without `[]`; a value with `:` `,` `\|` survives; scalars encode as before; `null` is skipped |

### Running

Use the project's `npm test` script. It carries the
`transformIgnorePatterns` for d3; without it two suites fail to parse.
Limit workers: the full suite in the dev container ran out of memory
and killed the dev server on 2026-10-05.

```bash
./dc.sh exec -e CI=true frontend npm test -- --watchAll=false --maxWorkers=2 \
  "globalCriteria|globalFilter|GlobalFilter|ViewFilters.questions|DashboardQuestionFilters"
./dc.sh exec frontend npx eslint <changed files>
```

ESLint rules to respect (`frontend/.eslintrc.json`): `curly`,
`no-undefined`, `prefer-arrow-callback`, `prefer-const`, prettier. Do not
disable rules.

---

## 7. Definition of done

- [x] Every task's user and technical acceptance criteria (§4) are
      ticked.
- [x] All VIZ-027 frontend suites green, including the tests that
      are green today.
- [x] Existing suites still green, in particular
      `DashboardViewFilters.test.js`, `DashboardViewer.test.js`,
      `useWidgetData.test.js`, `BuilderInspector.test.js`,
      `viewerPreviewParity.test.js`.
- [x] `npm run lint` and `npm run prettier` clean, and the CI lint
      (warnings as errors, `ci/build.sh`).
- [ ] Manual check on a published **public** dashboard: untick two
      options, press Apply, and see one request per widget in the
      network tab, each with the same `global_criteria`.
- [ ] Manual check on a map widget: the map does not remount on a
      filter change.

**As built (2026-10-07).** New files: `util/dashboardGlobalFilter.js`,
`components/dashboard/QuestionFilters.jsx` (the panel, kept out of
`DashboardViewFilters.jsx`), `pages/dashboards/DashboardQuestionFilters.jsx`,
`pages/dashboards/DashboardDateQuestionPicker.jsx` (copy through
`uiText`, which `BuilderInspector.jsx` does not use). `useWidgetData`
adds `globalFilters()` to all eight builders; `useVisualizationRequest`
sends a `paramsSerializer`. Not run: `yarn build`.

Code review fixes (2026-10-07):
- **The backend's cap of 50 values per request.** Show only sends the
  ticked values, so unticking one option of a 60-option question would
  send 59 and every widget would answer 400. The panel disables Apply
  past 50 and says so (`MAX_GLOBAL_CRITERIA` in `dashboardGlobalFilter.js`
  mirrors the backend constant). A question with a very long option list
  is a poor filter until "filter out" is offered for it again.
- **Builder preview and canvas** pass the saved entries (`{form, name}`,
  no options): the button shows disabled there. A question without
  options never blocks Apply for the others.
- **Keyboard**: focus moves into the panel when it opens, Escape closes
  it and drops the draft; the button has `aria-expanded` and
  `aria-haspopup`; the match choice is a `fieldset` with a `legend`.
- **Builder**: questions without a `name` are not offered; an entry no
  longer in the forms says so; each Remove button names its entry; the
  date picker shows a stored id of any form in a group as that group,
  and an unknown id as "Saved date question", never a bare number.

80 suites, 871 tests green; lint, prettier and the CI lint clean.

## 8. Open points for this part

- **Builder error placement**: a field-level error on the picker needs
  `DashboardBuilder.handleSave` to route `default_filters.*` fields.
  Out of scope unless authors find the global message unclear.
- **"All submissions" charts still show a filtered-out option** (parent
  D-2 consequence). The parent asks for a note in the user
  documentation, not a UI change. If support questions come in, a
  tooltip on such widgets is the cheapest follow-up.
