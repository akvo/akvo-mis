import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import Onboarding from "../Onboarding";
import "@testing-library/jest-dom";

jest.mock("axios");

// LP-004: the wizard's step 1 is driven by GET /register/form-library and a new
// step 2 lets the visitor tick starter templates of the chosen category.
const CATEGORIES = {
  categories: [
    {
      id: 4,
      name: "WASH",
      slug: "wash",
      templates: [
        { id: 901, name: "JMP Core WASH Household", monitoring_count: 1 },
        { id: 905, name: "Water Point Mapping", monitoring_count: 0 },
      ],
    },
  ],
};

const renderWizard = () =>
  render(
    <MemoryRouter>
      <Onboarding />
    </MemoryRouter>
  );

// The step indicator renders "Step {n} of {total}" across separate text nodes,
// so read the whole <p>'s normalised text rather than matching one node.
const stepLabel = () => {
  const el = screen.getByText((_, node) => {
    const txt = (node?.textContent || "").replace(/\s+/g, " ").trim();
    return node?.tagName === "P" && /^Step \d+ of \d+$/.test(txt);
  });
  return el.textContent.replace(/\s+/g, " ").trim();
};

describe("Onboarding starter-forms wizard (LP-004)", () => {
  beforeEach(() => {
    axios.mockImplementation((req) => {
      if (req.url === "register/form-library") {
        return Promise.resolve({ status: 200, data: CATEGORIES });
      }
      return Promise.resolve({ status: 200, data: {} });
    });
    try {
      window.localStorage.clear();
    } catch (err) {
      // ignore
    }
  });

  test("step 1 lists the fetched categories plus a skip tile", async () => {
    renderWizard();
    expect(await screen.findByText("WASH")).toBeInTheDocument();
    expect(screen.getByText("Something else / skip")).toBeInTheDocument();
  });

  test("choosing a category shows its templates on step 2, unticked", async () => {
    renderWizard();
    fireEvent.click(await screen.findByText("WASH"));
    fireEvent.click(screen.getByText("Continue"));
    expect(screen.getByText("JMP Core WASH Household")).toBeInTheDocument();
    // monitoring count surfaces as a badge; the one with 0 shows no badge.
    expect(screen.getByText("+1 monitoring")).toBeInTheDocument();
    expect(screen.queryByText(/\+0 monitoring/)).not.toBeInTheDocument();
  });

  test("skip auto-advances past the forms step and renumbers to 6", async () => {
    renderWizard();
    fireEvent.click(await screen.findByText("Something else / skip"));
    // Picking skip means there are no templates to show, so the count drops by
    // one (6, not 7) even before leaving step 1.
    expect(stepLabel()).toBe("Step 1 of 6");
    fireEvent.click(screen.getByText("Continue"));
    // The empty forms step is skipped entirely: we land on the org step, shown
    // as a contiguous "Step 2 of 6" — not "Step 3 of 7" with a phantom step 2,
    // and not the empty-state screen.
    expect(screen.getByText(/organisation called/i)).toBeInTheDocument();
    expect(stepLabel()).toBe("Step 2 of 6");
    expect(
      screen.queryByText(/add forms later from the Form Library/i)
    ).not.toBeInTheDocument();
  });

  test("a category with templates keeps the full 7-step count", async () => {
    renderWizard();
    fireEvent.click(await screen.findByText("WASH"));
    // WASH has templates, so the forms step stays in the count.
    expect(stepLabel()).toBe("Step 1 of 7");
    fireEvent.click(screen.getByText("Continue"));
    expect(screen.getByText("Add starter forms?")).toBeInTheDocument();
    expect(stepLabel()).toBe("Step 2 of 7");
  });

  test("prefills the workspace address from a ?subdomain= query param", async () => {
    // The WorkspaceNotFound "Create this workspace" link lands here with the
    // guessed address; the wizard starts the address step from it (sanitised,
    // lower-cased, winning over any draft).
    window.history.replaceState({}, "", "/?subdomain=Sleman");
    try {
      renderWizard();
      fireEvent.click(await screen.findByText("Something else / skip"));
      fireEvent.click(screen.getByText("Continue")); // -> org
      fireEvent.change(screen.getByRole("textbox"), {
        target: { value: "Acme" },
      });
      fireEvent.click(screen.getByText("Continue")); // -> place
      fireEvent.change(screen.getByRole("textbox"), {
        target: { value: "Kenya" },
      });
      fireEvent.click(screen.getByText("Continue")); // -> address
      expect(screen.getByDisplayValue("sleman")).toBeInTheDocument();
    } finally {
      window.history.replaceState({}, "", "/");
    }
  });

  test("step 1 cannot be skipped without a choice", async () => {
    renderWizard();
    await screen.findByText("WASH");
    fireEvent.click(screen.getByText("Continue"));
    // No tile chosen → still on step 1 with an error, not on step 2.
    expect(screen.getByText("Pick one to continue.")).toBeInTheDocument();
    expect(
      screen.queryByText(/add forms later from the Form Library/i)
    ).not.toBeInTheDocument();
  });

  test("the header shows a Log in link to find-workspace", async () => {
    renderWizard();
    await screen.findByText("WASH");
    expect(screen.getByText("Log in").closest("a")).toHaveAttribute(
      "href",
      "/find-workspace"
    );
  });

  test("the close button starts over in place, clearing the answers", async () => {
    // "/" is the wizard itself, so there is no landing to navigate to on close;
    // the ✕ resets the wizard rather than looping back to the same screen.
    renderWizard();
    fireEvent.click(await screen.findByText("WASH"));
    fireEvent.click(screen.getByText("Continue"));
    expect(screen.getByText("Add starter forms?")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Start over"));
    // Back on a fresh step 1: the chosen category is gone (so the count drops to
    // 6 with the forms step skipped), and the forms screen is no longer shown.
    expect(screen.getByText(/do you want to monitor/i)).toBeInTheDocument();
    expect(screen.queryByText("Add starter forms?")).not.toBeInTheDocument();
    expect(stepLabel()).toBe("Step 1 of 6");
  });
});
