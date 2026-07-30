import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import axios from "axios";
import { store } from "../../../lib";
import Configure from "../Configure";
import "@testing-library/jest-dom";

jest.mock("axios");

// The redirect targets have to exist: <Navigate> with nowhere to land keeps
// re-navigating, which React reports as an exceeded update depth.
const renderConfigure = () =>
  render(
    <MemoryRouter initialEntries={["/configure"]}>
      <Routes>
        <Route path="/configure" element={<Configure />} />
        <Route path="/login" element={<div>login reached</div>} />
        <Route path="/control-center" element={<div>dashboard reached</div>} />
      </Routes>
    </MemoryRouter>
  );

describe("Configure", () => {
  beforeEach(() => {
    axios.mockResolvedValue({ status: 200, data: [] });
  });

  afterEach(() => {
    store.update((s) => {
      s.user = null;
    });
  });

  test("collects the names and explains level versus unit", () => {
    store.update((s) => {
      s.user = { email: "founder@acme.org", configured: false };
    });
    renderConfigure();

    expect(screen.getByText(/Set up your workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/First Name/i)).toBeInTheDocument();
    expect(screen.getByText(/Last Name/i)).toBeInTheDocument();
    // The two hierarchy fields are the ones users conflate, so each carries
    // an example: the tier is "National", the unit at it is "Kenya".
    expect(screen.getByText(/top administrative level/i)).toBeInTheDocument();
    expect(screen.getByText(/top administrative unit/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("National")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Kenya")).toBeInTheDocument();
  });

  test("a configured workspace is sent to the dashboard", () => {
    store.update((s) => {
      s.user = { email: "founder@acme.org", configured: true };
    });
    renderConfigure();
    expect(screen.getByText(/dashboard reached/i)).toBeInTheDocument();
    expect(screen.queryByText(/Set up your workspace/i)).toBeNull();
  });

  test("no session is sent to login", () => {
    renderConfigure();
    expect(screen.getByText(/login reached/i)).toBeInTheDocument();
  });
});
