# Widget configuration usability: design

**Status:** shipped — GitHub [#350], PR [#351], commit `f7a26d9f`.
Frontend only, 2 files.

## Problem

Two small things made the widget inspector harder to use than it needed
to be.

The Question dropdown listed labels only. A dashboard author picking
between "Water source" and "Water quality" could not tell which was a
single choice, which was a multi-choice and which was a number without
selecting one and watching what other controls appeared. The question's
type determines which groupings and value types are legal, so it is the
single most decision-relevant fact about a question and it was invisible.

For Pie widgets, the Pie/Doughnut Variant selector sat *below* Question,
Group by and Value type. Variant is the coarsest choice on the widget —
it decides what the thing looks like — and it was the last one offered.

## Decisions

- **Icon by type, not colour by type.** Four icons — number, option,
  multiple_option, date — plus a text fallback for anything else
  (`QUESTION_TYPE_ICON`,
  [`BuilderInspector.jsx:88`](../../frontend/src/pages/dashboards/BuilderInspector.jsx#L88)).
  Colour alone would not survive a monochrome print or a colour-vision
  deficiency; an icon does.
- **The icon renders on the closed control too**, via antd's
  `optionLabelProp="label"` with a `QuestionLabel` node passed as both
  the option body and its label. Showing the type only inside an open
  dropdown would solve the choosing problem and leave the *reviewing*
  problem — an author returning to a widget still could not see what it
  was bound to.
- **Variant moves to the top of the widget section**, above Data source
  and Question ([line 349](../../frontend/src/pages/dashboards/BuilderInspector.jsx#L349)).
  Ordering by decision coarseness, not by implementation order.

## Components

`QuestionLabel` is one small component reused by every question-shaped
select in the inspector: Question, scatter X, scatter Y. New question
pickers should use it rather than rendering a bare label.

## Out of scope

Icons in the widget palette (already present, different set) and type
badges anywhere outside the inspector.
