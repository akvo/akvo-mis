import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import BuilderInspector from "../BuilderInspector";
import {
  pruneConfigForForm,
  tableColumnOptions,
  monitoringForms,
} from "../builderConstants";

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

// =========================================================
// Switching a widget's form must not leave stale question ids behind
// =========================================================
//
// Changing the form already clears `widget.question`, but table columns and
// criteria carry question ids of their own and were left untouched. A real
// dashboard ended up with a table on form 10001 whose column referenced
// question 102 — a question belonging to form 1 — which the backend rejects
// because a column's question must belong to the widget's form.

describe("pruneConfigForForm", () => {
  const QUESTIONS = [{ id: 600203 }, { id: 600204 }];

  test("drops columns whose question is not in the new form", () => {
    const config = {
      columns: [
        { key: "parent_name", source: "parent_name" },
        { key: "answer_600203", source: "answer", question: 600203 },
        { key: "answer_102", source: "answer", question: 102 },
      ],
    };
    expect(pruneConfigForForm(config, QUESTIONS).columns).toEqual([
      { key: "parent_name", source: "parent_name" },
      { key: "answer_600203", source: "answer", question: 600203 },
    ]);
  });

  test("drops criteria whose question is not in the new form", () => {
    const config = {
      criteria: [
        { type: "option_equals", question: 600204, value: "a" },
        { type: "option_equals", question: 102, value: "b" },
      ],
    };
    expect(pruneConfigForForm(config, QUESTIONS).criteria).toEqual([
      { type: "option_equals", question: 600204, value: "a" },
    ]);
  });

  test("keeps question-free entries, which are form-independent", () => {
    const config = {
      columns: [
        { key: "parent_name", source: "parent_name" },
        { key: "administration", source: "administration" },
      ],
      criteria: [],
    };
    expect(pruneConfigForForm(config, QUESTIONS).columns).toHaveLength(2);
  });

  test("leaves keys it does not own alone", () => {
    const config = { measure: "current_state", page_size: 50 };
    const out = pruneConfigForForm(config, QUESTIONS);
    expect(out.measure).toBe("current_state");
    expect(out.page_size).toBe(50);
  });

  test("an empty form offering drops every question-bound entry", () => {
    const config = {
      columns: [{ key: "answer_1", source: "answer", question: 1 }],
      criteria: [{ type: "option_equals", question: 1, value: "x" }],
    };
    const out = pruneConfigForForm(config, []);
    expect(out.columns).toEqual([]);
    expect(out.criteria).toEqual([]);
  });
});

// =========================================================
// Table columns span two forms, with two different sources
// =========================================================
//
// /escalation is a "registration parent plus its latest monitoring child"
// query, so a table's own form is the MONITORING side. Its columns come
// from both forms and the source differs:
//
//   registration question -> parent_answer   (read off the parent)
//   monitoring question   -> answer          (read off the latest child)
//
// The inspector wrote `answer` for every question it offered, and only
// offered the widget's own form. A dashboard bound to the registration
// form with `answer` columns therefore asked a query that returns count: 0
// no matter what — verified against seeded data.

const FORMS = [
  {
    id: 6001,
    name: "Registration",
    type: "registration",
    questions: [
      { id: 102, label: "Gender" },
      { id: 106, label: "Members" },
    ],
  },
  {
    id: 6002,
    name: "Monitoring",
    type: "monitoring",
    questions: [{ id: 10106, label: "Status" }],
  },
];

describe("tableColumnOptions", () => {
  test("registration questions are read off the parent", () => {
    const opts = tableColumnOptions(FORMS, 6002);
    const gender = opts.find((o) => o.question === 102);
    expect(gender.source).toBe("parent_answer");
  });

  test("monitoring questions are read off the latest submission", () => {
    const opts = tableColumnOptions(FORMS, 6002);
    const status = opts.find((o) => o.question === 10106);
    expect(status.source).toBe("answer");
  });

  test("both forms are offered, not just the widget's own", () => {
    const opts = tableColumnOptions(FORMS, 6002);
    // Numeric sort: the default is lexicographic, which puts 10106 second.
    expect(opts.map((o) => o.question).sort((a, b) => a - b)).toEqual([
      102, 106, 10106,
    ]);
  });

  test("keys distinguish the two sources so they cannot collide", () => {
    // A question id can only appear once, but the key has to say which
    // side of the join it came from — the response is keyed by it.
    const opts = tableColumnOptions(FORMS, 6002);
    expect(opts.find((o) => o.question === 102).key).toBe("parent_answer_102");
    expect(opts.find((o) => o.question === 10106).key).toBe("answer_10106");
  });

  test("no monitoring form selected offers the registration side only", () => {
    const opts = tableColumnOptions(FORMS, null);
    expect(opts.map((o) => o.question)).toEqual([102, 106]);
  });
});

describe("monitoringForms", () => {
  test("a table may only bind to a monitoring form", () => {
    expect(monitoringForms(FORMS).map((f) => f.id)).toEqual([6002]);
  });
});

// =========================================================
// Who can view this dashboard (VIZ-010)
// =========================================================
//
// Lives in the dashboard settings panel — what the inspector shows when
// no widget is selected — because it is a property of the dashboard, not
// of anything on the canvas. Gated on `share dashboard`: publishing to
// colleagues and publishing to the internet are different acts, so an
// editor who may do the first does not silently gain the second.

const settings = (props = {}) => {
  const onDashboardChange = jest.fn();
  render(
    <BuilderInspector
      widget={null}
      sources={SOURCES}
      dashboardName="Water access"
      dashboardDesc=""
      defaultFilters={{}}
      visibility="internal"
      canShare
      onWidgetChange={jest.fn()}
      onDashboardChange={onDashboardChange}
      errorMessage={null}
      {...props}
    />
  );
  return onDashboardChange;
};

describe("the visibility control", () => {
  test("it sits in the dashboard settings panel", () => {
    settings();
    expect(screen.getByText(/who can view/i)).toBeInTheDocument();
  });

  test("turning it on writes public", () => {
    const onDashboardChange = settings();
    fireEvent.click(
      screen.getByRole("switch", { name: /anyone with the link/i })
    );
    expect(onDashboardChange).toHaveBeenCalledWith("visibility", "public");
  });

  test("turning it off writes internal", () => {
    const onDashboardChange = settings({ visibility: "public" });
    fireEvent.click(
      screen.getByRole("switch", { name: /anyone with the link/i })
    );
    expect(onDashboardChange).toHaveBeenCalledWith("visibility", "internal");
  });

  test("it says what public actually means", () => {
    // "Public" on its own does not tell an author that no sign-in is
    // required, which is the part with consequences.
    settings({ visibility: "public" });
    expect(screen.getByText(/without signing in/i)).toBeInTheDocument();
  });

  test("without the permission it is not offered", () => {
    settings({ canShare: false });
    expect(screen.queryByText(/who can view/i)).not.toBeInTheDocument();
  });

  test("a public dashboard still says so to someone who cannot change it", () => {
    // Hiding the control is right; hiding the fact is not — anyone
    // editing a public dashboard should know it is public.
    settings({ canShare: false, visibility: "public" });
    expect(screen.getByText(/public/i)).toBeInTheDocument();
  });
});
