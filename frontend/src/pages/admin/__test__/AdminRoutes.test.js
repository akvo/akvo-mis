import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import TestApp from "../../../TestApp";
import store from "../../../lib/store";
import "@testing-library/jest-dom";

jest.mock("axios");

// Booted through the real App rather than a stand-in tree: the thing
// under test is which paths RouteList answers on the console host and
// what its guard does, and a hand-written copy of that tree would agree
// with itself no matter what App actually serves.
const onConsole = async (entryPoint) => {
  await act(async () => {
    render(<TestApp entryPoint={entryPoint} />);
  });
};

describe("the console host", () => {
  const appConfig = window.appConfig;
  const location = window.location;

  beforeEach(() => {
    window.appConfig = { ...appConfig, baseDomain: "app.com" };
    delete window.location;
    window.location = { ...location, hostname: "admin.app.com" };
    // Nothing is signed in and no workspace resolves here; both are the
    // normal state of this host.
    axios.mockRejectedValue({ response: { status: 401 } });
    store.update((s) => {
      s.user = null;
      s.isLoggedIn = false;
      s.tenant = null;
      s.tenantMissing = false;
    });
  });

  afterEach(() => {
    window.appConfig = appConfig;
    window.location = location;
    store.update((s) => {
      s.user = null;
      s.isLoggedIn = false;
    });
  });

  it("serves the activation page an invited operator is sent to", async () => {
    // MT-021 mails an operator `admin.<domain>/activate/<token>`. Without
    // this route the catch-all sends them to the console, the guard
    // sends them to /login, and they cannot sign in — an invited
    // account is inactive with an unusable password until this page
    // runs. The invite button would be a button that cannot work.
    //
    // The token here is not a real one — the backend answers 400 and
    // the page says so. That message is proof the route resolved to
    // Activate rather than to the catch-all.
    axios.mockRejectedValue({ response: { status: 400 } });
    await onConsole("/activate/some-token");
    expect(screen.getByText(/this link has expired/i)).toBeInTheDocument();
  });

  // Whether a pre-authentication path is served or swallowed by the
  // catch-all is invisible while signed out: both end up rendering the
  // login page. With an operator session the two diverge — the
  // catch-all reaches the console, a real route does not — and an
  // operator following a reset link while already signed in is an
  // ordinary thing to do.
  it.each(["/forgot-password", "/login/some-token", "/activate/some-token"])(
    "does not swallow %s into the console",
    async (path) => {
      store.update((s) => {
        s.user = { id: 1, email: "ops@akvo.org", is_platform_admin: true };
        s.isLoggedIn = true;
      });
      await onConsole(path);
      expect(screen.queryByText("Platform Console")).not.toBeInTheDocument();
    }
  );

  it("does not warn an operator about form assignments", async () => {
    // The workspace app tells a user with no assigned forms to contact
    // their administrator. An operator has no forms by construction and
    // is not a superuser, so without an exemption every console sign-in
    // ends with a warning about a workspace concept the console does
    // not have — and there is no administrator above them to contact.
    axios.mockImplementation(({ url }) =>
      url === "login"
        ? Promise.resolve({
            status: 200,
            data: {
              id: 1,
              email: "ops@akvo.org",
              is_platform_admin: true,
              is_superuser: false,
              forms: [],
              token: "t",
            },
          })
        : Promise.resolve({ status: 200, data: [] })
    );
    await onConsole("/login");
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText("Email"), {
        target: { value: "ops@akvo.org" },
      });
      fireEvent.change(screen.getByPlaceholderText("Password"), {
        target: { value: "Console#Pass123" },
      });
    });
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /log in/i }));
    });
    expect(screen.queryByText(/form assignment/i)).not.toBeInTheDocument();
  });

  it("sends a session-less visitor on /admin to the login page", async () => {
    await onConsole("/admin/tenants");
    expect(screen.getByText("Log in")).toBeInTheDocument();
  });

  it("shows the console to an operator", async () => {
    store.update((s) => {
      s.user = { id: 1, email: "ops@akvo.org", is_platform_admin: true };
      s.isLoggedIn = true;
    });
    await onConsole("/admin/tenants");
    expect(screen.getByText("Platform Console")).toBeInTheDocument();
    expect(screen.getByText("ops@akvo.org")).toBeInTheDocument();
  });

  it("keeps a workspace user out of the console", async () => {
    // is_platform_admin is the only thing separating these two, which
    // is why the guard reads it and not is_superuser.
    store.update((s) => {
      s.user = { id: 2, email: "admin@acme.org", is_superuser: true };
      s.isLoggedIn = true;
    });
    await onConsole("/admin/tenants");
    expect(screen.queryByText("Platform Console")).not.toBeInTheDocument();
    expect(screen.getByText("Log in")).toBeInTheDocument();
  });
});
