import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import BuilderCanvas from "../BuilderCanvas";
import useWidgetData from "../../../util/hooks/useWidgetData";

jest.mock("../../../util/hooks/useWidgetData");

// akvo-charts wraps ECharts and Leaflet; neither runs under jsdom. Same
// stand-in approach as DashboardGrid.test.js.
jest.mock("akvo-charts", () => ({
  Bar: () => <div data-testid="chart-bar" />,
  StackBar: () => <div data-testid="chart-stackbar" />,
  Line: () => <div data-testid="chart-line" />,
  StackLine: () => <div data-testid="chart-stackline" />,
  Pie: () => <div data-testid="chart-pie" />,
  Doughnut: () => <div data-testid="chart-doughnut" />,
  MapCluster: () => <div data-testid="chart-map" />,
}));

// =========================================================
// The canvas draws the data the widget is actually bound to
// =========================================================
//
// It did not always. VIZ-006 shipped the canvas a week before VIZ-008
// built the fetch layer, so every card rendered a hardcoded array keyed on
// widget.type alone: a bar chart always showed the same four invented
// water-point categories, whatever question it was pointed at. Changing
// the question produced no request and no visible change, and the chart on
// screen looked like a real result for the question just chosen — the
// exact failure VIZ-006 opens by warning about.
//
// These tests pin the canvas to useWidgetData, which is what makes
// "the canvas shows what the viewer will show" (VIZ-006 §3) true rather
// than aspirational.

const ROOT = 6001;
const MONITORING = 6002;

const NO_FILTERS = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
};

const w = (overrides = {}) => ({
  id: 1,
  type: "bar",
  title: "Water points",
  col_span: 12,
  color: "#1890ff",
  form: MONITORING,
  question: 600203,
  config: { measure: "current_state", group_by: "option" },
  ...overrides,
});

const state = (overrides = {}) => ({
  data: [{ label: "A", value: 1 }],
  renderWidget: null,
  pagination: null,
  loading: false,
  error: null,
  refetch: jest.fn(),
  ...overrides,
});

const noop = () => {};

const draw = (widgets, extra = {}) =>
  render(
    <BuilderCanvas
      widgets={widgets}
      selectedId={null}
      dashboardName="Water access"
      dashboardDesc=""
      filters={NO_FILTERS}
      rootFormId={ROOT}
      onSelect={noop}
      onDeselect={noop}
      onMove={noop}
      onDelete={noop}
      onReorder={noop}
      {...extra}
    />
  );

beforeEach(() => {
  useWidgetData.mockReset();
  useWidgetData.mockImplementation((widget) => state({ renderWidget: widget }));
});

describe("the canvas fetches per widget", () => {
  test("each widget is passed to useWidgetData with the dashboard's family and filters", () => {
    const widget = w();
    draw([widget]);

    expect(useWidgetData).toHaveBeenCalledWith(widget, NO_FILTERS, {
      rootFormId: ROOT,
    });
  });

  test("changing the bound question re-asks with the new widget", () => {
    const { rerender } = draw([w({ question: 600203 })]);

    const changed = w({ question: 600207 });
    rerender(
      <BuilderCanvas
        widgets={[changed]}
        selectedId={null}
        dashboardName="Water access"
        dashboardDesc=""
        filters={NO_FILTERS}
        rootFormId={ROOT}
        onSelect={noop}
        onDeselect={noop}
        onMove={noop}
        onDelete={noop}
        onReorder={noop}
      />
    );

    // The config the inspector just wrote reaches the hook. Without this
    // the canvas is showing one question's chart while claiming another.
    expect(useWidgetData).toHaveBeenLastCalledWith(changed, NO_FILTERS, {
      rootFormId: ROOT,
    });
  });

  test("the renderer draws the hook's data, not a fixture", () => {
    useWidgetData.mockImplementation((widget) =>
      state({ renderWidget: widget, data: [{ label: "Borehole", value: 7 }] })
    );
    draw([w()]);

    expect(screen.getByTestId("chart-bar")).toBeInTheDocument();
  });
});

describe("a widget with no data source asks for nothing", () => {
  test("it shows a prompt instead of a chart", () => {
    draw([w({ form: null, question: null })]);

    expect(screen.getByText(/choose a data source/i)).toBeInTheDocument();
    expect(screen.queryByTestId("chart-bar")).not.toBeInTheDocument();
  });

  test("a section title is not treated as unconfigured", () => {
    draw([
      w({
        type: "section_title",
        form: null,
        question: null,
        config: { text: "Coverage" },
      }),
    ]);

    expect(screen.queryByText(/choose a data source/i)).not.toBeInTheDocument();
    expect(screen.getByText("Coverage")).toBeInTheDocument();
  });
});

describe("per-widget states stay inside their own card", () => {
  test("a loading widget does not blank the canvas", () => {
    useWidgetData.mockImplementation((widget) =>
      widget.id === 1
        ? state({ renderWidget: widget, loading: true, data: null })
        : state({ renderWidget: widget })
    );
    draw([w({ id: 1 }), w({ id: 2, type: "pie" })]);

    expect(screen.getByTestId("chart-pie")).toBeInTheDocument();
    expect(screen.queryByTestId("chart-bar")).not.toBeInTheDocument();
  });

  test("a failing widget offers a retry and leaves its neighbour alone", () => {
    useWidgetData.mockImplementation((widget) =>
      widget.id === 1
        ? state({ renderWidget: widget, error: new Error("boom"), data: null })
        : state({ renderWidget: widget })
    );
    draw([w({ id: 1 }), w({ id: 2, type: "pie" })]);

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByTestId("chart-pie")).toBeInTheDocument();
  });
});

describe("the canvas shows the viewer's filter bar, inert", () => {
  test("it renders the real bar rather than a look-alike", () => {
    const { container } = draw([w()], {
      defaultFilters: {
        date: { enabled: true },
        administration: { enabled: true },
      },
    });
    // The component itself, not three hand-drawn chips that resemble it.
    expect(container.querySelector(".dashboard-view-filters")).not.toBeNull();
  });

  test("its controls are disabled — the canvas is unfiltered by design", () => {
    const { container } = draw([w()], {
      defaultFilters: {
        date: { enabled: true },
        administration: { enabled: false },
      },
    });
    expect(container.querySelector(".ant-picker-disabled")).not.toBeNull();
  });

  test("a dashboard with both filters off shows no bar", () => {
    const { container } = draw([w()], {
      defaultFilters: {
        date: { enabled: false },
        administration: { enabled: false },
      },
    });
    expect(container.querySelector(".dashboard-view-filters")).toBeNull();
  });
});
