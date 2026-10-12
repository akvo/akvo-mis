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

  const withSiteKey = async (run) => {
    const original = window.appConfig;
    // Only the site key: setting baseDomain too would make
    // onBaseDomainHost() false under jsdom's "localhost" host, and the
    // /register route would redirect away before rendering anything.
    window.appConfig = { ...original, turnstileSiteKey: "0xK" };
    try {
      await run();
    } finally {
      window.appConfig = original;
    }
  };

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
    // `message` and `details` are given deliberately different text:
    // a regression that dropped the field mapping and fell back to the
    // toast would show `message` and never the `details` sentence, so
    // asserting on the distinction is what actually exercises the
    // mapping rather than just "something rendered somewhere".
    axios.mockImplementation((reqConfig) => {
      if (reqConfig && reqConfig.url === "register") {
        return Promise.reject({
          response: {
            data: {
              message: "Registration failed",
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
    // That text exists nowhere but `details.subdomain`, so finding it
    // inside the field's own error container -- not merely somewhere
    // on the page -- is what pins it to the field rather than a toast
    // that happens to render into the DOM too.
    expect(
      screen
        .getByText(/reserved for system use/i)
        .closest(".ant-form-item-explain-error")
    ).not.toBeNull();
    // The toast-only message must not appear: that is what fails if
    // the mapping regresses to the old toast fallback.
    expect(screen.queryByText("Registration failed")).toBeNull();
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

  test("renders no captcha when no site key is configured", async () => {
    render(<TestApp entryPoint={"/register"} />);
    // Awaited: the app's first paint is not synchronous, and asserting
    // straight after render() would pass against an empty document
    // whether or not the widget is suppressed.
    await screen.findByPlaceholderText("acme");
    expect(document.querySelector("#turnstile-widget")).toBeNull();
  });

  test("renders the captcha container when a site key is configured", async () => {
    await withSiteKey(async () => {
      render(<TestApp entryPoint={"/register"} />);
      await screen.findByPlaceholderText("acme");
      expect(document.querySelector("#turnstile-widget")).not.toBeNull();
    });
  });

  test("shows a captcha error under the widget", async () => {
    await withSiteKey(async () => {
      // Keyed on the request, not mockRejectedValueOnce: the app makes
      // other calls on mount and a "once" rejection would be spent on
      // whichever of those fired first.
      axios.mockImplementation((reqConfig) => {
        if (reqConfig && reqConfig.url === "register") {
          return Promise.reject({
            response: {
              status: 400,
              data: {
                message: "Registration failed",
                details: {
                  captcha_token: ["Verification failed. Please try again."],
                },
              },
            },
          });
        }
        return Promise.resolve({ status: 200, data: [] });
      });

      render(<TestApp entryPoint={"/register"} />);
      await screen.findByPlaceholderText("you@organisation.org");
      fill({});
      await waitFor(() => {
        expect(
          screen.getByText(/Verification failed. Please try again./i)
        ).toBeInTheDocument();
      });
      // Inside the widget's own Form.Item error container rather than
      // merely somewhere on the page: that is what pins it under the
      // widget instead of in the detached toast.
      expect(
        screen
          .getByText(/Verification failed. Please try again./i)
          .closest(".ant-form-item-explain-error")
      ).not.toBeNull();
      // `message` differs from `details`, so a regression that dropped
      // the captcha mapping and fell back to the toast would show this
      // instead.
      expect(screen.queryByText("Registration failed")).toBeNull();
    });
  });
  test("a throttled sign-up surfaces the retry message", async () => {
    // DRF's throttle body is {detail: "..."} with no `message`, so
    // reading only `message` told a throttled registrant "Registration
    // failed" and nothing about waiting.
    axios.mockImplementation((reqConfig) => {
      if (reqConfig && reqConfig.url === "register") {
        return Promise.reject({
          response: {
            status: 429,
            data: {
              detail:
                "Request was throttled. Expected available in 3600 seconds.",
            },
          },
        });
      }
      return Promise.resolve({ status: 200, data: [] });
    });

    render(<TestApp entryPoint={"/register"} />);
    await screen.findByPlaceholderText("you@organisation.org");
    fill({});
    expect(
      await screen.findByText(/Request was throttled/i)
    ).toBeInTheDocument();
  });
});
