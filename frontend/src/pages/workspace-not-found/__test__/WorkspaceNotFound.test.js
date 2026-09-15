import { render, screen } from "@testing-library/react";
import axios from "axios";
import TestApp from "../../../TestApp";
import store from "../../../lib/store";
import "@testing-library/jest-dom";

jest.mock("axios");

// A host the deployment does not serve: the tenant middleware answers 404
// to everything on it, tenant-info included, and that 404 is the only
// thing that distinguishes this from the base domain.
const servedAsNothing = () => {
  axios.mockImplementation((cfg) => {
    if (cfg.url === "tenant-info") {
      return Promise.reject({ response: { status: 404 } });
    }
    return Promise.resolve({ status: 200, data: [] });
  });
};

const withHostname = async (hostname, run) => {
  const original = window.location;
  delete window.location;
  window.location = {
    ...original,
    hostname,
    host: hostname,
    protocol: "https:",
    port: "",
  };
  try {
    await run();
  } finally {
    window.location = original;
  }
};

describe("WorkspaceNotFound", () => {
  const appConfig = window.appConfig;

  beforeEach(() => {
    servedAsNothing();
    window.appConfig = { ...appConfig, baseDomain: "app.com" };
    store.update((s) => {
      s.tenant = null;
      s.tenantMissing = false;
      s.tenantLoaded = false;
      s.user = null;
      s.isLoggedIn = false;
    });
  });

  afterEach(() => {
    window.appConfig = appConfig;
  });

  test("names the address that does not exist", async () => {
    await withHostname("sleman.app.com", async () => {
      render(<TestApp entryPoint={"/login"} />);
      expect(await screen.findByText(/No workspace here/i)).toBeInTheDocument();
      expect(screen.getByText("sleman.app.com")).toBeInTheDocument();
    });
  });

  test("replaces the app rather than sitting on one route", async () => {
    // Every call from this host is refused by the same 404, so there is
    // no route worth rendering — not the login form it used to show.
    await withHostname("sleman.app.com", async () => {
      render(<TestApp entryPoint={"/control-center"} />);
      expect(await screen.findByText(/No workspace here/i)).toBeInTheDocument();
    });
  });

  test("both ways out lead back to the main site", async () => {
    await withHostname("sleman.app.com", async () => {
      render(<TestApp entryPoint={"/login"} />);
      expect(
        await screen.findByRole("link", { name: /Try another address/i })
      ).toHaveAttribute("href", "https://app.com/find-workspace");
      // Carrying the name over means the guess someone already made is
      // the one the sign-up form starts from.
      expect(
        screen.getByRole("link", { name: /Create this workspace/i })
      ).toHaveAttribute("href", "https://app.com/register?subdomain=sleman");
    });
  });
});
