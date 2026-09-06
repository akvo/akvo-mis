# Bar chart stacking by another question: design

**Status:** not implemented. GitHub [#349] is open, the branch
`feature/349-viz-015-bar-chart-stacking-by-another-question` exists on
origin with no commits ahead of `main`. This is a forward design.

## Problem

"Stack by" today offers three values: None, Option value, and
Registration site (`VALID_STACK_BY = {"option", "parent_id"}`,
[`constants.py`](../../backend/api/v1/v1_visualization/constants.py)).

`option` stacks a bar by the options of the *same* question the widget is
already measuring, which answers "how does this question break down over
time". It cannot answer the more common question — "how does *this*
question break down by *that* one": functionality by water source type,
compliance by district-assigned category. That needs a second question as
the stacking dimension, and the grammar has no room for one.

## Decisions

- **Extend the value, not the parameter.** `stack_by` becomes
  `option | parent_id | question:{id}`. A new parameter would mean every
  reader — serializer, `values_functions`, the public allowlist, the
  frontend hook — grows a second branch that must stay in sync with the
  first. One parameter with a namespaced value keeps the existing
  "stack_by requires group_by and question_id" rule intact.
- **Only option-type questions may stack.** `option` and
  `multiple_option` produce a bounded set of series; a number or date
  question would produce one series per distinct value, which is not a
  stacked bar. The inspector filters the picker and the serializer
  rejects anything else, rather than relying on the UI alone.
- **The stacking question must belong to the widget's form.** The same
  rule `validate_dashboard_payload` already applies to
  `widget.question`. Cross-form stacking would reintroduce the join
  ambiguity VIZ-001 D-3 exists to prevent.

## Components

**Backend.** `VALID_STACK_BY` gains the namespaced form and
`ValuesFilterSerializer.validate` resolves the id, checking form
membership and type. `handle_stack_by_option` currently reads the series
from the measured question's own `QuestionOptions`
([`values_functions.py:362`](../../backend/api/v1/v1_visualization/values_functions.py#L362));
it takes the stacking question's options instead, joining `Answers` on
the stacking question for the same `data_ids`. Series labels come from
the stacking question's option labels.

**Frontend.** `VALID_STACK_BY` in `builderConstants.js` becomes a
function of the selected form's questions rather than a constant list.
`useWidgetData` already forwards `stack_by` untouched and already derives
`stackMapping` when it is set, so the rendering path needs no change —
`VizBar` picks `StackBar` on `Boolean(config.stack_by)` either way.

**Public dashboards.** `allowlist_from` in `public_scope.py` must collect
the stacking question id, or a public dashboard using this feature will
404 its own widget. This is the easiest thing in the change to forget.

## Testing

A stacked bar whose stacking question has three options renders three
series with those labels. A stacking question from another form is
refused at save. An anonymous caller can read a public dashboard that
uses one.

## Out of scope

Stacking line charts by a second question. `VALID_STACK_BY` is shared, so
it would follow for free, but `NEEDS_STACK_BY` covers bar and line and
the acceptance criteria name bar only — confirm before widening.
