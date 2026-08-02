import { render, screen, fireEvent } from "@testing-library/react";
import axios from "axios";
import TestApp from "../../../TestApp";
import store from "../../../lib/store";
import "@testing-library/jest-dom";

jest.mock("axios");

// Every host answers GET /tenant-info; what it answers is what the app
// uses to decide which of the two contexts it is in.
const servedAs = (tenant) => {
  axios.mockImplementation((cfg) => {
    if (cfg.url === "tenant-info") {
      return Promise.resolve(
        tenant ? { status: 200, data: tenant } : { status: 204, data: "" }
      );
    }
    return Promise.resolve({ status: 200, data: [] });
  });
};

describe("base domain vs workspace address", () => {
  const appConfig = window.appConfig;
  const realLocation = window.location;

  beforeEach(() => {
    window.appConfig = { ...appConfig, baseDomain: "app.com" };
    store.update((s) => {
      s.tenant = null;
      s.tenantLoaded = false;
      s.user = null;
      s.isLoggedIn = false;
    });
  });

  afterEach(() => {
    window.appConfig = appConfig;
    window.location = realLocation;
  });

  test("the main site offers to find a workspace, not to sign in", async () => {
    servedAs(null);
    render(<TestApp entryPoint={"/login"} />);
    expect(
      await screen.findByText(/Go to your workspace/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Welcome back/i)).toBeNull();
  });

  test("entering an address goes to that workspace", async () => {
    servedAs(null);
    delete window.location;
    window.location = {
      ...realLocation,
      protocol: "http:",
      port: "",
      href: "",
    };
    render(<TestApp entryPoint={"/find-workspace"} />);
    fireEvent.change(await screen.findByPlaceholderText("acme"), {
      target: { value: "Acme " },
    });
    fireEvent.click(screen.getByRole("button", { name: /Continue/i }));
    // Trimmed and lower-cased: a host is neither case-sensitive nor
    // tolerant of a stray space pasted in from an email.
    await screen.findByText(/Go to your workspace/i);
    expect(window.location.href).toBe("http://acme.app.com");
  });

  test("a workspace address says whose workspace it is", async () => {
    servedAs({ subdomain: "acme", name: "Kenya", configured: true });
    render(<TestApp entryPoint={"/login"} />);
    expect(await screen.findByTestId("workspace-name")).toHaveTextContent(
      "Kenya"
    );
  });

  test("a single-host deployment signs in at /login as before", async () => {
    // No base domain: tenant-info answers 204 here too, so only
    // appConfig can tell the two apart — and it must, or every
    // single-host install would lose its login page.
    window.appConfig = { ...appConfig };
    servedAs(null);
    render(<TestApp entryPoint={"/login"} />);
    expect(await screen.findByText(/Welcome back/i)).toBeInTheDocument();
    expect(screen.queryByText(/Go to your workspace/i)).toBeNull();
  });
});
