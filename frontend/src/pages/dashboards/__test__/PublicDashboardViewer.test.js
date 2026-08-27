import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PublicDashboardViewer from "../PublicDashboardViewer";
import dashboardApi from "../../../util/dashboardApi";

jest.mock("../../../util/dashboardApi");
jest.mock("../../../components/dashboard/DashboardViewFilters", () => {
  const MockFilters = () => <div data-testid="filters" />;
  MockFilters.displayName = "DashboardViewFilters";
  return MockFilters;
});
jest.mock("../../../components/dashboard/DashboardGrid", () => {
  const MockGrid = (props) => (
    <div
      data-testid="grid"
      data-widget-count={props.widgets.length}
      data-source={JSON.stringify(props.source)}
    />
  );
  MockGrid.displayName = "DashboardGrid";
  return MockGrid;
});

// =========================================================
// The anonymous viewer (VIZ-010)
// =========================================================
//
// Reachable without an account — that is the whole feature — and rendered
// through the same grid as every other surface, so what the public sees
// cannot quietly diverge from what its author reviewed.

const PAYLOAD = {
  id: 12,
  name: "Water Points Overview",
  slug: "water-points",
  description: "Operational status",
  default_filters: { date: { enabled: true } },
  widgets: [
    { id: 1, type: "kpi", col_span: 6, title: "Sites" },
    { id: 2, type: "bar", col_span: 12, title: "Status" },
  ],
};

const renderViewer = () =>
  render(
    <MemoryRouter initialEntries={["/public/dashboards/water-points"]}>
      <Routes>
        <Route
          path="/public/dashboards/:slug"
          element={<PublicDashboardViewer />}
        />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  jest.clearAllMocks();
});

describe("it reads the public namespace", () => {
  test("it asks for the dashboard without a token", async () => {
    dashboardApi.getPublic.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(dashboardApi.getPublic).toHaveBeenCalled());
    expect(dashboardApi.getPublic).toHaveBeenCalledWith("water-points");
    // Never the authenticated one: that would 401 a visitor who is the
    // entire audience for this page.
    expect(dashboardApi.getPublished).not.toHaveBeenCalled();
  });

  test("its widgets fetch from the public namespace too", async () => {
    dashboardApi.getPublic.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    const grid = await screen.findByTestId("grid");
    expect(grid).toHaveAttribute(
      "data-source",
      JSON.stringify({ slug: "water-points", isPublic: true })
    );
  });

  test("it renders the dashboard's own identity and widgets", async () => {
    dashboardApi.getPublic.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    expect(
      await screen.findByText("Water Points Overview")
    ).toBeInTheDocument();
    expect(screen.getByText("Operational status")).toBeInTheDocument();
    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-widget-count",
      "2"
    );
  });
});

describe("everything it cannot show looks the same", () => {
  test.each([404, 403, 500])(
    "a %s renders one not-found screen",
    async (code) => {
      // Internal, unpublished, deleted, another workspace's, or the wrong
      // host. The client cannot tell them apart and must not guess.
      dashboardApi.getPublic.mockRejectedValue({ response: { status: code } });
      renderViewer();

      await waitFor(() =>
        expect(screen.queryByTestId("grid")).not.toBeInTheDocument()
      );
    }
  );
});
