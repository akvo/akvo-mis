import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import Levels from "../Levels";
import "@testing-library/jest-dom";

jest.mock("axios");

// The screen renders the server's list as-is; its only local logic is the
// freeze gate — derived from the administration count — and picking the
// deepest row as the only deletable one. Those are what is asserted here.
const renderLevels = () => {
  return render(
    <MemoryRouter>
      <Levels />
    </MemoryRouter>
  );
};

const mockLoad = (unitCount) => {
  axios.mockImplementation(({ url }) => {
    if (url.startsWith("administrations")) {
      return Promise.resolve({ data: { total: unitCount } });
    }
    return Promise.resolve({
      data: [
        { id: 1, name: "National", level: 0 },
        { id: 2, name: "Province", level: 1 },
      ],
    });
  });
};

describe("Levels management", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("lists the tenant's tiers and allows adding when only root exists", async () => {
    mockLoad(1);
    renderLevels();

    expect(await screen.findByText("National")).toBeInTheDocument();
    expect(screen.getByText("Province")).toBeInTheDocument();

    const add = screen.getByRole("button", { name: /Add Level/i });
    // Disabled until a name is typed, but not frozen.
    expect(screen.getByPlaceholderText(/New level name/i)).toBeEnabled();
    expect(add).toBeInTheDocument();
    expect(screen.queryByText(/can no longer be added/i)).toBeNull();
    // Only the deepest tier offers a delete.
    expect(screen.getAllByRole("button", { name: /Delete/i })).toHaveLength(1);
  });

  test("freezes add and delete once units exist below root", async () => {
    mockLoad(5);
    renderLevels();

    expect(await screen.findByText(/can no longer be added/i)).toBeVisible();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/New level name/i)).toBeDisabled();
    });
    expect(screen.getByRole("button", { name: /Delete/i })).toBeDisabled();
    // Rename stays available on every tier.
    expect(screen.getAllByRole("button", { name: /Edit/i })).toHaveLength(2);
  });
});
