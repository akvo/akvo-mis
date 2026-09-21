import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizScatter from "../widgets/VizScatter";

let lastOption = null;

jest.mock("../widgets/useEChartsOption", () => {
  const RealReact = require("react");
  return (option) => {
    lastOption = option;
    const boxRef = RealReact.useRef(null);
    return { boxRef };
  };
});

const scatterWidget = (config = {}) => ({
  id: 1,
  type: "scatter",
  title: "Depth vs Turbidity",
  config: { ...config },
});

beforeEach(() => {
  lastOption = null;
});

describe("VizScatter widget", () => {
  describe("empty state", () => {
    test("renders empty message when data is empty array", () => {
      render(<VizScatter config={scatterWidget()} data={[]} filters={{}} />);
      expect(screen.getByText("No data available")).toBeInTheDocument();
      expect(lastOption).toBeNull();
    });

    test("renders empty message when data is null", () => {
      render(<VizScatter config={scatterWidget()} data={null} filters={{}} />);
      expect(screen.getByText("No data available")).toBeInTheDocument();
      expect(lastOption).toBeNull();
    });
  });

  describe("Axis labels and options", () => {
    const data = [
      { x: 10, y: 25, name: "Well 1" },
      { x: 20, y: 50, name: "Well 2" },
    ];

    test("renders default axis labels when not specified", () => {
      render(<VizScatter config={scatterWidget()} data={data} filters={{}} />);
      expect(lastOption).not.toBeNull();
      expect(lastOption.xAxis.name).toBe("Number of datapoints");
      expect(lastOption.xAxis.nameLocation).toBe("center");
      expect(lastOption.xAxis.nameGap).toBe(30);
      expect(lastOption.yAxis.name).toBe("Number of datapoints");
      expect(lastOption.yAxis.nameLocation).toBe("center");
      expect(lastOption.yAxis.nameGap).toBe(70);
      expect(lastOption.series[0].data).toEqual([
        [10, 25, "Well 1"],
        [20, 50, "Well 2"],
      ]);
    });

    test("renders custom xAxis and yAxis labels when configured", () => {
      render(
        <VizScatter
          config={scatterWidget({
            x_axis_label: "Well Depth (m)",
            y_axis_label: "Turbidity (NTU)",
          })}
          data={data}
          filters={{}}
        />
      );
      expect(lastOption).not.toBeNull();
      expect(lastOption.xAxis.name).toBe("Well Depth (m)");
      expect(lastOption.yAxis.name).toBe("Turbidity (NTU)");
    });
  });
});
