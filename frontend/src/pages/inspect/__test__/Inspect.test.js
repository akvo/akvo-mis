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
  beforeEach(() => {
    axios.mockReset();
  });

  it("exchanges the code", async () => {
    axios.mockResolvedValue({ status: 200, data: { subdomain: "acme" } });
    await renderAt("?code=abc");
    const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
    expect(call[0].url).toContain("inspect/exchange");
    expect(call[0].data.code).toBe("abc");
  });

  it("explains a refused code instead of looping", async () => {
    axios.mockRejectedValue({ response: { status: 400 } });
    await renderAt("?code=stale");
    expect(
      screen.getByText(/link has expired|already been used/i)
    ).toBeInTheDocument();
  });

  it("refuses to call anything without a code", async () => {
    await renderAt("");
    expect(axios).not.toHaveBeenCalled();
  });
});
