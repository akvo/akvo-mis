import { render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Modal } from "antd";
import axios from "axios";
import TenantDetail from "../TenantDetail";
import "@testing-library/jest-dom";

jest.mock("axios");

const tenant = {
  id: 42,
  subdomain: "mohhs",
  name: "Ministry of Health HSS",
  state: "active",
  features: { embedded_dashboard: true },
  users: 47,
  forms: 12,
  dashboards: 5,
  datapoints: 128430,
  devices: 23,
};

const users = [
  {
    id: 7,
    name: "Grace Mensah",
    email: "grace@moh.gov",
    state: "active",
    devices: 0,
    last_login: null,
  },
  {
    id: 8,
    name: "Amina Dauda",
    email: "amina@moh.gov",
    state: "deactivated",
    devices: 3,
    last_login: null,
  },
];

const renderDetail = async (overrides = {}) => {
  axios.mockImplementation(({ url }) =>
    Promise.resolve({
      status: 200,
      data: url.includes("/users") ? users : { ...tenant, ...overrides },
    })
  );
  await act(async () => {
    render(
      <MemoryRouter initialEntries={["/admin/tenants/42"]}>
        <Routes>
          <Route path="/admin/tenants/:id" element={<TenantDetail />} />
        </Routes>
      </MemoryRouter>
    );
  });
};

describe("Tenant detail", () => {
  // Modal.confirm renders into document.body, outside the container
  // Testing Library unmounts, so a dialog opened by one test is still
  // on screen in the next one and every query for a button by name
  // matches twice.
  afterEach(() => {
    Modal.destroyAll();
    document.body.innerHTML = "";
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
      await renderDetail();
      // The same hand-off the list performs: only this host can mint a
      // code, and the workspace's own /inspect spends it. A link would
      // carry no credential.
      axios.mockResolvedValue({ status: 200, data: { code: "xyz" } });
      await act(async () => {
        userEvent.click(screen.getByRole("button", { name: /inspect/i }));
      });
      const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
      expect(call[0].url).toContain("admin/tenants/42/inspect");
      expect(window.location.replace).toHaveBeenCalledWith(
        "http://mohhs.app.com/inspect?code=xyz"
      );
    });

    it("is absent for a workspace whose host cannot resolve", async () => {
      // Suspended and deleted workspaces 404 at their own address, so
      // the button would open a dead page.
      await renderDetail({ state: "suspended" });
      expect(
        screen.queryByRole("button", { name: /inspect/i })
      ).not.toBeInTheDocument();
    });
  });

  it("renders the counts", async () => {
    await renderDetail();
    expect(screen.getByText("128,430")).toBeInTheDocument();
    expect(screen.getByText("mohhs")).toBeInTheDocument();
  });

  it("lists the workspace's users", async () => {
    await renderDetail();
    expect(screen.getByText("grace@moh.gov")).toBeInTheDocument();
    expect(screen.getByText("amina@moh.gov")).toBeInTheDocument();
  });

  it("says how many devices a deactivated user has blocked", async () => {
    // The consequence of deactivating is otherwise invisible, which is
    // the whole reason the action exists.
    await renderDetail();
    expect(screen.getByText(/3 devices blocked/i)).toBeInTheDocument();
  });

  it("writes a feature toggle", async () => {
    await renderDetail();
    axios.mockClear();
    axios.mockResolvedValue({ status: 200, data: tenant });
    await act(async () => {
      userEvent.click(screen.getByRole("switch", { name: /embedded/i }));
    });
    const call = axios.mock.calls.find(([conf]) => conf.method === "PUT");
    expect(call[0].url).toContain("admin/tenants/42/features");
  });

  it("deactivates a user and reloads the row", async () => {
    await renderDetail();
    axios.mockClear();
    axios.mockImplementation(({ url }) =>
      Promise.resolve({
        status: 200,
        data: url.includes("/users") ? users : tenant,
      })
    );
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /deactivate/i }));
    });
    const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
    expect(call[0].url).toBe("admin/users/7/deactivate");
  });

  it("suspends a workspace", async () => {
    await renderDetail();
    axios.mockClear();
    axios.mockResolvedValue({
      status: 200,
      data: { ...tenant, state: "suspended" },
    });
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /suspend/i }));
    });
    const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
    expect(call[0].url).toContain("admin/tenants/42/deactivate");
  });

  it("asks before deleting", async () => {
    // Soft-delete is reversible only from a shell, so the confirmation
    // is the last point a mis-click can be caught.
    await renderDetail();
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    });
    expect(
      await screen.findByText(/address stops resolving/i)
    ).toBeInTheDocument();
  });

  it("does not delete until the confirmation is accepted", async () => {
    // The dialog is the guard. Opening it must not be enough to issue
    // the request, or the guard is decoration.
    await renderDetail();
    axios.mockClear();
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    });
    expect(
      axios.mock.calls.find(([conf]) => conf.method === "DELETE")
    ).toBeUndefined();
  });

  it("keeps the counts on screen after a mutation", async () => {
    // The page assigns each mutation's response straight over the
    // workspace it is displaying, so a reply that omits the counts does
    // not merely omit them — it blanks five tiles that were on screen a
    // moment ago, beside a Delete button.
    await renderDetail();
    axios.mockClear();
    axios.mockResolvedValue({
      status: 200,
      data: { ...tenant, features: { embedded_dashboard: false } },
    });
    await act(async () => {
      userEvent.click(screen.getByRole("switch", { name: /embedded/i }));
    });
    expect(screen.getByText("128,430")).toBeInTheDocument();
  });

  it("offers neither restore nor delete once a workspace is deleted", async () => {
    // Restore only flips is_active, which a deleted workspace ignores —
    // the state stays "deleted", nothing visibly changes and no error
    // is shown. The delete dialog's own copy says restoring is a shell
    // operation, so a Restore button here contradicts it.
    axios.mockImplementation(({ url }) =>
      Promise.resolve({
        status: 200,
        data: url.includes("/users") ? users : { ...tenant, state: "deleted" },
      })
    );
    await act(async () => {
      render(
        <MemoryRouter initialEntries={["/admin/tenants/42"]}>
          <Routes>
            <Route path="/admin/tenants/:id" element={<TenantDetail />} />
          </Routes>
        </MemoryRouter>
      );
    });
    expect(
      screen.queryByRole("button", { name: /restore/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^delete$/i })
    ).not.toBeInTheDocument();
  });

  it("opens the rename dialog on its impact preflight", async () => {
    await renderDetail();
    axios.mockClear();
    axios.mockResolvedValue({
      status: 200,
      data: { published_dashboards: 3, public_dashboards: 1 },
    });
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /^rename$/i }));
    });
    expect(
      axios.mock.calls.some(([conf]) =>
        conf.url.includes("admin/tenants/42/rename-impact")
      )
    ).toBe(true);
    expect(await screen.findByText(/3 dashboard links/)).toBeInTheDocument();
  });

  it("displays tenant logo and operator controls", async () => {
    await renderDetail({ logo: "/images/custom-logo.png" });
    const logoImg = screen.getByAltText(/Ministry of Health HSS Logo/i);
    expect(logoImg).toBeInTheDocument();
    expect(logoImg).toHaveAttribute("src", "/images/custom-logo.png");
    expect(screen.getByText(/upload logo/i)).toBeInTheDocument();
    expect(screen.getByText(/remove logo/i)).toBeInTheDocument();
  });
});
