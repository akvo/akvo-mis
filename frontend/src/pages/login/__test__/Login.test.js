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
});
