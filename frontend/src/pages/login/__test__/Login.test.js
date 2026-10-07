import { render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import TestApp from "../../../TestApp";
import "@testing-library/jest-dom";

jest.mock("axios");

describe("Login and Registration", () => {
  beforeEach(() => {
    // App bootstrap fetches GET /forms/published on mount; give every
    // api call a resolvable default so the unmocked fetch doesn't reject.
    axios.mockResolvedValue({ status: 200, data: [] });
  });

  test("test if the login form exists", () => {
    const { asFragment } = render(<TestApp />);
    userEvent.click(screen.getByText("Log in"), { button: 0 });
    expect(screen.getByText(/Welcome back/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Please enter your account details/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByText(/Recover Password/i)).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot("LoginPage");
  });

  test("test if the registration form exists", async () => {
    const fakeUser = {
      name: "John Doe",
      invite: "abcd",
    };
    axios.mockResolvedValue({ status: 200, data: fakeUser });

    let registrationPage;
    await act(async () => {
      registrationPage = render(<TestApp entryPoint={"/login/abcd"} />);
      expect(screen.getByText(/Invalid/i)).toBeInTheDocument();
    });

    const welcome = screen.getByTestId("welcome-title");
    expect(welcome.textContent).toBe(
      `Welcome to the Test App platform, ${fakeUser.name}`
    );

    expect(screen.getByText(/Confirm Password/i)).toBeInTheDocument();
    expect(screen.getByText(/Set New Password/i)).toBeInTheDocument();
    expect(registrationPage.asFragment()).toMatchSnapshot("RegistrationPage");
  });

  test("a throttled sign-in says so instead of spinning forever", async () => {
    // The per-email and per-IP login limits make 429 reachable on this
    // form. The old catch handled only 401 and 400, so a 429 left
    // setLoading(true) in place with no notification: a permanently
    // disabled button and no explanation.
    axios.mockImplementation((reqConfig) => {
      if (reqConfig && reqConfig.url === "login") {
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

    render(<TestApp entryPoint={"/login"} />);
    const email = await screen.findByPlaceholderText("Email");
    userEvent.type(email, "member@acme.org");
    userEvent.type(screen.getByPlaceholderText("Password"), "wrong-pass");
    // The site header carries its own "Log in" button, so the form's is
    // selected by submit type rather than by label.
    const submit = document.querySelector('button[type="submit"]');
    await act(async () => {
      userEvent.click(submit);
    });

    expect(
      await screen.findByText(/Request was throttled/i)
    ).toBeInTheDocument();
    // Usable again, not stuck in its loading state.
    expect(submit.classList.contains("ant-btn-loading")).toBe(false);
  });
});
