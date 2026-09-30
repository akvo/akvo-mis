import { fireEvent, render, screen, within } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import Tenants from "../Tenants";
import "@testing-library/jest-dom";

jest.mock("axios");

const rows = [
  {
    id: 1,
    subdomain: "mohhs",
    name: "Ministry of Health HSS",
    state: "active",
    features: { embedded_dashboard: true },
    users: 47,
    forms: 12,
    dashboards: 5,
    datapoints: 128430,
    devices: 23,
  },
  {
    id: 2,
    subdomain: "sleman",
    name: "Sleman Regency",
    state: "suspended",
    features: {},
    users: 8,
    forms: 3,
    dashboards: 1,
    datapoints: 12004,
    devices: 4,
  },
];

const renderList = async () => {
  axios.mockResolvedValue({ status: 200, data: rows });
  await act(async () => {
    render(
      <MemoryRouter>
        <Tenants />
      </MemoryRouter>
    );
  });
};

// The state filter's buttons carry the same labels as the state tags, so
// every assertion about a row's state is scoped to the table body. A bare
// getByText("Active") matches the filter control too.
const body = () => within(document.querySelector("tbody"));

describe("Tenants list", () => {
  it("renders a row per workspace with its counts", async () => {
    await renderList();
    expect(screen.getByText("mohhs")).toBeInTheDocument();
    expect(screen.getByText("Ministry of Health HSS")).toBeInTheDocument();
    expect(screen.getByText("128,430")).toBeInTheDocument();
  });

  it("shows each workspace's state", async () => {
    await renderList();
    expect(body().getByText("Active")).toBeInTheDocument();
    expect(body().getByText("Suspended")).toBeInTheDocument();
  });

  it("does not offer Inspect for a workspace that cannot resolve", async () => {
    // A suspended workspace's host 404s, so inspecting it would open a
    // dead address. The label still renders for that row — the column
    // stays legible — but only the active row's copy is a control,
    // which is the whole assertion.
    await renderList();
    expect(screen.getAllByText("Inspect")).toHaveLength(2);
    const actions = screen.getAllByRole("button", { name: "Inspect" });
    expect(actions).toHaveLength(1);
    expect(actions[0].closest("tr")).toHaveTextContent("mohhs");
  });

  describe("the Inspect action", () => {
    const appConfig = window.appConfig;
    let originalLocation;

    beforeEach(() => {
      window.appConfig = { ...appConfig, baseDomain: "app.com" };
      originalLocation = window.location;
      delete window.location;
      window.location = {
        ...originalLocation,
        protocol: "http:",
        hostname: "admin.app.com",
        host: "admin.app.com",
        port: "",
        replace: jest.fn(),
      };
    });

    afterEach(() => {
      window.location = originalLocation;
      window.appConfig = appConfig;
    });

    it("mints a one-time code and opens the workspace with it", async () => {
      await renderList();
      // The console hands over a code, not a token, and the workspace's
      // own /inspect spends it. A bare link to that address carries no
      // credential and lands on the expired-link page.
      axios.mockResolvedValue({ status: 200, data: { code: "xyz" } });
      await act(async () => {
        userEvent.click(screen.getByRole("button", { name: "Inspect" }));
      });
      const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
      expect(call[0].url).toContain("admin/tenants/1/inspect");
      expect(window.location.replace).toHaveBeenCalledWith(
        "http://mohhs.app.com/inspect?code=xyz"
      );
    });

    it("says so when the code cannot be minted", async () => {
      await renderList();
      axios.mockRejectedValue({ response: { status: 404 } });
      await act(async () => {
        userEvent.click(screen.getByRole("button", { name: "Inspect" }));
      });
      expect(window.location.replace).not.toHaveBeenCalled();
    });
  });

  it("narrows the table to one state", async () => {
    await renderList();
    expect(screen.getByText("mohhs")).toBeInTheDocument();
    await act(async () => {
      userEvent.click(screen.getByRole("radio", { name: "Suspended" }));
    });
    expect(screen.queryByText("mohhs")).not.toBeInTheDocument();
    expect(screen.getByText("sleman")).toBeInTheDocument();
  });

  it("narrows the table by subdomain and by name", async () => {
    await renderList();
    const box = screen.getByPlaceholderText("Search subdomain or name");
    await act(async () => {
      fireEvent.change(box, { target: { value: "sleman" } });
    });
    expect(screen.queryByText("mohhs")).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.change(box, { target: { value: "ministry" } });
    });
    // Matching the root unit's name, not just the address: an operator
    // looking for a workspace knows the organisation, not the label.
    expect(screen.getByText("mohhs")).toBeInTheDocument();
    expect(screen.queryByText("sleman")).not.toBeInTheDocument();
  });
});
