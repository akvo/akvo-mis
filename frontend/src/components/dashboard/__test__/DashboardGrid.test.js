import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardGrid from "../DashboardGrid";
import useWidgetData from "../../../util/hooks/useWidgetData";

jest.mock("../../../util/hooks/useWidgetData");

// akvo-charts is an ECharts/Leaflet wrapper; neither runs under jsdom.
// Same stand-in approach as ChartRenderer.test.js.
jest.mock("akvo-charts", () => ({
  Bar: () => <div data-testid="chart-bar" />,
  StackBar: () => <div data-testid="chart-stackbar" />,
  Line: () => <div data-testid="chart-line" />,
  StackLine: () => <div data-testid="chart-stackline" />,
  Pie: () => <div data-testid="chart-pie" />,
  Doughnut: () => <div data-testid="chart-doughnut" />,
  MapCluster: () => <div data-testid="chart-map" />,
}));

const ROOT = 6001;

const w = (overrides = {}) => ({
  id: 1,
  type: "bar",
  title: "Water points",
  col_span: 12,
  color: "#1890ff",
  form: 6002,
  question: 600203,
  config: { measure: "current_state", group_by: "option" },
  ...overrides,
});

// Type-appropriate stand-ins, matching what useWidgetData really returns.
const DATA_FOR = {
  kpi: { value: 42 },
  table: [{ id: 1, site: "Nadi" }],
  map: [{ id: 1, name: "Nadi", geo: [-17.78, 177.94], status: null }],
};

const state = (overrides = {}) => ({
  data: [{ label: "A", value: 1 }],
  renderWidget: null,
  pagination: null,
  loading: false,
  error: null,
  refetch: jest.fn(),
  ...overrides,
});

// Default: every widget resolves with data, echoing its own widget back
// as renderWidget the way the real hook does.
const resolveAll = (overrides = {}) => {
  useWidgetData.mockImplementation((widget) =>
    state({
      renderWidget: widget,
      ...(DATA_FOR[widget.type] ? { data: DATA_FOR[widget.type] } : {}),
      ...overrides,
    })
  );
};

const renderGrid = (widgets, filters = {}) =>
  render(
    <DashboardGrid widgets={widgets} filters={filters} rootFormId={ROOT} />
  );

const cellFor = (title) =>
  document.querySelector(`[data-widget-title="${title}"]`);

beforeEach(() => {
  useWidgetData.mockReset();
  resolveAll();
});

describe("layout", () => {
  test("col_span reaches the cell, defaulting to full width", () => {
    renderGrid([
      w({ title: "Half" }),
      w({ id: 2, title: "Default", col_span: null }),
    ]);
    expect(cellFor("Half")).toHaveStyle("grid-column: span 12");
    expect(cellFor("Default")).toHaveStyle("grid-column: span 24");
  });

  test("an empty widget array renders the empty-dashboard message", () => {
    renderGrid([]);
    expect(screen.getByText(/no widgets yet/i)).toBeInTheDocument();
  });
});

// The mockup's view screen (index.html:363-412) and its style builders
// (679-730) pin these. They are the rules, not the pixel values.
describe("mockup chrome", () => {
  test.each([
    ["bar", true],
    ["line", true],
    ["pie", true],
    ["table", true],
    ["map", true],
    ["kpi", false],
    ["section_title", false],
  ])("a %s widget renders a card header: %s", (type, expected) => {
    renderGrid([w({ type, title: "Titled" })]);
    const header = cellFor("Titled").querySelector(
      ".dashboard-view-cell-header"
    );
    expect(Boolean(header)).toBe(expected);
  });

  test("a kpi carries the accent colour as a top border", () => {
    renderGrid([w({ type: "kpi", title: "Ops", color: "#64A73B" })]);
    expect(cellFor("Ops")).toHaveStyle("border-top: 3px solid #64A73B");
  });

  test("a non-kpi carries no top border", () => {
    renderGrid([w({ type: "bar", title: "Bars" })]);
    expect(cellFor("Bars")).not.toHaveStyle("border-top: 3px solid #1890ff");
  });

  test("a section title is not a card", () => {
    renderGrid([w({ type: "section_title", title: "Heading" })]);
    expect(cellFor("Heading").className).toMatch(/--section_title/);
  });

  test("body padding follows the type", () => {
    renderGrid([
      w({ type: "table", title: "T" }),
      w({ id: 2, type: "map", title: "M" }),
      w({ id: 3, type: "bar", title: "B" }),
    ]);
    const body = (t) => cellFor(t).querySelector(".dashboard-view-cell-body");
    expect(body("T")).toHaveStyle("padding: 0px");
    expect(body("M")).toHaveStyle("padding: 12px");
    expect(body("B")).toHaveStyle("padding: 16px");
  });

  test("chart bodies carry the view-mode fixed heights", () => {
    renderGrid([
      w({ type: "bar", title: "B" }),
      w({ id: 2, type: "pie", title: "P" }),
      w({ id: 3, type: "map", title: "M" }),
      w({ id: 4, type: "kpi", title: "K" }),
    ]);
    const body = (t) => cellFor(t).querySelector(".dashboard-view-cell-body");
    expect(body("B")).toHaveStyle("height: 300px");
    expect(body("P")).toHaveStyle("height: 320px");
    expect(body("M")).toHaveStyle("height: 380px");
    // A KPI sizes to its content.
    expect(body("K")).not.toHaveStyle("height: 300px");
  });
});

