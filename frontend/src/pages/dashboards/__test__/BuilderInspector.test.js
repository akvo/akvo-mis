import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import BuilderInspector from "../BuilderInspector";
import api from "../../../lib/api";

jest.mock("../../../lib/api");
import {
  pruneConfigForForm,
  tableColumnOptions,
  monitoringForms,
  stackByOptions,
  withValidStack,
  stackValueOf,
  stackChangeOf,
  groupByOptions,
  withValidGroupBy,
  valueQuestionOptions,
  repeatAggOptions,
  valueTypeOptions,
  breakdownOptions,
  breakdownValueOf,
  breakdownChangeOf,
  withValidBreakdown,
  VALID_STACK_BY,
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
        { id: 600202, label: "Population", name: "population", type: "number" },
        { id: 600201, label: "Inspected on", name: "inspected", type: "date" },
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

// =========================================================
// The map's stored `map_mode`
// =========================================================
//
// VizMap reads `config.map_mode`; the inspector derives the same thing
// from the picked question's type. Healing a widget saved before the
// flag existed is worth doing — but only where the two actually
// disagree about what gets drawn, because `onWidgetChange` sets the
// builder's `dirty` flag, and a dirty dashboard prompts "You have
// unsaved changes" on the way out. Writing a flag that changes nothing
// would raise that prompt on every map in every existing dashboard, for
// merely clicking one.

const mapWidget = (question, config = {}) => ({
  id: 1,
  type: "map",
  title: "Sites",
  col_span: 24,
  form: 6002,
  question,
  config,
});

describe("clustering is a choice, not the default (#387)", () => {
  const SWITCH = "Cluster and size by value";

  beforeEach(() => {
    api.get.mockReset();
    api.get.mockResolvedValue({ data: { data: [] } });
  });

  const switchFor = () =>
    screen
      .getByText(SWITCH)
      .closest(".builder-inspector-switch-row")
      .querySelector("button");

  test("picking a value question leaves clustering off", () => {
    // The path an author actually takes. The heal effect covers widgets
    // saved before map_mode existed; this is the one that runs when
    // somebody builds a map today, and it must land on the default.
    const onWidgetChange = draw(mapWidget(null));
    fireEvent.mouseDown(
      screen.getByText("Select a question").closest(".ant-select-selector")
    );
    fireEvent.click(screen.getByText("Population"));
    const next = onWidgetChange.mock.calls.at(-1)[0];
    expect(next.config.map_mode).toBe("range");
  });

  test("the switch is offered for a value question", () => {
    draw(mapWidget(600202, { map_mode: "range" }));
    expect(screen.getByText(SWITCH)).toBeInTheDocument();
  });

  test("an option question is never offered it", () => {
    // Clustering by an option question's answer is what a category map
    // already does; there is nothing to size by.
    draw(mapWidget(600203, { map_mode: "category" }));
    expect(screen.queryByText(SWITCH)).toBeNull();
  });

  test("it reads off in range mode and on in quantity mode", () => {
    const { unmount } = render(
      <BuilderInspector
        widget={mapWidget(600202, { map_mode: "range" })}
        sources={SOURCES}
        dashboardName="W"
        dashboardDesc=""
        defaultFilters={{}}
        onWidgetChange={jest.fn()}
        onDashboardChange={jest.fn()}
        errorMessage={null}
      />
    );
    expect(switchFor()).toHaveAttribute("aria-checked", "false");
    unmount();
    draw(mapWidget(600202, { map_mode: "quantity" }));
    expect(switchFor()).toHaveAttribute("aria-checked", "true");
  });

  test("turning it on switches to the clustered magnitude map", () => {
    const onWidgetChange = draw(mapWidget(600202, { map_mode: "range" }));
    fireEvent.click(switchFor());
    const next = onWidgetChange.mock.calls.at(-1)[0];
    expect(next.config.map_mode).toBe("quantity");
  });

  test("turning it off goes back to ranges", () => {
    const onWidgetChange = draw(mapWidget(600202, { map_mode: "quantity" }));
    fireEvent.click(switchFor());
    const next = onWidgetChange.mock.calls.at(-1)[0];
    expect(next.config.map_mode).toBe("range");
  });

  test("Combine by is offered only while clustering", () => {
    const { unmount } = render(
      <BuilderInspector
        widget={mapWidget(600202, { map_mode: "quantity" })}
        sources={SOURCES}
        dashboardName="W"
        dashboardDesc=""
        defaultFilters={{}}
        onWidgetChange={jest.fn()}
        onDashboardChange={jest.fn()}
        errorMessage={null}
      />
    );
    expect(screen.getByText("Combine by")).toBeInTheDocument();
    unmount();
    draw(mapWidget(600202, { map_mode: "range" }));
    expect(screen.queryByText("Combine by")).toBeNull();
  });

  test("range mode shows the bands, with the open one last", () => {
    draw(
      mapWidget(600202, {
        map_mode: "range",
        value_ranges: [
          { to: 340, color: "#d73027" },
          { to: null, color: "#1a9850" },
        ],
      })
    );
    expect(screen.getByText("Colours")).toBeInTheDocument();
    expect(screen.getByText("340 and above")).toBeInTheDocument();
  });

  test("a value question with no bands yet still offers one row", () => {
    // The honest empty state: one open band claims no boundary the
    // author never set.
    draw(mapWidget(600202, { map_mode: "range" }));
    expect(screen.getByText("All values")).toBeInTheDocument();
  });

  test("editing a threshold writes it back", () => {
    const onWidgetChange = draw(
      mapWidget(600202, {
        map_mode: "range",
        value_ranges: [
          { to: 340, color: "#d73027" },
          { to: null, color: "#1a9850" },
        ],
      })
    );
    const input = document.querySelector(".ant-input-number-input");
    fireEvent.change(input, { target: { value: "500" } });
    const next = onWidgetChange.mock.calls.at(-1)[0];
    expect(next.config.value_ranges[0].to).toBe(500);
  });

  test("adding a band keeps the open one last", () => {
    // A band added after the open one could never hold a point.
    const onWidgetChange = draw(
      mapWidget(600202, {
        map_mode: "range",
        value_ranges: [
          { to: 340, color: "#d73027" },
          { to: null, color: "#1a9850" },
        ],
      })
    );
    fireEvent.click(screen.getByText("Add range"));
    const next = onWidgetChange.mock.calls.at(-1)[0].config.value_ranges;
    expect(next).toHaveLength(3);
    expect(next.at(-1).to).toBeNull();
    expect(next.slice(0, -1).every((b) => b.to !== null)).toBe(true);
  });

  test("re-seeding asks the data again and replaces the bands", async () => {
    api.get.mockResolvedValue({
      data: { data: [1, 2, 3, 4, 5, 6].map((v) => ({ group: "x", value: v })) },
    });
    const onWidgetChange = draw(
      mapWidget(600202, {
        map_mode: "range",
        value_ranges: [
          { to: 999, color: "#111" },
          { to: null, color: "#222" },
        ],
      })
    );
    fireEvent.click(screen.getByText("Re-seed from data"));
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    const next = onWidgetChange.mock.calls.at(-1)[0].config.value_ranges;
    expect(next.map((b) => b.to)).not.toContain(999);
  });

  test("a new colour scheme recolours the bands, keeping the breaks", () => {
    // The scheme reseeds an option map's status_colours and a line
    // chart's category colours; a range map's bands were left behind, so
    // picking a scheme visibly did nothing to the map.
    const onWidgetChange = draw(
      mapWidget(600202, {
        map_mode: "range",
        color_scheme: "categorical",
        value_ranges: [
          { to: 340, color: "#1890ff" },
          { to: 890, color: "#64A73B" },
          { to: null, color: "#F5A623" },
        ],
      })
    );
    fireEvent.click(screen.getByTitle("Green shades"));
    const next = onWidgetChange.mock.calls.at(-1)[0].config;
    expect(next.value_ranges.map((b) => b.color)).toEqual([
      "#006d2c",
      "#31a354",
      "#74c476",
    ]);
    // The numbers are the author's; a palette change must not move them.
    expect(next.value_ranges.map((b) => b.to)).toEqual([340, 890, null]);
  });

  test("a clustered map has no bands to recolour", () => {
    const onWidgetChange = draw(
      mapWidget(600202, { map_mode: "quantity", color_scheme: "categorical" })
    );
    fireEvent.click(screen.getByTitle("Warm"));
    const next = onWidgetChange.mock.calls.at(-1)[0].config;
    expect(next.value_ranges).toBeUndefined();
    expect(next.chart_colors[0]).toBe("#bd0026");
  });

  test("more bands than the palette has colours still recolours", () => {
    const onWidgetChange = draw(
      mapWidget(600202, {
        map_mode: "range",
        value_ranges: [1, 2, 3, 4, 5, 6].map((n) => ({
          to: n === 6 ? null : n * 10,
          color: "#000",
        })),
      })
    );
    fireEvent.click(screen.getByTitle("Warm"));
    const colors = onWidgetChange.mock.calls
      .at(-1)[0]
      .config.value_ranges.map((b) => b.color);
    expect(colors).toHaveLength(6);
    expect(colors.every((c) => c !== "#000")).toBe(true);
  });

  test("Colours are offered only while NOT clustering", () => {
    // Every clustered circle is one colour; a palette would describe
    // nothing on screen.
    draw(mapWidget(600202, { map_mode: "quantity" }));
    expect(screen.queryByText("Colours")).toBeNull();
  });

  test("turning it off seeds bands from the data, once", async () => {
    api.get.mockResolvedValue({
      data: {
        data: [10, 20, 30, 40, 50, 60].map((v, i) => ({
          group: String(i),
          value: v,
        })),
      },
    });
    const onWidgetChange = draw(mapWidget(600202, { map_mode: "quantity" }));
    fireEvent.click(switchFor());

    await waitFor(() =>
      expect(
        onWidgetChange.mock.calls.some((c) => c[0].config.value_ranges?.length)
      ).toBe(true)
    );
    const seeded = onWidgetChange.mock.calls
      .map((c) => c[0].config.value_ranges)
      .filter(Boolean)
      .at(-1);
    expect(seeded.at(-1).to).toBeNull();
    expect(seeded.length).toBeGreaterThan(1);
  });

  test("bands the author already set are never re-seeded", async () => {
    // The whole point of seeding once: their numbers stay put.
    const existing = [
      { to: 5, color: "#111" },
      { to: null, color: "#222" },
    ];
    const onWidgetChange = draw(
      mapWidget(600202, { map_mode: "quantity", value_ranges: existing })
    );
    fireEvent.click(switchFor());
    await waitFor(() => expect(onWidgetChange).toHaveBeenCalled());
    expect(api.get).not.toHaveBeenCalled();
  });

  test("a failed seed still leaves a usable editor", async () => {
    api.get.mockRejectedValue(new Error("network"));
    const onWidgetChange = draw(mapWidget(600202, { map_mode: "quantity" }));
    fireEvent.click(switchFor());
    await waitFor(() =>
      expect(
        onWidgetChange.mock.calls.some((c) => c[0].config.value_ranges)
      ).toBe(true)
    );
    const seeded = onWidgetChange.mock.calls
      .map((c) => c[0].config.value_ranges)
      .filter(Boolean)
      .at(-1);
    expect(seeded).toEqual([{ to: null, color: expect.any(String) }]);
  });
});

describe("map_mode is healed only where it changes the drawing", () => {
  test("a legacy map on a value question is switched to ranges", () => {
    // The case that matters: saved before map_mode existed, so it reads
    // as a category map and draws identical dots, ignoring the value.
    // It lands in range mode because that is the default a value
    // question gets — clustering is opted into, never inherited.
    const onWidgetChange = draw(mapWidget(600202));
    expect(onWidgetChange).toHaveBeenCalledTimes(1);
    const next = onWidgetChange.mock.calls[0][0];
    expect(next.config.map_mode).toBe("range");
    // A value question has no options, so any colours left by a
    // previous option question describe nothing.
    expect(next.config.status_colors).toEqual({});
  });

  test("a value map already set to quantity is left alone", () => {
    // The author chose clustering; inheriting the new default would
    // silently un-cluster every map shipped by #382.
    const onWidgetChange = draw(mapWidget(600202, { map_mode: "quantity" }));
    expect(onWidgetChange).not.toHaveBeenCalled();
  });

  test("a legacy map on an option question is left alone", () => {
    // Absent already means category to VizMap, so writing "category"
    // changes no pixel — and would mark the dashboard dirty for it.
    const onWidgetChange = draw(mapWidget(600203));
    expect(onWidgetChange).not.toHaveBeenCalled();
  });

  test("a map already in the right mode is left alone", () => {
    const onWidgetChange = draw(mapWidget(600202, { map_mode: "quantity" }));
    expect(onWidgetChange).not.toHaveBeenCalled();
  });

  test("a map with no question yet is left alone", () => {
    const onWidgetChange = draw(mapWidget(null));
    expect(onWidgetChange).not.toHaveBeenCalled();
  });

  test("a map stuck in quantity after a swap to an option question", () => {
    // The reverse heal, and it does change the drawing: quantity mode
    // sizes by a value the option question cannot supply.
    const onWidgetChange = draw(mapWidget(600203, { map_mode: "quantity" }));
    expect(onWidgetChange).toHaveBeenCalledTimes(1);
    expect(onWidgetChange.mock.calls[0][0].config.map_mode).toBe("category");
  });
});

describe("the map question picker", () => {
  test("offers no date question", () => {
    // /sources narrows to the four aggregatable types, but a map can
    // neither colour by a date nor size by one.
    draw(mapWidget(null));
    fireEvent.mouseDown(
      screen.getByText("Select a question").closest(".ant-select-selector")
    );
    expect(screen.getByText("Population")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.queryByText("Inspected on")).toBeNull();
  });
});

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
// The visibility switch
// =========================================================
//
// Unlike every other field in the settings panel, this one writes
// immediately through its own endpoint rather than joining the dirty
// state the Save button flushes. These tests pin both halves of that:
// a draft cannot be made public at all, and a flip never reaches
// onDashboardChange.

describe("visibility switch", () => {
  it("disables the visibility switch on a draft", () => {
    render(
      <BuilderInspector
        widget={null}
        sources={{ forms: [] }}
        dashboardName="Coverage"
        dashboardDesc=""
        defaultFilters={{}}
        isPublic={false}
        isPublished={false}
        onWidgetChange={jest.fn()}
        onDashboardChange={jest.fn()}
        onVisibilityChange={jest.fn()}
      />
    );
    expect(screen.getByText(/Publish this dashboard first/i)).toBeVisible();
    expect(
      screen.getByRole("switch", { name: /public dashboard/i })
    ).toBeDisabled();
  });

  it("reports a flip without touching dashboard state", () => {
    const onVisibilityChange = jest.fn();
    const onDashboardChange = jest.fn();
    render(
      <BuilderInspector
        widget={null}
        sources={{ forms: [] }}
        dashboardName="Coverage"
        dashboardDesc=""
        defaultFilters={{}}
        isPublic={false}
        isPublished={true}
        onWidgetChange={jest.fn()}
        onDashboardChange={onDashboardChange}
        onVisibilityChange={onVisibilityChange}
      />
    );
    fireEvent.click(screen.getByRole("switch", { name: /public dashboard/i }));
    expect(onVisibilityChange).toHaveBeenCalledWith(true);
    // The switch is not dirty state: it must never reach the Save payload.
    expect(onDashboardChange).not.toHaveBeenCalled();
  });
});

// =========================================================
// Stack by another question (VIZ-015)
// =========================================================
//
// One antd Select writes two config fields. The interesting parts are
// which questions it offers, and that it writes both fields in a single
// update — two `updateConfig` calls would each close over the same
// `widget`, so the second would put the first's field back.

describe("stackByOptions", () => {
  const QUESTIONS = [
    { id: 1, label: "Status", type: "option" },
    { id: 2, label: "Features", type: "multiple_option" },
    { id: 3, label: "Depth", type: "number" },
    { id: 4, label: "Inspected", type: "date" },
  ];
  const values = (...args) => stackByOptions(...args).map((c) => c.value);

  test("nothing can be stacked before a question is picked", () => {
    // stack_by is refused by the values endpoint AND the save
    // validator without a question, so offering it is offering a 400.
    expect(stackByOptions(QUESTIONS, null, "option")).toEqual([
      { value: "", label: "None" },
    ]);
  });

  test("an option question stacks by its own options under any grouping", () => {
    expect(values(QUESTIONS, 1, "month")).toEqual(["", "option"]);
    expect(values(QUESTIONS, 1, "parent_id")).toEqual(["", "option"]);
    expect(values(QUESTIONS, 1, "date")).toEqual(["", "option"]);
  });

  test("another question's options need group_by=option", () => {
    // Grouped by anything else the measured question contributes
    // nothing, and the chart is already spelled by measuring the other
    // question directly.
    expect(values(QUESTIONS, 1, "month")).not.toContain("q:2");
    expect(values(QUESTIONS, 1, "option")).toContain("q:2");
  });

  test("registration site is never offered for an option question", () => {
    // handle_option_question ignores stack_by=parent_id entirely and
    // falls through to the unstacked breakdown.
    expect(values(QUESTIONS, 1, "option")).not.toContain("parent_id");
    expect(values(QUESTIONS, 2, "month")).not.toContain("parent_id");
  });

  test("a number question stacks by site, and only over time", () => {
    // handle_stack_by_parent supports date and month; anything else
    // returns an empty chart.
    expect(values(QUESTIONS, 3, "month")).toEqual(["", "parent_id"]);
    expect(values(QUESTIONS, 3, "date")).toEqual(["", "parent_id"]);
    expect(values(QUESTIONS, 3, "parent_id")).toEqual([""]);
    expect(values(QUESTIONS, 3, "option")).toEqual([""]);
  });

  test("a date question cannot be stacked at all", () => {
    expect(values(QUESTIONS, 4, "option")).toEqual([""]);
  });

  test("number and date questions are never offered as stacks", () => {
    const labels = stackByOptions(QUESTIONS, 1, "option").map((c) => c.label);
    expect(labels).not.toContain("Depth");
    expect(labels).not.toContain("Inspected");
  });

  test("the widget's own question is left out", () => {
    // Stacking by it is already spelled "Option value", and a question
    // cross-tabbed against itself is a diagonal.
    expect(values(QUESTIONS, 1, "option")).not.toContain("q:1");
    expect(values(QUESTIONS, 1, "option")).toContain("q:2");
  });

  test("survives a form with no questions", () => {
    // Called bare, which also pins the defaults: a widget that has not
    // been given a form yet reaches this before /sources answers.
    expect(stackByOptions()).toEqual([{ value: "", label: "None" }]);
  });
});

describe("withValidStack", () => {
  const CHOICES = [
    { value: "", label: "None" },
    { value: "option", label: "Option value" },
    { value: "q:2", label: "Features" },
  ];

  test("keeps a choice the new shape still offers", () => {
    const config = { stack_by: "option", stack_question: 2 };
    expect(withValidStack(config, CHOICES)).toBe(config);
  });

  test("clears one it no longer offers", () => {
    // Regrouping away from group_by=option strands `q:2`, and a
    // stranded value is a guaranteed 400 rather than a cosmetic slip.
    const next = withValidStack(
      { stack_by: "option", stack_question: 2 },
      CHOICES.filter((c) => c.value !== "q:2")
    );
    expect(next.stack_by).toBeNull();
    expect(next.stack_question).toBeNull();
  });

  test("clears a stack the question type cannot draw", () => {
    const next = withValidStack({ stack_by: "parent_id" }, CHOICES);
    expect(next.stack_by).toBeNull();
  });
});

describe("pruneConfigForForm and the stack question", () => {
  test("drops a stack question the new form does not have", () => {
    const next = pruneConfigForForm(
      { stack_by: "option", stack_question: 600204 },
      [{ id: 600101 }]
    );
    expect(next.stack_question).toBeNull();
  });

  test("keeps one the new form does have", () => {
    const next = pruneConfigForForm(
      { stack_by: "option", stack_question: 600204 },
      [{ id: 600204 }]
    );
    expect(next.stack_question).toBe(600204);
  });
});

// =========================================================
// Stack by another FORM (VIZ-015.a)
// =========================================================

describe("cross-form stack choices", () => {
  const FAMILY = [
    {
      id: 6001,
      name: "Registration",
      questions: [
        { id: 600102, label: "Agencies", type: "multiple_option" },
        { id: 600103, label: "Depth", type: "number" },
      ],
    },
    {
      id: 6002,
      name: "Monitoring",
      questions: [{ id: 600203, label: "Status", type: "option" }],
    },
  ];
  const OWN = [{ id: 600203, label: "Status", type: "option" }];
  const values = (choices) =>
    choices.flatMap((c) =>
      c.options ? c.options.map((o) => o.value) : c.value
    );

  test("another form's questions appear only under parent_id", () => {
    // The join keys on the registration datapoint, which is only a key
    // under that grouping.
    expect(
      values(stackByOptions(OWN, 600203, "option", FAMILY, 6002))
    ).not.toContain("f:6001:600102");
    expect(
      values(stackByOptions(OWN, 600203, "parent_id", FAMILY, 6002))
    ).toContain("f:6001:600102");
  });

  test("they are grouped by form name", () => {
    const choices = stackByOptions(OWN, 600203, "parent_id", FAMILY, 6002);
    const group = choices.find((c) => c.options);
    expect(group.label).toBe("Registration");
  });

  test("the widget's own form is not offered as a group", () => {
    const choices = stackByOptions(OWN, 600203, "parent_id", FAMILY, 6002);
    expect(choices.filter((c) => c.options).map((c) => c.label)).toEqual([
      "Registration",
    ]);
  });

  test("non-option questions on other forms are excluded", () => {
    const vals = values(stackByOptions(OWN, 600203, "parent_id", FAMILY, 6002));
    expect(vals).not.toContain("f:6001:600103");
  });

  test("a multi-select measured question is not offered cross-form", () => {
    // The join takes one category answer per site, so it would drop
    // everything after the first without a word.
    const multi = [{ id: 600203, label: "Features", type: "multiple_option" }];
    const vals = values(
      stackByOptions(multi, 600203, "parent_id", FAMILY, 6002)
    );
    expect(vals).not.toContain("f:6001:600102");
  });
});

describe("stackValueOf and stackChangeOf", () => {
  test("a cross-form config round-trips through the Select value", () => {
    const config = { stack_by: "option", stack_question: 5, stack_form: 6001 };
    expect(stackValueOf(config)).toBe("f:6001:5");
  });

  test("selecting a form entry writes all four fields at once", () => {
    // One update: two updateConfig calls would each close over the same
    // widget and the second would undo the first.
    expect(stackChangeOf("f:6001:5", "option")).toEqual({
      stack_by: "option",
      stack_question: 5,
      stack_form: 6001,
      group_by: "parent_id",
    });
  });

  test("a same-form entry clears stack_form and keeps the grouping", () => {
    expect(stackChangeOf("q:5", "option")).toEqual({
      stack_by: "option",
      stack_question: 5,
      stack_form: null,
      group_by: "option",
    });
  });

  test("None clears everything but the grouping", () => {
    expect(stackChangeOf("", "month")).toEqual({
      stack_by: null,
      stack_question: null,
      stack_form: null,
      group_by: "month",
    });
  });

  test("withValidStack keeps a cross-form choice the groups still offer", () => {
    const config = { stack_by: "option", stack_question: 5, stack_form: 6001 };
    const choices = [
      { value: "", label: "None" },
      { label: "Registration", options: [{ value: "f:6001:5", label: "X" }] },
    ];
    expect(withValidStack(config, choices)).toBe(config);
  });

  test("withValidStack clears a cross-form choice the groups dropped", () => {
    const next = withValidStack(
      { stack_by: "option", stack_question: 5, stack_form: 6001 },
      [{ value: "", label: "None" }]
    );
    expect(next.stack_form).toBeNull();
    expect(next.stack_question).toBeNull();
    expect(next.stack_by).toBeNull();
  });

  test("changing the widget's form clears a cross-form stack", () => {
    const next = pruneConfigForForm(
      { stack_by: "option", stack_question: 600102, stack_form: 6001 },
      [{ id: 600203 }]
    );
    expect(next.stack_question).toBeNull();
    expect(next.stack_form).toBeNull();
  });
});

// =========================================================
// Group by offers only what draws
// =========================================================
//
// Measured against the compute layer: an unstacked option question has
// exactly one grouping that returns rows, and the other three drew an
// empty chart while saying nothing.

describe("groupByOptions", () => {
  const values = (q, config) => groupByOptions(q, config).map((g) => g.value);
  const OPTION = { id: 1, type: "option" };
  const MULTI = { id: 2, type: "multiple_option" };
  const NUMBER = { id: 3, type: "number" };
  const DATE = { id: 4, type: "date" };

  test("an unstacked option question has exactly one grouping", () => {
    expect(values(OPTION, {})).toEqual(["option"]);
    expect(values(MULTI, {})).toEqual(["option"]);
  });

  test("stacked by ITSELF, the bars must be something else", () => {
    // A question crossed with itself is a diagonal — one segment per bar
    // — which the backend declines to draw. Offering it put two
    // dropdowns reading "Option value" one above the other, meaning
    // different things, and the pairing drew nothing.
    expect(values(OPTION, { stack_by: "option" })).toEqual([
      "month",
      "date",
      "parent_id",
    ]);
  });

  test("stacked by ANOTHER question, only the cross-tab", () => {
    // The cross-tab is defined over options and nothing else; the
    // serializer refuses any other grouping alongside a stack question.
    expect(values(OPTION, { stack_by: "option", stack_question: 9 })).toEqual([
      "option",
    ]);
  });

  test("a cross-form stack pins the grouping to the site", () => {
    // The join keys on the registration datapoint, which is only a key
    // under parent_id. Missing this snapped a working cross-form widget
    // to `option` and the serializer refused the config that followed.
    expect(
      values(OPTION, {
        stack_by: "option",
        stack_question: 9,
        stack_form: 6001,
      })
    ).toEqual(["parent_id"]);
  });

  test("it pins the grouping whatever the measured question is", () => {
    expect(values(NUMBER, { stack_by: "option", stack_form: 6001 })).toEqual([
      "parent_id",
    ]);
  });

  test("a number question never offers option", () => {
    // It collapses to a single Total bar rather than erroring — the
    // quiet kind of wrong.
    expect(values(NUMBER, {})).toEqual(["month", "date", "parent_id"]);
  });

  test("a number question stacked by site narrows to time", () => {
    expect(values(NUMBER, { stack_by: "parent_id" })).toEqual([
      "month",
      "date",
    ]);
  });

  test("no question counts submissions, so option is meaningless", () => {
    expect(values(null, {})).toEqual(["month", "date", "parent_id"]);
    expect(values(DATE, {})).toEqual(["month", "date", "parent_id"]);
  });

  test("the option entry does not read like Stack by's", () => {
    // They sat one above the other in the panel, both saying "Option
    // value", meaning bars in one and segments in the other.
    const [own] = groupByOptions(OPTION, {});
    expect(own.label).toBe("This question's options");
    expect(VALID_STACK_BY.map((s) => s.label)).toContain("Option value");
  });
});

describe("withValidGroupBy", () => {
  test("keeps a grouping the new question still draws", () => {
    const config = { group_by: "month" };
    expect(
      withValidGroupBy(config, groupByOptions({ type: "number" }, {}))
    ).toBe(config);
  });

  test("snaps a stranded grouping to the first that draws", () => {
    // option -> number strands group_by=option, which would draw one
    // "Total" bar instead of erroring.
    const next = withValidGroupBy(
      { group_by: "option" },
      groupByOptions({ type: "number" }, {})
    );
    expect(next.group_by).toBe("month");
  });

  test("treats an absent grouping as the default", () => {
    const next = withValidGroupBy({}, groupByOptions({ type: "number" }, {}));
    expect(next.group_by).toBe("month");
  });
});

// =========================================================
// Bars measured by a number question (VIZ-015.b)
// =========================================================

describe("valueQuestionOptions", () => {
  const QUESTIONS = [
    { id: 1, label: "Status", type: "option" },
    { id: 2, label: "Features", type: "multiple_option" },
    { id: 3, label: "Project cost", type: "number" },
    { id: 4, label: "Households", type: "number" },
    { id: 5, label: "Inspected", type: "date" },
  ];

  test("offers the form's number questions", () => {
    const values = valueQuestionOptions(QUESTIONS, QUESTIONS[0]).map(
      (v) => v.value
    );
    expect(values).toEqual([3, 4]);
  });

  test("offers nothing when the measured question is a number", () => {
    // The value supplies the HEIGHT and the measured question the bars,
    // so with a number question there is nothing to give a height to.
    expect(valueQuestionOptions(QUESTIONS, QUESTIONS[2])).toEqual([]);
  });

  test("offers nothing before a question is picked", () => {
    expect(valueQuestionOptions(QUESTIONS, null)).toEqual([]);
  });

  test("carries the type through for the icon", () => {
    expect(valueQuestionOptions(QUESTIONS, QUESTIONS[0])[0].type).toBe(
      "number"
    );
  });
});

describe("repeatAggOptions", () => {
  test("offers every aggregation for a single-choice split", () => {
    expect(repeatAggOptions(false, true).map((a) => a.value)).toContain("sum");
  });

  test("withholds sum for a multi-choice split", () => {
    // A submission selecting three options contributes its full value to
    // each: right for an average, and for a sum it totals three times
    // the money that exists.
    expect(repeatAggOptions(true, true).map((a) => a.value)).not.toContain(
      "sum"
    );
    expect(repeatAggOptions(true, true).map((a) => a.value)).toContain(
      "average"
    );
  });

  test("keeps sum when the chart is not stacked", () => {
    // Unstacked bars do not visually add up, so the chart never performs
    // the addition that makes the overlap misleading.
    expect(repeatAggOptions(true, false).map((a) => a.value)).toContain("sum");
  });
});

describe("breakdownOptions", () => {
  const OPTION_Q = { id: 600203, label: "Status", type: "option" };
  const MULTI_Q = { id: 600207, label: "Agencies", type: "multiple_option" };
  const NUMBER_Q = { id: 600202, label: "Cost", type: "number" };
  const ALL = [OPTION_Q, MULTI_Q, NUMBER_Q];
  const FAMILY = [
    {
      id: 6001,
      name: "Registration",
      questions: [{ id: 600101, label: "Type", type: "option" }],
    },
    { id: 6002, name: "Monitoring", questions: ALL },
  ];
  const values = (...args) =>
    breakdownOptions(...args).map((c) => c.value ?? c.label);

  test("nothing without a question", () => {
    expect(breakdownOptions(null, ALL, FAMILY, 6002)).toEqual([]);
  });

  test("an option question offers None, the two times, the site and its siblings", () => {
    expect(values(OPTION_Q, ALL, [], 6002)).toEqual([
      "",
      "month",
      "date",
      "parent_id",
      "q:600207",
    ]);
  });

  // The whole point of the merge: these used to appear only once Group
  // by was already Registration site.
  test("a sibling form's questions are in the same list", () => {
    const groups = breakdownOptions(OPTION_Q, ALL, FAMILY, 6002).filter(
      (c) => c.options
    );
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Registration");
    expect(groups[0].options[0].value).toBe("f:6001:600101");
  });

  test("a multi-choice question is offered no cross-form entries", () => {
    // The join takes one answer per site, so it would drop data.
    expect(
      breakdownOptions(MULTI_Q, ALL, FAMILY, 6002).some((c) => c.options)
    ).toBe(false);
  });

  test("a number question offers the times and the site, and no None", () => {
    // No options of its own to fall back to, so an ungrouped number is
    // one bar labelled Total — a KPI, not a bar chart.
    expect(values(NUMBER_Q, ALL, FAMILY, 6002)).toEqual([
      "month",
      "date",
      "parent_id",
    ]);
  });

  test("the fixed choices carry an icon key and the questions a type", () => {
    const byValue = Object.fromEntries(
      breakdownOptions(OPTION_Q, ALL, [], 6002).map((c) => [c.value, c])
    );
    expect(byValue.month.icon).toBe("date");
    expect(byValue.parent_id.icon).toBe("site");
    expect(byValue["q:600207"].type).toBe("multiple_option");
  });
});

describe("breakdownValueOf and breakdownChangeOf", () => {
  test("an absent grouping reads as None", () => {
    expect(breakdownValueOf({})).toBe("");
    expect(breakdownValueOf({ group_by: "option" })).toBe("");
  });

  test("a time or site grouping reads as itself", () => {
    expect(breakdownValueOf({ group_by: "month" })).toBe("month");
    expect(breakdownValueOf({ group_by: "parent_id" })).toBe("parent_id");
  });

  test("a stack question round-trips", () => {
    const next = breakdownChangeOf("q:600207", {
      id: 1,
      type: "option",
    });
    expect(next).toEqual({
      group_by: "option",
      stack_by: "option",
      stack_question: 600207,
      stack_form: null,
    });
    expect(breakdownValueOf(next)).toBe("q:600207");
  });

  test("a cross-form choice writes parent_id and both ids", () => {
    const next = breakdownChangeOf("f:6001:600101", { id: 1, type: "option" });
    expect(next).toEqual({
      group_by: "parent_id",
      stack_by: "option",
      stack_question: 600101,
      stack_form: 6001,
    });
    expect(breakdownValueOf(next)).toBe("f:6001:600101");
  });

  // Leaving either id behind sends a question under a grouping it does
  // not belong to, which the endpoint refuses.
  test("moving to a time clears both stack ids", () => {
    const next = breakdownChangeOf("month", { id: 1, type: "option" });
    expect(next.stack_question).toBeNull();
    expect(next.stack_form).toBeNull();
    expect(next.group_by).toBe("month");
  });

  test("an option question keeps its own options as the segments", () => {
    expect(breakdownChangeOf("month", { id: 1, type: "option" }).stack_by).toBe(
      "option"
    );
  });

  test("a number question never stacks", () => {
    expect(
      breakdownChangeOf("parent_id", { id: 1, type: "number" }).stack_by
    ).toBeNull();
  });
});

describe("withValidBreakdown", () => {
  const NUMBER_Q = { id: 600202, label: "Cost", type: "number" };

  test("keeps a breakdown the new question still draws", () => {
    const config = { group_by: "month", stack_by: null };
    expect(
      withValidBreakdown(config, breakdownOptions(NUMBER_Q, [], [], 6002))
    ).toBe(config);
  });

  test("snaps None onto the first that draws when the question turns numeric", () => {
    // group_by=option on a number question draws one "Total" bar.
    const next = withValidBreakdown(
      { group_by: "option", stack_by: "option" },
      breakdownOptions(NUMBER_Q, [], [], 6002)
    );
    expect(next.group_by).toBe("month");
    expect(next.stack_by).toBeNull();
  });
});

describe("valueTypeOptions", () => {
  const values = (config) => valueTypeOptions(config).map((v) => v.value);

  test("counting bars keep both types", () => {
    expect(values({})).toEqual(["number", "percentage"]);
  });

  test("a summed value keeps percentage", () => {
    // The bar's own total is a denominator of the same quantity.
    expect(values({ value_question: 42, repeat_agg: "sum" })).toContain(
      "percentage"
    );
  });

  test("every other aggregation drops it", () => {
    // A sum of averages is not a quantity, so nothing is left to divide
    // by but a submission count.
    ["average", "max", "min", "last"].forEach((agg) => {
      expect(values({ value_question: 42, repeat_agg: agg })).toEqual([
        "number",
      ]);
    });
  });

  test("an absent aggregation reads as average, not sum", () => {
    expect(values({ value_question: 42 })).toEqual(["number"]);
  });
});

describe("pruneConfigForForm and the value question", () => {
  test("drops a value question the new form does not have", () => {
    const next = pruneConfigForForm({ value_question: 600202 }, [
      { id: 600203 },
    ]);
    expect(next.value_question).toBeNull();
  });
});
