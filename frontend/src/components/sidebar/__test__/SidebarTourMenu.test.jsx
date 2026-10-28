import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import Sidebar from "../index";
import { store } from "../../../lib";
import { ability as defineAbility, AbilityContext } from "../../can";

describe("Sidebar Tour Menu & Data Attributes", () => {
  beforeEach(() => {
    store.update((s) => {
      s.isLoggedIn = true;
      s.user = { id: 1, email: "admin@akvo.org", is_superuser: true };
      s.tourOpen = false;
      s.tourStep = 0;
      s.tourGoal = null;
    });
  });

  test("renders 'Take a tour' menu item below documentation and clicking it opens the tour in store", () => {
    const testAbility = defineAbility({ is_superuser: true });

    const { container } = render(
      <AbilityContext.Provider value={testAbility}>
        <BrowserRouter>
          <Sidebar />
        </BrowserRouter>
      </AbilityContext.Provider>
    );

    // Verify Documentation exists
    expect(screen.getByText("Documentation")).toBeInTheDocument();

    // Verify Take a tour exists
    const tourMenuItem = screen.getByText(/Take a tour/i);
    expect(tourMenuItem).toBeInTheDocument();

    // Verify data-tour attributes are present in DOM
    expect(
      container.querySelector('[data-tour="sidebar-product-tour"]')
    ).toBeInTheDocument();
    expect(
      container.querySelector('[data-tour="sidebar-documentation"]')
    ).toBeInTheDocument();

    // Click Take a tour inside act
    act(() => {
      fireEvent.click(tourMenuItem);
    });

    // Verify store is updated
    const rawState = store.getRawState();
    expect(rawState.tourOpen).toBe(true);
    expect(rawState.tourStep).toBe(0);
    expect(rawState.tourGoal).toBeNull();
  });
});
