import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PublicDashboardMenu from "../PublicDashboardMenu";
import dashboardApi from "../../../util/dashboardApi";

jest.mock("../../../util/dashboardApi");

const renderMenu = () =>
  render(
    <MemoryRouter>
      <PublicDashboardMenu />
    </MemoryRouter>
  );

describe("PublicDashboardMenu", () => {
  it("renders nothing when there are no public dashboards", async () => {
    dashboardApi.listPublished.mockResolvedValue({ data: [] });
    const { container } = renderMenu();
    await waitFor(() => {
      expect(dashboardApi.listPublished).toHaveBeenCalled();
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the request fails", async () => {
    dashboardApi.listPublished.mockRejectedValue(new Error("nope"));
    const { container } = renderMenu();
    await waitFor(() => {
      expect(dashboardApi.listPublished).toHaveBeenCalled();
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the trigger when dashboards exist", async () => {
    dashboardApi.listPublished.mockResolvedValue({
      data: [{ id: 1, name: "Water points", slug: "water-points" }],
    });
    renderMenu();
    expect(await screen.findByText(/dashboard/i)).toBeVisible();
  });
});
