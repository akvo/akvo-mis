import React from "react";
import { render } from "@testing-library/react";
import VizPie from "../VizPie";

// akvo-charts draws with ECharts, which splits a pie into equal slices when
// every value is 0 (`stillShowZeroSum`). A filter that leaves nothing must
// draw an empty ring instead, not a pie that looks like data.
let lastRawConfig = null;
jest.mock("akvo-charts", () => {
  const Capture = ({ rawConfig }) => {
    lastRawConfig = rawConfig;
    return null;
  };
  return { Pie: Capture, Doughnut: Capture };
});
jest.mock("../useChartResize", () => () => ({
  chartRef: { current: null },
  boxRef: { current: null },
}));

const draw = (data) => {
  lastRawConfig = null;
  render(<VizPie config={{ config: { variant: "doughnut" } }} data={data} />);
  return lastRawConfig.series[0];
};

test("all values 0 draw an empty ring", () => {
  const series = draw([
    { label: "Villages", value: 0 },
    { label: "School", value: 0 },
  ]);
  expect(series.data).toEqual([]);
  expect(series.showEmptyCircle).toBe(true);
  expect(series.stillShowZeroSum).toBe(false);
});

test("values draw their slices as before", () => {
  const series = draw([
    { label: "Villages", value: 0 },
    { label: "School", value: 1 },
  ]);
  expect(series.data).toEqual([
    { name: "Villages", value: 0 },
    { name: "School", value: 1 },
  ]);
});
