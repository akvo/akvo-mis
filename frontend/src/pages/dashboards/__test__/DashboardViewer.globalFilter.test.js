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
  const MockFilters = ({ value, onChange }) => (
    <div>
      <button
        onClick={() =>
          onChange({
            ...value,
            exclusions: { 700301: ["operational", "non_operational"] },
          })
        }
      >
        filter out Operational, then Non-operational
      </button>
      <button
        onClick={() =>
          onChange({
            ...value,
            exclusions: { 700301: ["non_operational", "operational"] },
          })
        }
      >
        filter out Non-operational, then Operational
      </button>
      <button onClick={() => onChange({ ...value, exclusions: {} })}>
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
        question: 700301,
        form: 7003,
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
  "option_not_in:700301:non_operational",
  "option_not_in:700301:operational",
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

test("nothing filtered out: the grid gets no global_criteria", async () => {
  await renderViewer();
  expect(gridFilters().global_criteria || null).toBeNull();
});

test("filtered-out options reach the grid as one sorted list", async () => {
  await renderViewer();
  fireEvent.click(
    screen.getByText("filter out Operational, then Non-operational")
  );
  expect(gridFilters().global_criteria).toEqual(BOTH);
});

test("the same options picked in another order give the same list", async () => {
  // Expect: identical lists, so every widget keeps its cache key.
  await renderViewer();
  fireEvent.click(
    screen.getByText("filter out Operational, then Non-operational")
  );
  expect(gridFilters().global_criteria).toEqual(BOTH);
  fireEvent.click(
    screen.getByText("filter out Non-operational, then Operational")
  );
  expect(gridFilters().global_criteria).toEqual(BOTH);
});

test("clearing the filter removes it again", async () => {
  await renderViewer();
  fireEvent.click(
    screen.getByText("filter out Operational, then Non-operational")
  );
  expect(gridFilters().global_criteria).toEqual(BOTH);
  fireEvent.click(screen.getByText("clear"));
  expect(gridFilters().global_criteria || null).toBeNull();
});