describe("the four per-widget states", () => {
  test("loading renders a skeleton in the cell", () => {
    useWidgetData.mockImplementation(() =>
      state({ loading: true, data: null })
    );
    renderGrid([w({ title: "Loading one" })]);
    expect(
      cellFor("Loading one").querySelector(".ant-skeleton")
    ).toBeInTheDocument();
  });

  test("error renders a message and a working retry", () => {
    const refetch = jest.fn();
    useWidgetData.mockImplementation(() =>
      state({ error: new Error("boom"), data: null, refetch })
    );
    renderGrid([w({ title: "Broken request" })]);

    expect(screen.getByText(/couldn't load this widget/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });

  test("a broken widget shows the question placeholder", () => {
    renderGrid([
      w({ title: "Stale", is_broken: true, broken_reason: "question_deleted" }),
    ]);
    expect(screen.getByText(/question no longer exists/i)).toBeInTheDocument();
  });

  test("broken_reason form_deleted blames the form, not the question", () => {
    renderGrid([
      w({ title: "Stale", is_broken: true, broken_reason: "form_deleted" }),
    ]);
    expect(screen.getByText(/form no longer exists/i)).toBeInTheDocument();
  });

  test("data renders the widget renderer", () => {
    renderGrid([w({ title: "Bars" })]);
    expect(screen.getByTestId("chart-bar")).toBeInTheDocument();
  });
});

describe("isolation", () => {
  test("one broken widget leaves every other widget rendered", () => {
    const widgets = [
      w({ id: 1, type: "kpi", title: "One" }),
      w({ id: 2, type: "bar", title: "Two" }),
      w({
        id: 3,
        type: "bar",
        title: "Three",
        is_broken: true,
        broken_reason: "question_deleted",
      }),
      w({ id: 4, type: "pie", title: "Four" }),
      w({ id: 5, type: "line", title: "Five" }),
    ];
    renderGrid(widgets);

    ["One", "Two", "Three", "Four", "Five"].forEach((t) =>
      expect(cellFor(t)).toBeInTheDocument()
    );
    // The broken one keeps its position and its title.
    expect(
      cellFor("Three").querySelector(".dashboard-view-cell-header")
    ).toHaveTextContent("Three");
    expect(screen.getByText(/question no longer exists/i)).toBeInTheDocument();
    expect(screen.getByTestId("chart-pie")).toBeInTheDocument();
    expect(screen.getByTestId("chart-line")).toBeInTheDocument();
  });

  test("the cell delegates the no-request decision rather than duplicating it", () => {
    renderGrid([w({ title: "Stale", is_broken: true })]);
    // The hook is still called, and still receives is_broken — the guard
    // lives in one place (useWidgetData), not two.
    expect(useWidgetData).toHaveBeenCalled();
    expect(useWidgetData.mock.calls[0][0].is_broken).toBe(true);
  });

  test("one widget's request failing leaves the others rendered", () => {
    useWidgetData.mockImplementation((widget) =>
      widget.id === 3
        ? state({ error: new Error("boom"), data: null })
        : state({
            renderWidget: widget,
            ...(DATA_FOR[widget.type] ? { data: DATA_FOR[widget.type] } : {}),
          })
    );
    renderGrid([
      w({ id: 1, type: "kpi", title: "One" }),
      w({ id: 2, type: "bar", title: "Two" }),
      w({ id: 3, type: "bar", title: "Three" }),
      w({ id: 4, type: "pie", title: "Four" }),
    ]);

    expect(screen.getByText(/couldn't load this widget/i)).toBeInTheDocument();
    expect(screen.getByTestId("chart-bar")).toBeInTheDocument();
    expect(screen.getByTestId("chart-pie")).toBeInTheDocument();
  });
});

describe("filters", () => {
  test("a filter change reaches every data widget and no section title", () => {
    const widgets = [
      w({ id: 1, type: "kpi", title: "One" }),
      w({ id: 2, type: "section_title", title: "Heading" }),
    ];
    const { rerender } = renderGrid(widgets, { administration_id: null });

    useWidgetData.mockClear();
    rerender(
      <DashboardGrid
        widgets={widgets}
        filters={{ administration_id: 42 }}
        rootFormId={ROOT}
      />
    );

    const kpiCall = useWidgetData.mock.calls.find((c) => c[0].type === "kpi");
    expect(kpiCall[1]).toEqual({ administration_id: 42 });
    // The section title goes through the same hook, which returns early —
    // asserting it makes no request is useWidgetData's job, not the grid's.
    expect(screen.getByText("Heading")).toBeInTheDocument();
  });
});
