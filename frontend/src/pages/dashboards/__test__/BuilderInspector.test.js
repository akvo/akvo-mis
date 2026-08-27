import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import BuilderInspector from "../BuilderInspector";

// =========================================================
// Removing a criterion
// =========================================================
//
// The control was there from the start, as a bare `×` reusing the canvas
// card's button class — no accessible name, and no `flex: none`. The
// inspector gives a criterion row 274px (310px pane less its padding) to
// fit a 130px select, a flexible select, a 90px input and the button, with
// 18px of gaps. The button is the only item in that row with no text to
// establish a minimum width, so it absorbed the overflow and shrank to a
// sliver nobody could find or hit.
//
// These tests pin the behaviour; builder.scss keeps it visible.

const SOURCES = {
  forms: [
    { id: 6001, name: "Registration", type: "registration", questions: [] },
    {
      id: 6002,
      name: "Monitoring",
      type: "monitoring",
      questions: [
        { id: 600203, label: "Status", name: "status", type: "option" },
      ],
    },
  ],
};

const CRITERIA = [
  { type: "option_equals", question: 600203, value: "broken" },
  { type: "threshold_gt", question: 600203, value: "5" },
];

const tableWidget = (criteria = CRITERIA) => ({
  id: 1,
  type: "table",
  title: "Sites needing attention",
  col_span: 24,
  form: 6002,
  question: null,
  config: {
    criteria,
    columns: [{ key: "parent_name", source: "parent_name" }],
  },
});

const draw = (widget, onWidgetChange = jest.fn()) => {
  render(
    <BuilderInspector
      widget={widget}
      sources={SOURCES}
      dashboardName="Water access"
      dashboardDesc=""
      defaultFilters={{}}
      onWidgetChange={onWidgetChange}
      onDashboardChange={jest.fn()}
      errorMessage={null}
    />
  );
  return onWidgetChange;
};

describe("criteria rows can be removed", () => {
  test("every criterion offers a named remove control", () => {
    draw(tableWidget());

    expect(
      screen.getAllByRole("button", { name: /remove condition/i })
    ).toHaveLength(2);
  });

  test("removing one leaves the others untouched", () => {
    const onWidgetChange = draw(tableWidget());

    fireEvent.click(
      screen.getAllByRole("button", { name: /remove condition/i })[0]
    );

    expect(onWidgetChange).toHaveBeenCalledTimes(1);
    const next = onWidgetChange.mock.calls[0][0];
    expect(next.config.criteria).toEqual([CRITERIA[1]]);
  });

  test("removing the last one empties the list rather than dropping the key", () => {
    // VizTable keys its "add a filter condition" state off an empty array,
    // so the key has to survive the removal.
    const onWidgetChange = draw(tableWidget([CRITERIA[0]]));

    fireEvent.click(screen.getByRole("button", { name: /remove condition/i }));

    const next = onWidgetChange.mock.calls[0][0];
    expect(next.config.criteria).toEqual([]);
  });
});
