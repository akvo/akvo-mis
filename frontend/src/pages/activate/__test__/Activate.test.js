import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import axios from "axios";
import Activate from "../Activate";
import "@testing-library/jest-dom";

jest.mock("axios");

const renderAt = (token) =>
  render(
    <MemoryRouter initialEntries={[`/activate/${token}`]}>
      <Routes>
        <Route path="/activate/:token" element={<Activate />} />
        <Route path="/configure" element={<div>configure reached</div>} />
      </Routes>
    </MemoryRouter>
  );

describe("Activate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("a good token confirms, then carries the user on", async () => {
    // A whole profile, because adopting the session runs it through
    // reloadData, which reads the assignment fields.
    axios.mockResolvedValue({
      status: 200,
      data: {
        token: "jwt",
        expiration_time: "2030-01-01",
        configured: false,
        email: "founder@acme.org",
        is_superuser: true,
        roles: [],
        forms: [],
      },
    });
    renderAt("good-token");
    // The confirmation is the only moment the registrant is told their
    // address is verified, so it gets a screen before the hand-off.
    expect(await screen.findByText(/Email verified/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Continue to setup/i }));
    expect(await screen.findByText(/configure reached/i)).toBeInTheDocument();
  });

  test("a dead token offers a resend instead of a dead end", async () => {
    axios.mockRejectedValue({ response: { status: 400, data: {} } });
    renderAt("stale-token");
    expect(await screen.findByText(/This link has expired/i)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /Resend activation email/i })
    ).toBeInTheDocument();
  });
});
