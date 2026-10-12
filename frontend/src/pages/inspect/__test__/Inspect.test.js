import React from "react";
import { render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import Inspect from "../Inspect";
import "@testing-library/jest-dom";

jest.mock("axios");

const renderAt = async (search) => {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[`/inspect${search}`]}>
        <Inspect />
      </MemoryRouter>
    );
  });
};

describe("Inspect landing", () => {
  let originalLocation;

  beforeEach(() => {
    axios.mockReset();
    // The exchange sets AUTH_TOKEN itself, so the page finishes with a
    // full navigation rather than a router transition -- that is the
    // whole of what it does on success, and it needs stubbing to see.
    originalLocation = window.location;
    delete window.location;
    window.location = { ...originalLocation, replace: jest.fn() };
  });

  afterEach(() => {
    window.location = originalLocation;
  });

  it("exchanges the code", async () => {
    axios.mockResolvedValue({ status: 200, data: { subdomain: "acme" } });
    await renderAt("?code=abc");
    const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
    expect(call[0].url).toContain("inspect/exchange");
    expect(call[0].data.code).toBe("abc");
  });

  it("hands the session to the app on success", async () => {
    axios.mockResolvedValue({ status: 200, data: { subdomain: "acme" } });
    await renderAt("?code=abc");
    expect(window.location.replace).toHaveBeenCalledWith("/control-center");
  });

  it("explains a refused code instead of looping", async () => {
    axios.mockRejectedValue({ response: { status: 400 } });
    await renderAt("?code=stale");
    expect(
      screen.getByText(/link has expired|already been used/i)
    ).toBeInTheDocument();
    // A code is single-use by design, so there is nothing to retry.
    expect(window.location.replace).not.toHaveBeenCalled();
  });

  it("refuses to call anything without a code", async () => {
    await renderAt("");
    expect(axios).not.toHaveBeenCalled();
  });
});
