import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizTable from "../widgets/VizTable";

// =========================================================
// What a table needs before it can ask for anything
// =========================================================
//
// Columns, and only columns. They are what the request asks for and what
// the grid draws, and /escalation still marks them required.
//
// Criteria are not required: the criteria grammar NARROWS a list of
// datapoints, it does not define one, so a table with no conditions is the
// plain list of every datapoint — which is what a dashboard table usually
// wants. Readiness is asked of the same serializer that builds the request,
// so "what we say is missing" and "what stops the request" cannot drift.

const widget = (config = {}) => ({
  id: 1,
  type: "table",
  title: "Sites needing attention",
  form: 10001,
  config,
});

const COLUMNS = [
  { key: "parent_name", source: "parent_name", label: "Datapoint name" },
  { key: "answer_10106", source: "answer", question: 10106, label: "Members" },
];

const CRITERIA = [
  { type: "option_equals", question: 10106, value: "children" },
];

// Exactly what /escalation returns, keyed by each column's `key`.
const ROWS = [
  { id: 4, parent_name: "Conrad-Forbes", answer_10106: "children" },
  { id: 60, parent_name: "Beard PLC", answer_10106: "parent" },
];

describe("configuration states", () => {
  test("no columns asks for columns", () => {
    render(<VizTable config={widget({ criteria: CRITERIA })} data={null} />);
    expect(screen.getByText(/column/i)).toBeInTheDocument();
  });

  // Criteria are optional: they narrow the datapoint list, they do not
  // define it. A table with columns and no conditions is the plain list of
  // every datapoint, which is what a dashboard table usually wants — so
  // there is nothing to prompt for, and no gate to pass.
  test("columns and no criteria renders rows, not a prompt", () => {
    render(<VizTable config={widget({ columns: COLUMNS })} data={ROWS} />);
    expect(screen.getByText("Conrad-Forbes")).toBeInTheDocument();
    expect(screen.queryByText(/filter condition/i)).not.toBeInTheDocument();
  });

  test("an unfinished condition simply does not narrow anything", () => {
    // [{type: "option_equals", question: 10106, value: ""}] — the shape a
    // real dashboard hit. It used to serialize to nothing and cancel the
    // whole request, leaving a grid with headers and no rows.
    render(
      <VizTable
        config={widget({
          columns: COLUMNS,
          criteria: [{ type: "option_equals", question: 600203, value: "" }],
        })}
        data={ROWS}
      />
    );
    expect(screen.getByText("Conrad-Forbes")).toBeInTheDocument();
  });

  test("columns the serializer would drop count as no columns", () => {
    // `latest_date` without a question id is rejected by the backend and
    // dropped client-side, so a table whose only column is that one asks
    // for nothing.
    render(
      <VizTable
        config={widget({
          columns: [{ key: "latest_date", source: "latest_date" }],
          criteria: CRITERIA,
        })}
        data={null}
      />
    );
    expect(screen.getByText(/column/i)).toBeInTheDocument();
  });

  test("fully configured renders the rows", () => {
    render(
      <VizTable
        config={widget({ columns: COLUMNS, criteria: CRITERIA })}
        data={ROWS}
      />
    );
    expect(screen.getByText("Conrad-Forbes")).toBeInTheDocument();
    expect(screen.getByText("Beard PLC")).toBeInTheDocument();
  });

  test("built-in columns show their label, not the raw key", () => {
    render(
      <VizTable
        config={widget({ columns: COLUMNS, criteria: CRITERIA })}
        data={ROWS}
      />
    );
    expect(screen.getByText("Datapoint name")).toBeInTheDocument();
    expect(screen.queryByText("parent_name")).not.toBeInTheDocument();
  });
});

describe("row limit", () => {
  const many = Array.from({ length: 12 }, (_, i) => ({
    id: i + 1,
    parent_name: `Site ${i + 1}`,
  }));
  const cols = [
    { key: "parent_name", source: "parent_name", label: "Datapoint name" },
  ];

  test("page_size caps how many rows are drawn", () => {
    render(
      <VizTable
        config={widget({ columns: cols, criteria: CRITERIA, page_size: 5 })}
        data={many}
      />
    );
    expect(screen.getByText("Site 5")).toBeInTheDocument();
    expect(screen.queryByText("Site 6")).not.toBeInTheDocument();
  });

  test("it falls back to 20 when unset", () => {
    render(
      <VizTable
        config={widget({ columns: cols, criteria: CRITERIA })}
        data={many}
      />
    );
    expect(screen.getByText("Site 12")).toBeInTheDocument();
  });
});

// ── Server-side pagination ───────────────────────────────────────────
//
// The rows in `data` are one page, and `count` for the whole set arrives
// separately. Handing antd a single page and letting it paginate meant it
// saw exactly `pageSize` rows, concluded there was one page and — with
// `hideOnSinglePage` — hid the pager. A table with page_size 3 over 5
// datapoints showed 3 rows and no route to the other 2.

describe("paging over a set larger than the page", () => {
  const cols = [{ key: "parent_name", source: "parent_name", label: "Site" }];
  const page1 = [
    { id: 1, parent_name: "Site 1" },
    { id: 2, parent_name: "Site 2" },
    { id: 3, parent_name: "Site 3" },
  ];
  const pager = (overrides = {}) => ({
    total: 5,
    current: 1,
    pageSize: 3,
    onChange: jest.fn(),
    ...overrides,
  });

  test("the pager appears when the set is larger than the page", () => {
    render(
      <VizTable
        config={widget({ columns: cols, page_size: 3 })}
        data={page1}
        pagination={pager()}
      />
    );
    expect(screen.getByTitle("2")).toBeInTheDocument();
  });

  test("choosing a page asks the server for it", () => {
    const p = pager();
    render(
      <VizTable
        config={widget({ columns: cols, page_size: 3 })}
        data={page1}
        pagination={p}
      />
    );
    fireEvent.click(screen.getByTitle("2"));
    expect(p.onChange).toHaveBeenCalledWith(2, expect.anything());
  });

  test("one page's worth of records still hides the pager", () => {
    render(
      <VizTable
        config={widget({ columns: cols, page_size: 20 })}
        data={page1}
        pagination={pager({ total: 3, pageSize: 20 })}
      />
    );
    expect(screen.queryByTitle("2")).not.toBeInTheDocument();
  });
});
