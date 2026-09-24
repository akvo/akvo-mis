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
});
