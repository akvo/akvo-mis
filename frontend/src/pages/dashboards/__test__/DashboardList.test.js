import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import DashboardList from "../DashboardList";
import dashboardApi from "../../../util/dashboardApi";
import { AbilityContext } from "../../../components/can";

jest.mock("../../../util/dashboardApi");

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

// =========================================================
// The card's open action
// =========================================================
//
// The card used to be opened by clicking its thumbnail strip — a preview
// of the widget layout drawn from `type` + `col_span`. With the strip gone
// the card needs an explicit way in, or a published dashboard becomes
// unreachable from the list: the footer carries Edit and Delete only, and
// Edit goes to the builder, not the viewer.
//
// A Preview action replaces it: same destination the thumbnail had, but
// stated as a control rather than implied by a clickable picture.

const DASHBOARDS = [
  {
    id: 1,
    name: "Water Points Overview",
    slug: "water-points-overview",
    description: "Operational status",
    status: "published",
    updated: "2026-08-20T10:00:00Z",
    widgets: [
      { id: 1, type: "bar", col_span: 12, color: "#1890ff" },
      { id: 2, type: "kpi", col_span: 6, color: "#64A73B" },
    ],
  },
];

const ability = { can: () => true };

const draw = async (data = DASHBOARDS) => {
  dashboardApi.list.mockResolvedValue({ data });
  const utils = render(
    <MemoryRouter>
      <AbilityContext.Provider value={ability}>
        <DashboardList />
      </AbilityContext.Provider>
    </MemoryRouter>
  );
  await waitFor(() =>
    expect(screen.getByText("Water Points Overview")).toBeInTheDocument()
  );
  return utils;
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe("the thumbnail strip is gone", () => {
  test("no card draws a thumbnail", async () => {
    const { container } = await draw();
    expect(container.querySelector(".dashboard-card-thumb")).toBeNull();
  });
});

describe("a dashboard can still be reached from the list", () => {
  test("the card offers a Preview action", async () => {
    await draw();
    expect(
      screen.getByRole("button", { name: /preview/i })
    ).toBeInTheDocument();
  });

  test("Preview goes to the viewer, not the builder", async () => {
    await draw();
    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    expect(mockNavigate).toHaveBeenCalledWith(
      "/dashboards/water-points-overview"
    );
  });

  test("Edit still goes to the builder", async () => {
    await draw();
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(mockNavigate).toHaveBeenCalledWith(
      "/control-center/dashboard/water-points-overview"
    );
  });
});

describe("visibility is reported as a badge, not a control", () => {
  test("badges each dashboard's visibility", async () => {
    dashboardApi.list.mockResolvedValue({
      data: [
        {
          id: 1,
          name: "Public one",
          slug: "public-one",
          status: "published",
          is_public: true,
          widgets: [],
        },
        {
          id: 2,
          name: "Private one",
          slug: "private-one",
          status: "published",
          is_public: false,
          widgets: [],
        },
      ],
    });
    render(
      <MemoryRouter>
        <AbilityContext.Provider value={ability}>
          <DashboardList />
        </AbilityContext.Provider>
      </MemoryRouter>
    );
    expect(await screen.findByText("Public")).toBeVisible();
    expect(await screen.findByText("Private")).toBeVisible();
  });
});

describe("delete sits in the card's corner, away from the routine actions", () => {
  test("it is not inside the footer's action group", async () => {
    const { container } = await draw();
    const actions = container.querySelector(".dashboard-card-actions");
    expect(actions.querySelector(".dashboard-btn-icon--danger")).toBeNull();
    expect(container.querySelector(".dashboard-card-delete")).not.toBeNull();
  });

  test("it still deletes, and asks first", async () => {
    await draw();
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    // Ant's Modal.confirm renders into the body, not the card.
    await waitFor(() =>
      expect(document.querySelector(".ant-modal-confirm")).not.toBeNull()
    );
    expect(dashboardApi.destroy).not.toHaveBeenCalled();
  });
});

describe("DashboardList with an embedded dashboard", () => {
  const EMBED = {
    id: 31,
    name: "Regional Sales",
    slug: "regional-sales",
    kind: "embed",
    root_form: null,
    status: "published",
    is_public: true,
    widgets: [],
    description: "Sales by region",
    created: "2026-09-01T10:00:00Z",
    updated: "2026-09-02T10:00:00Z",
  };

  it("badges it as external instead of counting widgets", async () => {
    dashboardApi.list.mockResolvedValue({ data: [EMBED] });
    render(
      <MemoryRouter>
        <AbilityContext.Provider value={ability}>
          <DashboardList />
        </AbilityContext.Provider>
      </MemoryRouter>
    );
    await screen.findByText("Regional Sales");
    expect(screen.getByText("External")).toBeInTheDocument();
    // "0 widgets" would be true and useless.
    expect(screen.queryByText(/0 widgets/)).not.toBeInTheDocument();
  });
});
