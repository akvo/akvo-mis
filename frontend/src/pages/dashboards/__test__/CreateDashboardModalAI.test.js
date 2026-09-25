import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import CreateDashboardModal from "../CreateDashboardModal";
import dashboardApi from "../../../util/dashboardApi";
import dashboardAi from "../../../util/dashboardAi";
import { store } from "../../../lib";

jest.mock("../../../util/dashboardApi");
jest.mock("../../../util/dashboardAi");

const modal = (visible, onCreate) => (
  <MemoryRouter>
    <CreateDashboardModal
      visible={visible}
      onCancel={jest.fn()}
      onCreate={onCreate}
    />
  </MemoryRouter>
);

const renderModal = (onCreate = jest.fn()) => render(modal(true, onCreate));

describe("CreateDashboardModal AI Starter Generation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    dashboardAi.getStatus.mockResolvedValue({
      data: { ai_available: true, provider: "openai" },
    });
    store.update((s) => {
      s.allForms = [
        { id: 6001, name: "Water Points", content: { published: true } },
      ];
      s.tenant = { subdomain: "acme", embed_enabled: true };
    });
  });

  it("renders the AI auto-generate toggle when registration forms are available", () => {
    renderModal();
    expect(
      screen.getByText("Auto-generate starter dashboard with AI")
    ).toBeInTheDocument();
  });

  it("renders AI unavailable notice when switch is toggled and ai_available is false", async () => {
    dashboardAi.getStatus.mockResolvedValue({
      data: { ai_available: false, provider: "none" },
    });
    renderModal();
    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);
    expect(
      await screen.findByText(/AI service is currently not configured/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText(/Overview of borehole functionality/i)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("+ Executive KPI Overview")
    ).not.toBeInTheDocument();
  });

  it("reveals user intent input when AI auto-generate switch is toggled", async () => {
    renderModal();
    const aiSwitch = screen.getByRole("switch");
    expect(
      screen.queryByPlaceholderText(/Overview of borehole functionality/i)
    ).not.toBeInTheDocument();

    await userEvent.click(aiSwitch);
    expect(
      await screen.findByPlaceholderText(/Overview of borehole functionality/i)
    ).toBeInTheDocument();
  });

  it("creates dashboard with AI starter widgets when auto-generate is toggled", async () => {
    const suggestedWidgets = [
      { type: "kpi", title: "Total Points", col_span: 6 },
      { type: "bar", title: "Status Breakdown", col_span: 12 },
    ];
    dashboardAi.suggestDashboard.mockResolvedValue({
      data: {
        name: "AI Water Overview",
        description: "Generated starter",
        widgets: suggestedWidgets,
      },
    });
    dashboardApi.create.mockResolvedValue({
      data: { id: 10, slug: "water-overview", widgets: suggestedWidgets },
    });

    const onCreate = jest.fn();
    renderModal(onCreate);

    await userEvent.type(
      screen.getByLabelText("Dashboard name"),
      "Water Overview"
    );

    // Select the form
    const select = screen.getByRole("combobox");
    fireEvent.mouseDown(select);
    const option = await screen.findByText("Water Points");
    fireEvent.click(option);

    // Toggle AI switch
    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    const intentInput = await screen.findByPlaceholderText(
      /Overview of borehole functionality/i
    );
    await userEvent.type(intentInput, "Focus on pump functionality");

    await userEvent.click(screen.getByText("Create dashboard"));

    await waitFor(() => {
      expect(dashboardAi.suggestDashboard).toHaveBeenCalledWith({
        root_form: 6001,
        user_intent: "Focus on pump functionality",
      });
    });

    await waitFor(() => {
      expect(dashboardApi.create).toHaveBeenCalledWith({
        name: "Water Overview",
        root_form: 6001,
        widgets: suggestedWidgets,
      });
    });

    expect(onCreate).toHaveBeenCalledWith({
      id: 10,
      slug: "water-overview",
      widgets: suggestedWidgets,
    });
  });

  it("falls back to empty dashboard creation if AI call fails", async () => {
    dashboardAi.suggestDashboard.mockRejectedValue(new Error("AI timeout"));
    dashboardApi.create.mockResolvedValue({
      data: { id: 11, slug: "water-fallback" },
    });

    const onCreate = jest.fn();
    renderModal(onCreate);

    await userEvent.type(
      screen.getByLabelText("Dashboard name"),
      "Water Fallback"
    );

    const select = screen.getByRole("combobox");
    fireEvent.mouseDown(select);
    const option = await screen.findByText("Water Points");
    fireEvent.click(option);

    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    await userEvent.click(screen.getByText("Create dashboard"));

    await waitFor(() => {
      expect(dashboardAi.suggestDashboard).toHaveBeenCalled();
      expect(dashboardApi.create).toHaveBeenCalledWith({
        name: "Water Fallback",
        root_form: 6001,
      });
    });

    expect(onCreate).toHaveBeenCalledWith({
      id: 11,
      slug: "water-fallback",
    });
  });

  it("populates and appends user intent when clicking quick preset chips", async () => {
    renderModal();
    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    const kpiChip = await screen.findByText("+ Executive KPI Overview");
    expect(kpiChip).toBeInTheDocument();

    await userEvent.click(kpiChip);
    const textarea = screen.getByPlaceholderText(
      /Overview of borehole functionality/i
    );
    expect(textarea).toHaveValue("Executive KPI Overview");

    const spatialChip = screen.getByText("+ Regional & Spatial Breakdown");
    await userEvent.click(spatialChip);
    expect(textarea).toHaveValue(
      "Executive KPI Overview, Regional & Spatial Breakdown"
    );
  });

  it("aborts creation if user cancels while AI generation is in flight", async () => {
    let resolveAi;
    const aiPromise = new Promise((resolve) => {
      resolveAi = resolve;
    });
    dashboardAi.suggestDashboard.mockReturnValue(aiPromise);
    dashboardApi.create.mockResolvedValue({
      data: { id: 12, slug: "water-abort" },
    });

    const onCreate = jest.fn();
    const onCancel = jest.fn();
    render(
      <MemoryRouter>
        <CreateDashboardModal
          visible={true}
          onCancel={onCancel}
          onCreate={onCreate}
        />
      </MemoryRouter>
    );

    await userEvent.type(
      screen.getByLabelText("Dashboard name"),
      "Water Abort"
    );

    const select = screen.getByRole("combobox");
    fireEvent.mouseDown(select);
    const option = await screen.findByText("Water Points");
    fireEvent.click(option);

    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    await userEvent.click(screen.getByText("Create dashboard"));

    // Verify loading status is displayed
    expect(
      await screen.findByText(
        "Analyzing form questions and crafting AI starter layout..."
      )
    ).toBeInTheDocument();

    // User cancels the modal while AI is in-flight
    const cancelBtn = screen.getByRole("button", { name: /cancel/i });
    await userEvent.click(cancelBtn);

    expect(onCancel).toHaveBeenCalled();

    // Now resolve AI in-flight promise
    resolveAi({
      data: { widgets: [{ type: "kpi", title: "K", col_span: 6 }] },
    });

    // Verify dashboardApi.create was NOT called and onCreate was NOT called
    await waitFor(() => {
      expect(dashboardApi.create).not.toHaveBeenCalled();
      expect(onCreate).not.toHaveBeenCalled();
    });
  });

  it("enforces max length 250 and renders character count on user intent textarea", async () => {
    renderModal();
    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    const textarea = await screen.findByPlaceholderText(
      /Overview of borehole functionality/i
    );
    const wrapper = textarea.closest(".ant-input-textarea-show-count");
    expect(wrapper).toHaveAttribute("data-count", "0 / 250");

    await userEvent.type(textarea, "Focus on wells");
    expect(wrapper).toHaveAttribute("data-count", "14 / 250");
  });

  it("passes selected monitoring forms to suggestDashboard when available", async () => {
    store.update((s) => {
      s.allForms = [
        { id: 6001, name: "Water Points", content: { published: true } },
        {
          id: 7001,
          name: "Monthly Water Inspections",
          content: { parent: 6001, published: true },
        },
      ];
    });

    dashboardAi.suggestDashboard.mockResolvedValue({
      data: {
        widgets: [{ type: "kpi", title: "Total Points", col_span: 6 }],
      },
    });
    dashboardApi.create.mockResolvedValue({
      data: { id: 20, slug: "multi-form-dashboard" },
    });

    const onCreate = jest.fn();
    renderModal(onCreate);

    await userEvent.type(
      screen.getByLabelText("Dashboard name"),
      "Multi Form Test"
    );

    const select = screen.getByRole("combobox");
    fireEvent.mouseDown(select);
    const option = await screen.findByText("Water Points");
    fireEvent.click(option);

    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    expect(
      await screen.findByText("Monitoring Forms to Include")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByText("Create dashboard"));

    await waitFor(() => {
      expect(dashboardAi.suggestDashboard).toHaveBeenCalledWith(
        expect.objectContaining({
          root_form: 6001,
        })
      );
    });
  });

  it("displays template generating status and button label without mentioning AI when ai_available is false", async () => {
    dashboardAi.getStatus.mockResolvedValue({
      data: { ai_available: false, provider: "none" },
    });
    let resolveAi;
    const aiPromise = new Promise((resolve) => {
      resolveAi = resolve;
    });
    dashboardAi.suggestDashboard.mockReturnValue(aiPromise);
    dashboardApi.create.mockResolvedValue({
      data: { id: 30, slug: "template-test" },
    });

    renderModal();

    await userEvent.type(
      screen.getByLabelText("Dashboard name"),
      "Template Test"
    );

    const select = screen.getByRole("combobox");
    fireEvent.mouseDown(select);
    const option = await screen.findByText("Water Points");
    fireEvent.click(option);

    const aiSwitch = screen.getByRole("switch");
    await userEvent.click(aiSwitch);

    await userEvent.click(screen.getByText("Create dashboard"));

    expect(
      await screen.findByText(
        "Analyzing form questions and generating starter dashboard..."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText("Generating with AI...")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/crafting AI starter layout/i)
    ).not.toBeInTheDocument();

    resolveAi({ data: { widgets: [] } });
  });
});
