import { render, screen } from "@testing-library/react";
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

  test("renders the registration form fields", () => {
    render(<TestApp entryPoint={"/register"} />);
    expect(screen.getByText(/Create your workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByText(/Subdomain/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Register/i })
    ).toBeInTheDocument();
  });
});
