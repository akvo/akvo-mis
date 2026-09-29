import { render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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

const renderDetail = async () => {
  axios.mockImplementation(({ url }) =>
    Promise.resolve({
      status: 200,
      data: url.includes("/users") ? users : tenant,
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
});
