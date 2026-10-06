import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import axios from "axios";
import TestApp from "../../../TestApp";
import { store } from "../../../lib";
import "@testing-library/jest-dom";

jest.mock("axios");

// The sign-up form is host-aware, and jsdom is always on "localhost"
// unless told otherwise.
const withHostname = async (hostname, run) => {
  const original = window.location;
  delete window.location;
  window.location = { ...original, hostname, host: hostname };
  try {
    await run();
  } finally {
    window.location = original;
  }
};
describe("Register", () => {
  beforeEach(() => {
    // App bootstrap fetches GET /forms/published on mount; give every
    // api call a resolvable default so the unmocked fetch doesn't reject.
    axios.mockResolvedValue({ status: 200, data: [] });
  });

  const fill = ({
    password = "Secret#Pass123",
    confirm = "Secret#Pass123",
  }) => {
    fireEvent.change(screen.getByPlaceholderText("you@organisation.org"), {
      target: { value: "founder@acme.org" },
    });
    fireEvent.change(screen.getByPlaceholderText("At least 8 characters"), {
      target: { value: password },
    });
    fireEvent.change(screen.getByPlaceholderText("Repeat your password"), {
      target: { value: confirm },
    });
    fireEvent.change(screen.getByPlaceholderText("acme"), {
      target: { value: "acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Create workspace/i }));
  };

  test("asks only for what claims a workspace", () => {
    render(<TestApp entryPoint={"/register"} />);
    expect(screen.getByText(/Create your workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/Workspace address/i)).toBeInTheDocument();
    expect(screen.getByText(/Workspace language/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Create workspace/i })
    ).toBeInTheDocument();
    // The registrant's name moved to the configuration form, which is the
    // first point at which the email is known to be real.
    expect(screen.queryByText(/First name/i)).toBeNull();
    expect(screen.queryByText(/Last name/i)).toBeNull();
  });

  test("submits selected language with registration payload", async () => {
    let postBody = null;
    axios.mockImplementation((reqConfig) => {
      if (reqConfig && reqConfig.url === "register") {
        postBody = reqConfig.data;
        return Promise.resolve({ status: 200, data: {} });
      }
      return Promise.resolve({ status: 200, data: [] });
    });

    render(<TestApp entryPoint={"/register"} />);
    fill({});
    await waitFor(() => {
      expect(screen.getByText(/Check your email/i)).toBeInTheDocument();
    });
    expect(postBody).not.toBeNull();
    expect(postBody.language).toBe("en");
  });

  test("ends on a check-your-email state rather than signing in", async () => {
    render(<TestApp entryPoint={"/register"} />);
    fill({});
    expect(await screen.findByText(/Check your email/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/founder@acme.org/)).toBeInTheDocument();
    });
  });

  test("a mistyped confirmation never reaches the server", async () => {
    render(<TestApp entryPoint={"/register"} />);
    fill({ confirm: "Secret#Pass124" });
    expect(
      await screen.findByText(/The two passwords do not match/i)
    ).toBeInTheDocument();
    // A typo caught after the account exists would need a password reset to
    // recover from, so the request must not go out at all.
    expect(screen.queryByText(/Check your email/i)).toBeNull();
  });
  test("redirects to root when accessed from a tenant subdomain", async () => {
    window.appConfig = { baseDomain: "app.com" };
    store.update((s) => {
      s.tenant = { id: 1, subdomain: "acme" };
      s.tenantLoaded = true;
    });

    await withHostname("acme.app.com", async () => {
      render(<TestApp entryPoint={"/register"} />);
      await waitFor(() => {
        expect(screen.queryByText(/Create your workspace/i)).toBeNull();
      });
    });

    // Cleanup
    delete window.appConfig;
    store.update((s) => {
      s.tenant = null;
      s.tenantLoaded = false;
    });
  });

  test("redirects to root from a workspace that does not exist", async () => {
    // The guard used to be "the lookup found no tenant", which is also
    // the answer on a subdomain nobody owns — so the form rendered there
    // and offered addresses under it.
    window.appConfig = { baseDomain: "app.com" };
    store.update((s) => {
      s.tenant = null;
      s.tenantLoaded = true;
    });

    await withHostname("sleman.app.com", async () => {
      render(<TestApp entryPoint={"/register"} />);
      await waitFor(() => {
        expect(screen.queryByText(/Create your workspace/i)).toBeNull();
      });
    });

    delete window.appConfig;
    store.update((s) => {
      s.tenantLoaded = false;
    });
  });

  test("offers addresses under the main site, not under the current host", async () => {
    window.appConfig = { baseDomain: "app.com" };

    await withHostname("app.com", async () => {
      render(<TestApp entryPoint={"/register"} />);
      expect(await screen.findByText(".app.com")).toBeInTheDocument();
    });

    delete window.appConfig;
  });

  test("prefills the address someone arrived here trying to reach", async () => {
    render(<TestApp entryPoint={"/register?subdomain=sleman"} />);
    expect(await screen.findByPlaceholderText("acme")).toHaveValue("sleman");
  });

  test("shows a field error under the workspace address input", async () => {
    // The API returns {message, details}; `details` is what names the
    // field, and a toast detached from the input is what this
    // replaces.
    axios.mockImplementation((reqConfig) => {
      if (reqConfig && reqConfig.url === "register") {
        return Promise.reject({
          response: {
            data: {
              message: "This name is reserved for system use.",
              details: {
                subdomain: [
                  "This name is reserved for system use. Please choose a different one.",
                ],
              },
            },
          },
        });
      }
      return Promise.resolve({ status: 200, data: [] });
    });

    render(<TestApp entryPoint={"/register"} />);
    // An earlier test in this file leaves the tenant lookup mid-flight
    // in the shared store; wait for the form to actually be there
    // before driving it, same as every other test here that follows
    // one of the redirect tests.
    await screen.findByPlaceholderText("you@organisation.org");
    fill({});
    await waitFor(() => {
      expect(screen.getByText(/reserved for system use/i)).toBeInTheDocument();
    });
    // Still on the form, not on the confirmation screen.
    expect(screen.queryByText(/Check your email/i)).toBeNull();
  });

  test("reports a short name by its length, not by the pattern", async () => {
    // The pattern and the minimum are separate rule objects on
    // purpose: merged into one, antd would report "Use lowercase
    // letters, numbers and hyphens" for a two-character name, which
    // is not what is wrong with it.
    render(<TestApp entryPoint={"/register"} />);
    fireEvent.change(await screen.findByPlaceholderText("acme"), {
      target: { value: "ab" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Create workspace/i }));
    await waitFor(() => {
      expect(screen.getByText(/at least 3 characters/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/no leading or trailing hyphen/i)).toBeNull();
  });
});
