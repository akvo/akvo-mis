import { render, screen } from "@testing-library/react";
import TestApp from "./TestApp";
import "@testing-library/jest-dom";

describe("App", () => {
  test("test if the login button exists", () => {
    // Root "/" now renders the public landing page (register CTA, no
    // "Log in" link), so enter at /login where the sign-in form lives.
    render(<TestApp entryPoint="/login" />);
    const linkElement = screen.getByText("Log in");
    expect(linkElement).toBeInTheDocument();
  });
});
