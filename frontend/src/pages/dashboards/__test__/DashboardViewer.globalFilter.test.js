import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DashboardViewer from "../DashboardViewer";
import dashboardApi from "../../../util/dashboardApi";

jest.mock("../../../util/dashboardApi");
jest.mock("../../../util/dashboardExport");

jest.mock("../../../components/dashboard/DashboardGrid", () => {
  const MockGrid = (props) => (
    <div data-testid="grid" data-filters={JSON.stringify(props.filters)} />
  );
  MockGrid.displayName = "DashboardGrid";
  return MockGrid;
});

// Stands in for the filter bar: each button emits what the real one emits
// when its dropdown closes (VIZ-027 §7 contract). Question 700301 is
// "Is the infrastructure operational?".
jest.mock("../../../components/dashboard/DashboardViewFilters", () => {
  // VIZ-027 D-21: the filter bar emits the TICKED values of each touched
  // question, keyed by form and name (D-20), plus how filters combine.
  const STATUS = "7003:infrastructure_status";
  const MockFilters = ({ value, onChange }) => (
    <div>
      <button
        onClick={() =>
          onChange({
            ...value,
            selections: { [STATUS]: ["operational", "non_operational"] },
          })
        }
      >
        show Operational, then Non-operational
      </button>
      <button
        onClick={() =>
          onChange({
            ...value,
            selections: { [STATUS]: ["non_operational", "operational"] },
          })
        }
      >
        show Non-operational, then Operational
      </button>
      <button
        onClick={() =>
          onChange({
            ...value,
            selections: {
              [STATUS]: ["operational"],
              "7001:water_source": ["rainwater"],
            },
            match: "any",
          })
        }
      >
        two filters, match any
      </button>
      <button onClick={() => onChange({ ...value, match: "any" })}>
        match any, nothing filtered
      </button>
      <button onClick={() => onChange({ ...value, selections: {} })}>
        clear
      </button>
    </div>
  );
  MockFilters.displayName = "DashboardViewFilters";
  return MockFilters;
});

const PAYLOAD = {
  id: 12,
  name: "Water Points",
  slug: "water-points",
  root_form: { id: 7001, name: "Water point registration" },
  default_filters: {
    questions: [
      {
        form: 7003,
        name: "infrastructure_status",
        label: "Is the infrastructure operational?",
        options: [
          { value: "operational", label: "Operational" },
          { value: "non_operational", label: "Non-operational" },
        ],
      },
    ],
  },
  widgets: [{ id: 1, type: "kpi", col_span: 6, title: "Water points" }],
};

// One entry per value, sorted, so the click order never changes the list
// (D-15).
const BOTH = [
  "option_in:7003:infrastructure_status:non_operational",
  "option_in:7003:infrastructure_status:operational",
];

const gridFilters = () =>
  JSON.parse(screen.getByTestId("grid").getAttribute("data-filters"));

const renderViewer = async () => {
  dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
  render(
    <MemoryRouter initialEntries={["/dashboards/water-points"]}>
      <Routes>
        <Route path="/dashboards/:slug" element={<DashboardViewer />} />
      </Routes>
    </MemoryRouter>
  );
  await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
};

test("nothing filtered: the grid gets no global_criteria", async () => {
  await renderViewer();
  expect(gridFilters().global_criteria || null).toBeNull();
});

test("ticked options reach the grid as one sorted list", async () => {
  await renderViewer();
  fireEvent.click(screen.getByText("show Operational, then Non-operational"));
  expect(gridFilters().global_criteria).toEqual(BOTH);
});

test("the same options picked in another order give the same list", async () => {
  // Expect: identical lists, so every widget keeps its cache key.
  await renderViewer();
  fireEvent.click(screen.getByText("show Operational, then Non-operational"));
  expect(gridFilters().global_criteria).toEqual(BOTH);
  fireEvent.click(screen.getByText("show Non-operational, then Operational"));
  expect(gridFilters().global_criteria).toEqual(BOTH);
});

test("clearing the filter removes it again", async () => {
  await renderViewer();
  fireEvent.click(screen.getByText("show Operational, then Non-operational"));
  expect(gridFilters().global_criteria).toEqual(BOTH);
  fireEvent.click(screen.getByText("clear"));
  expect(gridFilters().global_criteria || null).toBeNull();
});

test("match any reaches the grid as global_match, with the filters", async () => {
  await renderViewer();
  fireEvent.click(screen.getByText("two filters, match any"));
  expect(gridFilters().global_criteria).toEqual([
    "option_in:7001:water_source:rainwater",
    "option_in:7003:infrastructure_status:operational",
  ]);
  expect(gridFilters().global_match).toBe("any");
});

test("match any without a filter sends nothing", async () => {
  await renderViewer();
  fireEvent.click(screen.getByText("match any, nothing filtered"));
  expect(gridFilters().global_match || null).toBeNull();
});

test("the viewer's own state never reaches the requests", async () => {
  await renderViewer();
  fireEvent.click(screen.getByText("two filters, match any"));
  expect(gridFilters()).not.toHaveProperty("selections");
  expect(gridFilters()).not.toHaveProperty("match");
});
