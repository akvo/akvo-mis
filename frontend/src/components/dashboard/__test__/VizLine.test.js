import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizLine from "../widgets/VizLine";

let lastLineProps = null;
let lastStackLineProps = null;

jest.mock("akvo-charts", () => {
  const RealReact = require("react");
  return {
    Line: RealReact.forwardRef((props, ref) => {
      lastLineProps = props;
      RealReact.useImperativeHandle(ref, () => ({}), []);
      return <div data-testid="line-chart" />;
    }),
    StackLine: RealReact.forwardRef((props, ref) => {
      lastStackLineProps = props;
      RealReact.useImperativeHandle(ref, () => ({}), []);
      return <div data-testid="stack-line-chart" />;
    }),
  };
});

const normalLineWidget = (config = {}) => ({
  id: 1,
  type: "line",
  title: "Water Quality Over Time",
  config: { chart_colors: ["#1890ff", "#64A73B"], ...config },
});

const stackedLineWidget = (config = {}) => ({
  id: 2,
  type: "line",
  title: "Volume by District Over Time",
  config: {
    stack_by: 1002,
    stackMapping: { stack: ["District A", "District B"] },
    chart_colors: ["#1890ff", "#64A73B"],
    ...config,
  },
});

beforeEach(() => {
  lastLineProps = null;
  lastStackLineProps = null;
});

describe("VizLine widget", () => {
  describe("empty state", () => {
    test("renders empty message when data is empty array", () => {
      render(<VizLine config={normalLineWidget()} data={[]} filters={{}} />);
      expect(screen.getByText("No data available")).toBeInTheDocument();
      expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
    });

    test("renders empty message when data is null", () => {
      render(<VizLine config={normalLineWidget()} data={null} filters={{}} />);
      expect(screen.getByText("No data available")).toBeInTheDocument();
    });
  });

  describe("Single Line", () => {
    const data = [
      { label: "2024-01", value: 45 },
      { label: "2024-02", value: 60 },
    ];

    test("renders line chart with default config", () => {
      render(<VizLine config={normalLineWidget()} data={data} filters={{}} />);
      expect(screen.getByTestId("line-chart")).toBeInTheDocument();
      const raw = lastLineProps.rawConfig;
      expect(raw.xAxis.type).toBe("category");
      expect(raw.xAxis.data).toEqual(["2024-01", "2024-02"]);
      expect(raw.yAxis.type).toBe("value");
    });

    test("renders xAxis and yAxis labels when configured", () => {
      render(
        <VizLine
          config={normalLineWidget({
            x_axis_label: "Submission date",
            y_axis_label: "Turbidity (NTU)",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(screen.getByTestId("line-chart")).toBeInTheDocument();
      const raw = lastLineProps.rawConfig;
      expect(raw.xAxis.name).toBe("Submission date");
      expect(raw.xAxis.nameLocation).toBe("center");
      expect(raw.xAxis.nameGap).toBe(30);
      expect(raw.yAxis.name).toBe("Turbidity (NTU)");
      expect(raw.yAxis.nameLocation).toBe("center");
      expect(raw.yAxis.nameGap).toBe(70);
      expect(raw.grid.bottom).toBe(60);
    });
  });

  describe("Stacked Line", () => {
    const stackedData = [
      { label: "2024-01", "District A": 20, "District B": 25 },
      { label: "2024-02", "District A": 30, "District B": 35 },
    ];

    test("renders stacked line chart with axis labels and legend margin", () => {
      render(
        <VizLine
          config={stackedLineWidget({
            x_axis_label: "Month",
            y_axis_label: "Water Volume (L)",
          })}
          data={stackedData}
          filters={{}}
        />
      );
      expect(screen.getByTestId("stack-line-chart")).toBeInTheDocument();
      const raw = lastStackLineProps.rawConfig;
      expect(raw.xAxis.name).toBe("Month");
      expect(raw.xAxis.nameLocation).toBe("center");
      expect(raw.yAxis.name).toBe("Water Volume (L)");
      expect(raw.legend.bottom).toBe(15);
      expect(raw.grid.bottom).toBe(70);
    });
  });
});
