import { render, screen, waitFor, act } from "@testing-library/react";
import axios from "axios";
import TestApp from "../../../TestApp";
import { store } from "../../../lib";
import "@testing-library/jest-dom";

jest.mock("axios");

// Refreshing a dashboard route must restore the session from the AUTH_TOKEN
// cookie rather than bouncing to the login page — and bouncing is permanent,
// because the login page does not redirect an authenticated visitor back out.
const configuredProfile = {
  email: "founder@acme.org",
  name: "Ada Founder",
  is_superuser: true,
  roles: [],
  forms: [],
  configured: true,
  last_login: 1785439099,
  administration: { id: 3, name: "Jawa Tengah", level: 0 },
};

const setCookies = (pairs) => {
  Object.entries(pairs).forEach(([k, v]) => {
    document.cookie = `${k}=${v}; path=/`;
  });
};

const clearCookies = () => {
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0].trim();
    document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`;
  });
};

describe("Session restore on refresh", () => {
  // setupTests enables the landing page, which makes App treat "/" — the only
  // path jsdom's window.location ever reports — as public and skip the auth
  // loader entirely. This deployment ships SHOW_LANDING_PAGE=false, so match
  // it, or the harness exercises a path the browser never takes.
  const landing = window.appConfig?.showLandingPage;
  beforeAll(() => {
    window.appConfig = { ...window.appConfig, showLandingPage: false };
  });
  afterAll(() => {
    window.appConfig = { ...window.appConfig, showLandingPage: landing };
  });

  beforeEach(() => {
    clearCookies();
    store.update((s) => {
      s.user = null;
      s.isLoggedIn = false;
    });
    axios.mockImplementation(({ url }) => {
      if (url.includes("profile")) {
        return Promise.resolve({ status: 200, data: configuredProfile });
      }
      if (url.includes("administration/")) {
        return Promise.resolve({
          status: 200,
          data: { id: 3, name: "Jawa Tengah", children: [] },
        });
      }
      return Promise.resolve({ status: 200, data: [] });
    });
  });

  afterEach(() => {
    clearCookies();
  });

  test("a valid cookie keeps the user on the dashboard", async () => {
    setCookies({ AUTH_TOKEN: "valid.jwt.token" });

    render(<TestApp entryPoint={"/control-center"} />);

    await waitFor(() => {
      expect(store.getRawState().isLoggedIn).toBe(true);
    });
    expect(screen.queryByText(/Recover Password/i)).toBeNull();
  });

  test("a cookie the server sets after mount survives", async () => {
    // Activation and login receive AUTH_TOKEN in a Set-Cookie header, not
    // through react-cookie — so react-cookie's cached snapshot still reports
    // no cookie afterwards. Anything keyed on that snapshot must not conclude
    // the cookie is absent and delete it.
    render(<TestApp entryPoint={"/control-center"} />);
    await waitFor(() => {
      expect(store.getRawState().isLoggedIn).toBe(false);
    });

    document.cookie = "AUTH_TOKEN=server.set.token; path=/";
    // Adopting the session is what re-runs the bootstrap effect.
    await act(async () => {
      store.update((s) => {
        s.isLoggedIn = true;
        s.user = configuredProfile;
      });
    });

    expect(document.cookie).toContain("AUTH_TOKEN=server.set.token");
  });

  test("an unconfigured workspace does not request administration/undefined", async () => {
    // Its profile carries an administration with no id; asking for it 404s
    // and rejects with nobody listening.
    axios.mockImplementation(({ url }) => {
      if (url.includes("profile")) {
        return Promise.resolve({
          status: 200,
          data: { ...configuredProfile, configured: false, administration: {} },
        });
      }
      return Promise.resolve({ status: 200, data: [] });
    });
    setCookies({ AUTH_TOKEN: "valid.jwt.token" });

    render(<TestApp entryPoint={"/control-center"} />);

    await waitFor(() => {
      expect(store.getRawState().isLoggedIn).toBe(true);
    });
    const requested = axios.mock.calls.map(([cfg]) => cfg.url);
    expect(requested.some((u) => u.includes("undefined"))).toBe(false);
  });
});
