import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import OnboardingTour, { getStorageKey } from "../OnboardingTour";
import { store } from "../../../lib";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

describe("OnboardingTour Component", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    store.update((s) => {
      s.isLoggedIn = true;
      s.user = {
        id: 42,
        email: "admin@akvo.org",
        is_superuser: true,
        roles: [{ role: "Admin", can_form_builder: true }],
      };
      s.tenant = { subdomain: "test-workspace" };
      s.tourOpen = false;
      s.tourGoal = null;
      s.tourStep = 0;
      s.language = { active: "en" };
    });
  });

  afterEach(() => {
    document.querySelectorAll("[data-tour]").forEach((el) => el.remove());
  });

  test("renders nothing when tourOpen is false", () => {
    const { container } = render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );
    expect(container.firstChild).toBeNull();
  });

  test("renders Step 1 Welcome & Goal Picker modal for Admin with recommended setup goal", () => {
    store.update((s) => {
      s.tourOpen = true;
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(screen.getByText("Welcome to Akvo MIS")).toBeInTheDocument();
    expect(screen.getByText(/STEP 1 OF 5/i)).toBeInTheDocument();
    expect(screen.getByText("Set up a data collection")).toBeInTheDocument();
    expect(screen.getByText("Review and approve data")).toBeInTheDocument();
    expect(screen.getByText("Explore data and dashboards")).toBeInTheDocument();
    expect(screen.getByText("Recommended")).toBeInTheDocument();

    // Verify Show me how & Skip buttons
    expect(screen.getByText("Show me how")).toBeInTheDocument();
    expect(screen.getByText("Skip")).toBeInTheDocument();
  });

  test("switches selected goal when clicking another radio card", () => {
    store.update((s) => {
      s.tourOpen = true;
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    // Initial state is Setup (5 steps)
    expect(screen.getByText(/STEP 1 OF 5/i)).toBeInTheDocument();

    // Click Review and approve data (4 steps)
    fireEvent.click(screen.getByText("Review and approve data"));
    expect(screen.getByText(/STEP 1 OF 4/i)).toBeInTheDocument();
  });

  test("clicking Skip dismisses tour and sets localStorage flag", () => {
    store.update((s) => {
      s.tourOpen = true;
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    const skipBtn = screen.getByText("Skip");
    act(() => {
      fireEvent.click(skipBtn);
    });

    expect(store.getRawState().tourOpen).toBe(false);
    expect(
      localStorage.getItem("akvo_mis_tour_completed_42_test-workspace")
    ).toBe("true");
  });

  test("clicking close button [X] on Step 1 dismisses tour", () => {
    store.update((s) => {
      s.tourOpen = true;
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    const closeBtn = screen.getByRole("button", { name: /Close/i });
    act(() => {
      fireEvent.click(closeBtn);
    });

    expect(store.getRawState().tourOpen).toBe(false);
  });

  test("renders single-goal mode for Data Viewer role without other choice cards", () => {
    store.update((s) => {
      s.user = {
        id: 99,
        email: "viewer@akvo.org",
        roles: [{ role: "Viewer" }],
      };
      s.tourOpen = true;
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(screen.getByText("Welcome to Akvo MIS")).toBeInTheDocument();
    expect(screen.getByText("Explore data and dashboards")).toBeInTheDocument();
    expect(
      screen.queryByText("Set up a data collection")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Review and approve data")
    ).not.toBeInTheDocument();
  });

  test("advances from Step 1 to Step 2 when clicking 'Show me how' and navigates to /control-center if on another page", () => {
    store.update((s) => {
      s.tourOpen = true;
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    const showMeBtn = screen.getByText("Show me how");
    act(() => {
      fireEvent.click(showMeBtn);
    });

    expect(mockNavigate).toHaveBeenCalledWith("/control-center");
    // Step 2 in Path A (Setup): "Build a form"
    expect(screen.getByText(/STEP 2 OF 5/i)).toBeInTheDocument();
    expect(screen.getByText("Build a form")).toBeInTheDocument();
    expect(screen.getByText("Next")).toBeInTheDocument();
    expect(screen.getByText("Back")).toBeInTheDocument();
  });

  test("navigates backward and forward across tour steps", () => {
    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "setup";
      s.tourStep = 1; // Step 2 (Build a form)
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(screen.getByText("Build a form")).toBeInTheDocument();

    // Click Next -> Step 3 (Get the app to your field team)
    act(() => {
      fireEvent.click(screen.getByText("Next"));
    });
    expect(
      screen.getByText("Get the app to your field team")
    ).toBeInTheDocument();

    // Click Back -> Step 2 (Build a form)
    act(() => {
      fireEvent.click(screen.getByText("Back"));
    });
    expect(screen.getByText("Build a form")).toBeInTheDocument();
  });

  test("spotlights target element when found in DOM and listens to resize/scroll", () => {
    const dummyTarget = document.createElement("div");
    dummyTarget.setAttribute("data-tour", "sidebar-form-builder");
    dummyTarget.getBoundingClientRect = () => ({
      top: 100,
      left: 20,
      width: 180,
      height: 40,
      right: 200,
      bottom: 140,
    });
    document.body.appendChild(dummyTarget);

    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "setup";
      s.tourStep = 1; // Step 2 targets [data-tour="sidebar-form-builder"]
    });

    const { container } = render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(
      container.querySelector(".onboarding-tour-spotlight-hole")
    ).toBeInTheDocument();

    // Fire resize & scroll
    act(() => {
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("scroll"));
    });

    // Clicking spotlight backdrop dismisses tour
    const backdrop = container.querySelector(".onboarding-tour-backdrop");
    act(() => {
      fireEvent.click(backdrop);
    });
    expect(store.getRawState().tourOpen).toBe(false);
  });

  test("handles 'Copy app link' action via navigator.clipboard", async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockImplementation(() => Promise.resolve()),
      },
    });

    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "setup";
      s.tourStep = 2; // Step 3
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    const copyBtn = screen.getByText("Copy app link");
    expect(copyBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      `${window.location.origin}/app`
    );
  });

  test("handles 'Copy app link' action fallback when clipboard API is unavailable or rejects", async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: jest
          .fn()
          .mockImplementation(() => Promise.reject(new Error("denied"))),
      },
    });
    document.execCommand = jest.fn().mockReturnValue(true);

    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "setup";
      s.tourStep = 2; // Step 3
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    const copyBtn = screen.getByText("Copy app link");
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(document.execCommand).toHaveBeenCalledWith("copy");
  });

  test("handles final step primary CTA navigation and dismissal for Path A", () => {
    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "setup";
      s.tourStep = 4; // Final step (Step 5 of 5)
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(screen.getByText(/STEP 5 OF 5/i)).toBeInTheDocument();
    expect(screen.getByText("Get help any time")).toBeInTheDocument();

    const ctaBtn = screen.getByText("Create your first form");
    expect(ctaBtn).toBeInTheDocument();

    act(() => {
      fireEvent.click(ctaBtn);
    });

    expect(mockNavigate).toHaveBeenCalledWith(
      "/control-center/form-builder/create",
      {}
    );
    expect(store.getRawState().tourOpen).toBe(false);
    expect(
      localStorage.getItem("akvo_mis_tour_completed_42_test-workspace")
    ).toBe("true");
  });

  test("handles final step primary CTA navigation and dismissal for Path B (Review)", () => {
    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "review";
      s.tourStep = 3; // Final step in Review is Step 4 of 4
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(screen.getByText(/STEP 4 OF 4/i)).toBeInTheDocument();
    const ctaBtn = screen.getByText("Review pending approvals");
    expect(ctaBtn).toBeInTheDocument();

    act(() => {
      fireEvent.click(ctaBtn);
    });

    expect(mockNavigate).toHaveBeenCalledWith("/control-center/approvals", {});
    expect(store.getRawState().tourOpen).toBe(false);
  });

  test("handles final step primary CTA navigation for Path C (Explore)", () => {
    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "explore";
      s.tourStep = 4; // Final step (Step 5 of 5)
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    const ctaBtn = screen.getByText("Create a dashboard");
    expect(ctaBtn).toBeInTheDocument();

    act(() => {
      fireEvent.click(ctaBtn);
    });

    expect(mockNavigate).toHaveBeenCalledWith("/control-center/dashboard", {
      state: { openCreate: true },
    });
  });

  test("adapts Explore tour for Data Viewer lacking dashboard permission (skips dashboard step and provides Browse data CTA)", () => {
    // Setup DOM targets
    const dataTarget = document.createElement("div");
    dataTarget.setAttribute("data-tour", "sidebar-data");
    const downloadsTarget = document.createElement("div");
    downloadsTarget.setAttribute("data-tour", "sidebar-downloads");
    const helpTarget = document.createElement("div");
    helpTarget.className = "chatbot-fab-btn";

    document.body.appendChild(dataTarget);
    document.body.appendChild(downloadsTarget);
    document.body.appendChild(helpTarget);

    store.update((s) => {
      s.user = {
        id: 99,
        email: "viewer@akvo.org",
        roles: [{ role: "Data Viewer", can_dashboard_view: true }],
      };
      s.tourOpen = true;
      s.tourGoal = "explore";
      s.tourStep = 0; // Step 1 Welcome modal
    });

    const { unmount } = render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    // Total steps for Data Viewer should be 4 (not 5)
    expect(screen.getByText(/STEP 1 OF 4/i)).toBeInTheDocument();

    // Advance to Step 2 (Manage Data)
    act(() => {
      fireEvent.click(screen.getByText("Show me how"));
    });
    expect(screen.getByText(/STEP 2 OF 4/i)).toBeInTheDocument();
    expect(screen.getByText("Browse your data")).toBeInTheDocument();

    // Advance to Step 3 (Downloads - skips sidebar-dashboards!)
    act(() => {
      fireEvent.click(screen.getByText("Next"));
    });
    expect(screen.getByText(/STEP 3 OF 4/i)).toBeInTheDocument();
    expect(screen.getByText("Download your data")).toBeInTheDocument();

    // Advance to Step 4 (Get help)
    act(() => {
      fireEvent.click(screen.getByText("Next"));
    });
    expect(screen.getByText(/STEP 4 OF 4/i)).toBeInTheDocument();
    expect(screen.getByText("Get help any time")).toBeInTheDocument();

    // CTA should say "Browse data" instead of "Create a dashboard"
    const ctaBtn = screen.getByText("Browse data");
    expect(ctaBtn).toBeInTheDocument();
    expect(screen.queryByText("Create a dashboard")).not.toBeInTheDocument();

    act(() => {
      fireEvent.click(ctaBtn);
    });

    expect(mockNavigate).toHaveBeenCalledWith("/control-center/data", {});
    expect(store.getRawState().tourOpen).toBe(false);

    unmount();
    dataTarget.remove();
    downloadsTarget.remove();
    helpTarget.remove();
  });

  test("getStorageKey generates correct scoped localStorage key", () => {
    expect(getStorageKey({ id: 10 }, { subdomain: "acme" })).toBe(
      "akvo_mis_tour_completed_10_acme"
    );
    expect(getStorageKey(null, null)).toBe(
      "akvo_mis_tour_completed_guest_default"
    );
  });

  test("smoothly scrolls down to #panel-submission when entering Step 4 of Setup", () => {
    const mockScrollTo = jest.fn();
    window.scrollTo = mockScrollTo;

    const panel = document.createElement("div");
    panel.id = "panel-submission";
    const mockScrollIntoView = jest.fn();
    panel.scrollIntoView = mockScrollIntoView;
    panel.getBoundingClientRect = () => ({
      top: 500,
      left: 200,
      width: 600,
      height: 300,
      right: 800,
      bottom: 800,
    });
    document.body.appendChild(panel);

    store.update((s) => {
      s.tourOpen = true;
      s.tourGoal = "setup";
      s.tourStep = 3; // Step 4 of 5 ("Watch submissions arrive")
    });

    render(
      <BrowserRouter>
        <OnboardingTour />
      </BrowserRouter>
    );

    expect(screen.getByText("Watch submissions arrive")).toBeInTheDocument();
    expect(mockScrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
    });
    expect(mockScrollTo).toHaveBeenCalledWith({
      top: 400, // 500 - 100 header offset
      behavior: "smooth",
    });

    panel.remove();
  });
});
