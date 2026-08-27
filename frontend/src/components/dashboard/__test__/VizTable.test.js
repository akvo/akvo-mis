import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizTable from "../widgets/VizTable";

// =========================================================
// The table's three states
// =========================================================
//
// /escalation requires BOTH `criteria` and `columns`
// (EscalationFilterSerializer: required=True on each), so useWidgetData
// issues no request until both exist. Without a state for the missing half
// the widget rendered an empty grid and said nothing, which reads as "the
// table is broken" rather than "the table is not finished".

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

  test("columns but no criteria asks for a filter condition", () => {
    render(<VizTable config={widget({ columns: COLUMNS })} data={null} />);
    // The half the mockup never had, and the reason a fully "configured"
    // table stayed empty: no criteria means no request at all.
    expect(screen.getByText(/filter condition/i)).toBeInTheDocument();
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
