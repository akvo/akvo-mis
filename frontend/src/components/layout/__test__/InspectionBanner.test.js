import React from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CookiesProvider } from "react-cookie";
import axios from "axios";
import InspectionBanner from "../InspectionBanner";
import { store } from "../../../lib";
import "@testing-library/jest-dom";

jest.mock("axios");

// A token whose only claim that matters here is `exp`. The banner reads
// the end time out of the cookie, so an assertion about it has to put a
// real one there.
const tokenExpiringAt = (date) => {
  const payload = btoa(JSON.stringify({ exp: Math.floor(date / 1000) }));
  return `header.${payload}.signature`;
};

const renderBanner = () =>
  render(
    <CookiesProvider>
      <InspectionBanner />
    </CookiesProvider>
  );

// Seeds the session the banner only renders for.
const inspecting = (subdomain = "acme") => {
  store.update((s) => {
    s.user = { id: 9, is_inspecting: true };
    s.tenant = { subdomain };
  });
};

describe("InspectionBanner", () => {
  const appConfig = window.appConfig;
  let originalLocation;

  beforeEach(() => {
    document.cookie = "AUTH_TOKEN=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    store.update((s) => {
      s.user = null;
      s.tenant = null;
    });
    window.appConfig = { ...appConfig, baseDomain: "app.com" };
    // Switching is a navigation to another origin, so the component
    // calls location.replace rather than the router.
    originalLocation = window.location;
    delete window.location;
    window.location = {
      ...originalLocation,
      protocol: "http:",
      hostname: "acme.app.com",
      host: "acme.app.com",
      port: "",
      replace: jest.fn(),
    };
    axios.mockReset();
  });

  afterEach(() => {
    window.location = originalLocation;
    window.appConfig = appConfig;
  });

  it("renders nothing for an ordinary session", () => {
    store.update((s) => {
      s.user = { id: 1, is_superuser: true };
      s.tenant = { subdomain: "acme" };
    });
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it("names the workspace and says the session is read only", () => {
    store.update((s) => {
      s.user = { id: 2, is_inspecting: true };
      s.tenant = { subdomain: "acme" };
    });
    renderBanner();
    expect(screen.getByText("acme")).toBeInTheDocument();
    expect(screen.getByText(/read only/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /exit inspection/i })
    ).toBeInTheDocument();
  });

  it("says when the session ends", () => {
    const ends = new Date();
    ends.setHours(14, 30, 0, 0);
    document.cookie = `AUTH_TOKEN=${tokenExpiringAt(ends.getTime())}`;
    store.update((s) => {
      s.user = { id: 3, is_inspecting: true };
      s.tenant = { subdomain: "acme" };
    });
    renderBanner();
    const expected = ends.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    expect(
      screen.getByText(new RegExp(`ends ${expected}`))
    ).toBeInTheDocument();
  });

  it("survives a token it cannot read", () => {
    document.cookie = "AUTH_TOKEN=not-a-jwt";
    store.update((s) => {
      s.user = { id: 4, is_inspecting: true };
      s.tenant = { subdomain: "acme" };
    });
    renderBanner();
    expect(screen.getByText(/read only/i)).toBeInTheDocument();
    expect(screen.queryByText(/ends/i)).not.toBeInTheDocument();
  });
});

describe("InspectionBanner workspace switcher", () => {
  const appConfig = window.appConfig;
  let originalLocation;

  beforeEach(() => {
    window.appConfig = { ...appConfig, baseDomain: "app.com" };
    originalLocation = window.location;
    delete window.location;
    window.location = {
      ...originalLocation,
      protocol: "http:",
      hostname: "acme.app.com",
      host: "acme.app.com",
      port: "",
      replace: jest.fn(),
    };
    axios.mockReset();
    inspecting("acme");
  });

  afterEach(() => {
    window.location = originalLocation;
    window.appConfig = appConfig;
  });

  const open = async () => {
    render(
      <CookiesProvider>
        <InspectionBanner />
      </CookiesProvider>
    );
    await act(async () => {
      userEvent.click(
        screen.getByRole("button", { name: /switch workspace/i })
      );
    });
  };

  it("lists switchable workspaces and excludes the current one", async () => {
    axios.mockResolvedValue({
      status: 200,
      data: [
        { id: 1, subdomain: "acme", name: "Acme" },
        { id: 2, subdomain: "beta", name: "Beta" },
      ],
    });
    await open();
    await waitFor(() => {
      expect(screen.getByRole("menu")).toBeInTheDocument();
    });
    const menu = within(screen.getByRole("menu"));
    expect(menu.getByText("beta")).toBeInTheDocument();
    // The workspace already open is not somewhere to switch to. Scoped
    // to the menu: the banner's own label says "acme" too, so an
    // unscoped query would pass on the wrong element.
    expect(menu.queryByText("acme")).not.toBeInTheDocument();
  });

  it("fetches the list only when the dropdown is opened", async () => {
    axios.mockResolvedValue({ status: 200, data: [] });
    render(
      <CookiesProvider>
        <InspectionBanner />
      </CookiesProvider>
    );
    expect(axios).not.toHaveBeenCalled();
  });

  it("navigates to the chosen workspace", async () => {
    axios.mockImplementation((conf) =>
      conf.method === "POST"
        ? Promise.resolve({
            status: 200,
            data: { code: "xyz", subdomain: "beta" },
          })
        : Promise.resolve({
            status: 200,
            data: [{ id: 2, subdomain: "beta", name: "Beta" }],
          })
    );
    await open();
    await waitFor(() => {
      expect(screen.getByText("beta")).toBeInTheDocument();
    });
    await act(async () => {
      userEvent.click(screen.getByText("beta"));
    });
    await waitFor(() => {
      expect(window.location.replace).toHaveBeenCalledWith(
        "http://beta.app.com/inspect?code=xyz"
      );
    });
  });
});
