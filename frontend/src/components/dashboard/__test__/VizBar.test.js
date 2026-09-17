import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizBar from "../widgets/VizBar";

let lastBarProps = null;
let lastStackBarProps = null;

jest.mock("akvo-charts", () => {
  const RealReact = require("react");
  return {
    Bar: RealReact.forwardRef((props, ref) => {
      lastBarProps = props;
      RealReact.useImperativeHandle(ref, () => ({}), []);
      return <div data-testid="bar-chart" />;
    }),
    StackBar: RealReact.forwardRef((props, ref) => {
      lastStackBarProps = props;
      RealReact.useImperativeHandle(ref, () => ({}), []);
      return <div data-testid="stack-bar-chart" />;
    }),
  };
});

const normalWidget = (config = {}) => ({
  id: 1,
  type: "bar",
  title: "Projects by District",
  config: { chart_colors: ["#1890ff", "#64A73B"], ...config },
});

const stackedWidget = (config = {}) => ({
  id: 2,
  type: "bar",
  title: "Projects by Status and District",
  config: {
    stack_by: 1002,
    stackMapping: { stack: ["Active", "Completed"] },
    chart_colors: ["#1890ff", "#64A73B"],
    ...config,
  },
});

beforeEach(() => {
  lastBarProps = null;
  lastStackBarProps = null;
});

