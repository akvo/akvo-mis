import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import UploadAdministrationData from "../UploadAdministrationData";
import { store } from "../../../lib";
import "@testing-library/jest-dom";

jest.mock("axios");

const renderPage = () =>
  render(
    <MemoryRouter>
      <UploadAdministrationData />
    </MemoryRouter>
  );

const setLevels = (levels) => {
  store.update((s) => {
    s.levels = levels;
    s.user = { name: "Tester" };
  });
};

const READY = [
  { id: 1, level: 0, name: "Country" },
  { id: 2, level: 1, name: "Province" },
];

describe("UploadAdministrationData", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setLevels(READY);
  });

  test("blocks uploading until a level below the root exists", async () => {
    setLevels([{ id: 1, level: 0, name: "Country" }]);
    renderPage();

    // The backend refuses this too; the page says so before the file is
    // ever chosen rather than after a round-trip.
    expect(await screen.findByText(/administrative levels/i)).toBeVisible();
    expect(screen.getByText(/Browse/i).closest("button")).toBeDisabled();
  });

  test("blocks uploading when the top level is unnamed", async () => {
    setLevels([
      { id: 1, level: 0, name: "" },
      { id: 2, level: 1, name: "Province" },
    ]);
    renderPage();

    expect(await screen.findByText(/administrative levels/i)).toBeVisible();
  });

  test("allows uploading once the hierarchy is defined", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Browse/i).closest("button")).toBeEnabled();
    });
    expect(screen.queryByText(/administrative levels/i)).toBeNull();
  });

  test("reports success only once the import job is done", async () => {
    axios.mockImplementation(({ url, method }) => {
      if (method === "POST" || url?.includes("bulk-administrations")) {
        return Promise.resolve({ data: { task_id: "task-1" } });
      }
      return Promise.resolve({ data: { status: "done" } });
    });
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Browse/i).closest("button")).toBeEnabled();
    });
    const input = container.querySelector('input[type="file"]');
    const file = new File(["x"], "a.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    Object.defineProperty(input, "files", { value: [file] });
    input.dispatchEvent(new Event("change", { bubbles: true }));

    expect(await screen.findByText(/Successfully Uploaded/i)).toBeVisible();
  });

  test("reports failure when the import job fails", async () => {
    axios.mockImplementation(({ url, method }) => {
      if (method === "POST" || url?.includes("bulk-administrations")) {
        return Promise.resolve({ data: { task_id: "task-1" } });
      }
      return Promise.resolve({ data: { status: "failed" } });
    });
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Browse/i).closest("button")).toBeEnabled();
    });
    const input = container.querySelector('input[type="file"]');
    const file = new File(["x"], "a.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    Object.defineProperty(input, "files", { value: [file] });
    input.dispatchEvent(new Event("change", { bubbles: true }));

    // The old page showed success here: HTTP 200 meant "file received",
    // never "rows imported".
    expect(await screen.findByText(/could not be imported/i)).toBeVisible();
    expect(screen.queryByText(/upload another/i)).toBeInTheDocument();
  });
});
