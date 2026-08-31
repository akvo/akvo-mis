import React from "react";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardGrid from "../DashboardGrid";
import BuilderCanvas from "../../../pages/dashboards/BuilderCanvas";
import useWidgetData from "../../../util/hooks/useWidgetData";
import { WIDGET_BODY_HEIGHT } from "../widgetLayout";

jest.mock("../../../util/hooks/useWidgetData");
jest.mock("../DashboardViewFilters", () => {
  const MockFilters = () => <div data-testid="filters" />;
  MockFilters.displayName = "DashboardViewFilters";
  return MockFilters;
});
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
// The canvas and the viewer size a chart identically
// =========================================================
//
// App.scss:355 pins every akvo-charts chart in the app to `height: 500px`
// via `div[role="figure"]`. The viewer overrides it (viewer.scss:232) and
// bounds each cell to a per-type height; the canvas never did, so its
// cards grew to fit a 500px chart while the same widget rendered at 300px
// in preview — the surface the author reviews and the surface colleagues
// see disagreed by roughly 40% of the chart's height.
//
// VIZ-006 §3 is explicit that the canvas shows what the viewer will show,
// so the height belongs in one place that both read.

const noop = () => {};

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

beforeEach(() => {
  useWidgetData.mockImplementation((widget) => ({
    data: [{ label: "A", value: 1 }],
    renderWidget: widget,
    pagination: null,
    loading: false,
    error: null,
    refetch: jest.fn(),
  }));
});

const viewerBody = (widget) => {
  const { container } = render(
    <DashboardGrid widgets={[widget]} filters={{}} rootFormId={6001} />
  );
  return container.querySelector(".dashboard-view-cell-body");
};

const canvasBody = (widget) => {
  const { container } = render(
    <BuilderCanvas
      widgets={[widget]}
      selectedId={null}
      dashboardName="D"
      dashboardDesc=""
      filters={{}}
      rootFormId={6001}
      defaultFilters={{}}
      onSelect={noop}
      onDeselect={noop}
      onMove={noop}
      onDelete={noop}
      onReorder={noop}
    />
  );
  return container.querySelector(".builder-widget-body");
};

describe("both surfaces read the same height", () => {
  test.each(["bar", "line", "pie", "map"])(
    "%s is the same height on the canvas and in the viewer",
    (type) => {
      const widget = w({ type });
      const expected = `${WIDGET_BODY_HEIGHT[type]}px`;

      expect(viewerBody(widget)).toHaveStyle({ height: expected });
      expect(canvasBody(widget)).toHaveStyle({ height: expected });
    }
  );

  test.each(["kpi", "table", "section_title"])(
    "%s stays auto-height on both",
    (type) => {
      const widget = w({ type, config: { text: "Hi" } });
      expect(WIDGET_BODY_HEIGHT[type]).toBeUndefined();
      expect(viewerBody(widget).style.height).toBe("");
      expect(canvasBody(widget).style.height).toBe("");
    }
  );

  test("charts get more room than the mockup's original 300px", () => {
    // The reason for the change: a half-width bar chart with date labels
    // was legible at the canvas's accidental 500px and cramped at 300.
    expect(WIDGET_BODY_HEIGHT.bar).toBeGreaterThan(300);
    expect(WIDGET_BODY_HEIGHT.pie).toBeGreaterThan(320);
  });
});