describe("VizBar widget", () => {
  describe("empty state", () => {
    test("renders empty message when data is empty array", () => {
      render(<VizBar config={normalWidget()} data={[]} filters={{}} />);
      expect(screen.getByText("No data available")).toBeInTheDocument();
      expect(screen.queryByTestId("bar-chart")).not.toBeInTheDocument();
    });

    test("renders empty message when data is null", () => {
      render(<VizBar config={normalWidget()} data={null} filters={{}} />);
      expect(screen.getByText("No data available")).toBeInTheDocument();
    });
  });

  describe("Normal Bar (non-stacked)", () => {
    const data = [
      { label: "District A", value: 30 },
      { label: "District B", value: 70 },
    ];

    test("renders number mode on vertical bar without percentage formatting", () => {
      render(
        <VizBar
          config={normalWidget({
            value_type: "number",
            orientation: "vertical",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
      const raw = lastBarProps.rawConfig;
      expect(raw.xAxis.type).toBe("category");
      expect(raw.xAxis.data).toEqual(["District A", "District B"]);
      expect(raw.yAxis.type).toBe("value");
      expect(raw.yAxis.axisLabel).toBeUndefined();
      expect(raw.tooltip.valueFormatter).toBeUndefined();
    });

    test("renders percentage mode on vertical bar with % on yAxis and tooltip", () => {
      render(
        <VizBar
          config={normalWidget({
            value_type: "percentage",
            orientation: "vertical",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
      const raw = lastBarProps.rawConfig;
      expect(raw.xAxis.type).toBe("category");
      expect(raw.yAxis.type).toBe("value");
      expect(raw.yAxis.axisLabel).toEqual({ formatter: "{value}%" });
      expect(raw.tooltip.valueFormatter).toBeDefined();
      expect(raw.tooltip.valueFormatter(50)).toBe("50%");
      expect(raw.tooltip.valueFormatter(null)).toBe("");
    });

    test("renders percentage mode on horizontal bar with % on xAxis and tooltip", () => {
      render(
        <VizBar
          config={normalWidget({
            value_type: "percentage",
            orientation: "horizontal",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
      const raw = lastBarProps.rawConfig;
      expect(raw.xAxis.type).toBe("value");
      expect(raw.xAxis.axisLabel).toEqual({ formatter: "{value}%" });
      expect(raw.yAxis.type).toBe("category");
      expect(raw.yAxis.axisLabel).toBeUndefined();
      expect(raw.tooltip.valueFormatter(75)).toBe("75%");
    });
  });

  describe("Stacked Bar", () => {
    const stackedData = [
      { label: "District A", Active: 40, Completed: 60 },
      { label: "District B", Active: 25, Completed: 75 },
    ];

    test("renders number mode on vertical stacked bar without percentage formatting", () => {
      render(
        <VizBar
          config={stackedWidget({
            value_type: "number",
            orientation: "vertical",
          })}
          data={stackedData}
          filters={{}}
        />
      );
      expect(screen.getByTestId("stack-bar-chart")).toBeInTheDocument();
      const raw = lastStackBarProps.rawConfig;
      expect(raw.xAxis.type).toBe("category");
      expect(raw.xAxis.data).toEqual(["District A", "District B"]);
      expect(raw.yAxis.type).toBe("value");
      expect(raw.yAxis.axisLabel).toBeUndefined();
      expect(raw.tooltip.valueFormatter).toBeUndefined();
      expect(raw.series).toHaveLength(2);
      expect(raw.series[0].stack).toBe("defaultStack");
      expect(raw.series[0].data).toEqual([40, 25]);
      expect(raw.series[1].data).toEqual([60, 75]);
      expect(raw.legend.show).toBe(true);
      expect(raw.legend.data).toEqual(["Active", "Completed"]);
    });

    test("renders percentage mode on vertical stacked bar with % on yAxis and tooltip", () => {
      render(
        <VizBar
          config={stackedWidget({
            value_type: "percentage",
            orientation: "vertical",
          })}
          data={stackedData}
          filters={{}}
        />
      );
      expect(screen.getByTestId("stack-bar-chart")).toBeInTheDocument();
      const raw = lastStackBarProps.rawConfig;
      expect(raw.xAxis.type).toBe("category");
      expect(raw.yAxis.type).toBe("value");
      expect(raw.yAxis.axisLabel).toEqual({ formatter: "{value}%" });
      expect(raw.tooltip.valueFormatter).toBeDefined();
      expect(raw.tooltip.valueFormatter(40)).toBe("40%");
      expect(raw.tooltip.valueFormatter(null)).toBe("");
    });

    test("renders percentage mode on horizontal stacked bar with % on xAxis and tooltip", () => {
      render(
        <VizBar
          config={stackedWidget({
            value_type: "percentage",
            orientation: "horizontal",
          })}
          data={stackedData}
          filters={{}}
        />
      );
      expect(screen.getByTestId("stack-bar-chart")).toBeInTheDocument();
      const raw = lastStackBarProps.rawConfig;
      expect(raw.xAxis.type).toBe("value");
      expect(raw.xAxis.axisLabel).toEqual({ formatter: "{value}%" });
      expect(raw.yAxis.type).toBe("category");
      expect(raw.yAxis.data).toEqual(["District A", "District B"]);
      expect(raw.yAxis.axisLabel).toBeUndefined();
      expect(raw.tooltip.valueFormatter(60)).toBe("60%");
    });
  });

  describe("Axis labels", () => {
    const data = [
      { label: "District A", value: 30 },
      { label: "District B", value: 70 },
    ];

    test("renders xAxis and yAxis names when x_axis_label and y_axis_label provided on vertical bar", () => {
      render(
        <VizBar
          config={normalWidget({
            x_axis_label: "Districts",
            y_axis_label: "Number of submissions",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
      const raw = lastBarProps.rawConfig;
      expect(raw.xAxis.name).toBe("Districts");
      expect(raw.xAxis.nameLocation).toBe("center");
      expect(raw.xAxis.nameGap).toBe(30);
      expect(raw.yAxis.name).toBe("Number of submissions");
      expect(raw.yAxis.nameLocation).toBe("center");
      expect(raw.yAxis.nameGap).toBe(50);
      expect(raw.grid.bottom).toBe(60);
    });

    test("renders xAxis and yAxis names on horizontal bar", () => {
      render(
        <VizBar
          config={normalWidget({
            orientation: "horizontal",
            x_axis_label: "Number of submissions",
            y_axis_label: "Districts",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
      const raw = lastBarProps.rawConfig;
      expect(raw.xAxis.name).toBe("Number of submissions");
      expect(raw.yAxis.name).toBe("Districts");
    });

    test("renders xAxis and yAxis names with adjusted legend bottom on stacked bar", () => {
      const stackedData = [
        { label: "District A", Active: 40, Completed: 60 },
        { label: "District B", Active: 25, Completed: 75 },
      ];
      render(
        <VizBar
          config={stackedWidget({
            x_axis_label: "Districts",
            y_axis_label: "Total Projects",
          })}
          data={stackedData}
          filters={{}}
        />
      );
      expect(screen.getByTestId("stack-bar-chart")).toBeInTheDocument();
      const raw = lastStackBarProps.rawConfig;
      expect(raw.xAxis.name).toBe("Districts");
      expect(raw.yAxis.name).toBe("Total Projects");
      expect(raw.legend.bottom).toBe(15);
      expect(raw.grid.bottom).toBe(70);
    });
  });
});
