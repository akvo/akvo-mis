import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    expect(screen.getByText("Level 0")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /Add Level/i })).toBeEnabled();
    expect(screen.queryByText(/can no longer be added/i)).toBeNull();
    // Only the deepest tier offers a delete — level 0 never can, since the
    // root unit sits on it.
    const deletes = screen.getAllByRole("button", { name: /Delete/i });
    expect(deletes).toHaveLength(2);
    expect(deletes[0]).toBeDisabled();
    expect(deletes[1]).toBeEnabled();
  });

  test("adding appends a draft row at the next depth", async () => {
    mockLoad(1);
    renderLevels();

    await screen.findByText("National");
    fireEvent.click(screen.getByRole("button", { name: /Add Level/i }));

    // The draft sits in the table at the depth it will occupy, rather than
    // in a separate form.
    expect(screen.getByText("Level 2")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Province, District, Ward/i)
    ).toBeInTheDocument();
    // Nothing to save until it is named.
    expect(screen.getByRole("button", { name: /^Save$/i })).toBeDisabled();
  });

  test("treats a name of only spaces as no name at all", async () => {
    mockLoad(1);
    renderLevels();

    await screen.findByText("National");
    fireEvent.click(screen.getByRole("button", { name: /Add Level/i }));

    const input = screen.getByPlaceholderText(/Province, District, Ward/i);
    const save = screen.getByRole("button", { name: /^Save$/i });

    await userEvent.type(input, "   ");
    // Still disabled: the server trims and would answer 400, so letting the
    // click through would spend a round-trip to say what is already visible.
    expect(save).toBeDisabled();

    await userEvent.type(input, "Ward");
    await waitFor(() => {
      expect(save).toBeEnabled();
    });
  });

  test("freezes add and delete once units exist below root", async () => {
    mockLoad(5);
    renderLevels();

    expect(await screen.findByText(/can no longer be added/i)).toBeVisible();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Add Level/i })).toBeDisabled();
    });
    screen.getAllByRole("button", { name: /Delete/i }).forEach((btn) => {
      expect(btn).toBeDisabled();
    });
    // Rename stays available on every tier.
    expect(screen.getAllByRole("button", { name: /Rename/i })).toHaveLength(2);
  });
});
