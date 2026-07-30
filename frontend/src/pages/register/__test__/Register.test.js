import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import axios from "axios";
import TestApp from "../../../TestApp";
import "@testing-library/jest-dom";

jest.mock("axios");

describe("Register", () => {
  beforeEach(() => {
    // App bootstrap fetches GET /forms/published on mount; give every
    // api call a resolvable default so the unmocked fetch doesn't reject.
    axios.mockResolvedValue({ status: 200, data: [] });
  });

  test("asks only for what claims a workspace", () => {
    render(<TestApp entryPoint={"/register"} />);
    expect(screen.getByText(/Create your workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByText(/Subdomain/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Register/i })
    ).toBeInTheDocument();
    // The registrant's name moved to the configuration form, which is the
    // first point at which the email is known to be real.
    expect(screen.queryByText(/First Name/i)).toBeNull();
    expect(screen.queryByText(/Last Name/i)).toBeNull();
  });

  test("ends on a check-your-email state rather than signing in", async () => {
    render(<TestApp entryPoint={"/register"} />);
    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "founder@acme.org" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "Secret#Pass123" },
    });
    fireEvent.change(screen.getByPlaceholderText("your-organisation"), {
      target: { value: "acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Register/i }));

    expect(await screen.findByText(/Check your email/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/founder@acme.org/)).toBeInTheDocument();
    });
  });
});
