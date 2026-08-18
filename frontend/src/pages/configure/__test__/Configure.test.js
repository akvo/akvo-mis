import { render, screen, fireEvent } from "@testing-library/react";
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
        <Route
          path="/control-center/master-data/levels"
          element={<div>levels reached</div>}
        />
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

  test("collects the names and explains tier versus unit", () => {
    store.update((s) => {
      s.user = { email: "founder@acme.org", configured: false };
    });
    renderConfigure();

    expect(screen.getByText(/Set up your project/i)).toBeInTheDocument();
    expect(screen.getByText(/First name/i)).toBeInTheDocument();
    expect(screen.getByText(/Last name/i)).toBeInTheDocument();
    // The two hierarchy fields are the ones users conflate, so each carries
    // an example: the tier is "Country", the unit at it is "Kenya".
    expect(screen.getByText(/Top level name/i)).toBeInTheDocument();
    expect(screen.getByText(/Top unit name/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Country")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Kenya")).toBeInTheDocument();
  });

  test("the preview names the hierarchy as it is typed", () => {
    store.update((s) => {
      s.user = { email: "founder@acme.org", configured: false };
    });
    renderConfigure();

    fireEvent.change(screen.getByPlaceholderText("Country"), {
      target: { value: "National" },
    });
    fireEvent.change(screen.getByPlaceholderText("Kenya"), {
      target: { value: "Uganda" },
    });
    expect(screen.getByText("National")).toBeInTheDocument();
    expect(screen.getByText("Uganda")).toBeInTheDocument();
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

  test("finishing setup leads on to level management", async () => {
    store.update((s) => {
      s.user = { email: "founder@acme.org", configured: false };
    });
    // Saving makes the workspace configured, which is exactly the condition
    // that sends an *arriving* visitor away — it must not throw out the
    // person who just completed the form.
    axios.mockImplementation(({ url }) => {
      if (url.includes("register/configure")) {
        return Promise.resolve({
          status: 200,
          data: { email: "founder@acme.org", configured: true },
        });
      }
      return Promise.resolve({ status: 200, data: [] });
    });
    renderConfigure();

    fireEvent.change(screen.getByPlaceholderText("Jane"), {
      target: { value: "Ada" },
    });
    fireEvent.change(screen.getByPlaceholderText("Doe"), {
      target: { value: "Founder" },
    });
    fireEvent.change(screen.getByPlaceholderText("Country"), {
      target: { value: "National" },
    });
    fireEvent.change(screen.getByPlaceholderText("Kenya"), {
      target: { value: "Uganda" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Finish setup/i }));

    expect(await screen.findByText(/You're all set/i)).toBeInTheDocument();
    expect(screen.queryByText(/dashboard reached/i)).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: /Continue to Level management/i })
    );
    expect(await screen.findByText(/levels reached/i)).toBeInTheDocument();
  });
});
