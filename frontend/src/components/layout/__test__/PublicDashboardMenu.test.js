import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("is a menu button whose chevron is not the avatar circle", async () => {
    dashboardApi.listPublished.mockResolvedValue({
      data: [{ id: 1, name: "Water points", slug: "water-points" }],
    });
    renderMenu();
    const trigger = await screen.findByRole("button", { name: /dashboard/i });
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    // `.icon` is the header's circular avatar badge. A direction glyph
    // must not be wearing it.
    expect(trigger.querySelector(".icon")).toBeNull();
    expect(
      trigger.querySelector(".public-dashboard-menu-chevron")
    ).not.toBeNull();
  });

  it("turns the chevron over while the menu is open", async () => {
    dashboardApi.listPublished.mockResolvedValue({
      data: [{ id: 1, name: "Water points", slug: "water-points" }],
    });
    renderMenu();
    const trigger = await screen.findByRole("button", { name: /dashboard/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    // The stylesheet rotates the chevron off aria-expanded, so the
    // attribute is the behaviour worth asserting.
    await waitFor(() => {
      expect(trigger).toHaveAttribute("aria-expanded", "true");
    });
  });
});
