import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import AISuggestionDrawer from "../AISuggestionDrawer";
import dashboardAi from "../../../util/dashboardAi";

jest.mock("../../../util/dashboardAi");

const mockSources = {
  forms: [
    {
      id: 101,
      name: "Water Points",
      type: "registration",
      questions: [
        { id: 201, label: "Functionality Status", type: "option" },
        { id: 202, label: "Community Population", type: "numeric" },
      ],
    },
  ],
};

const mockSuggestions = [
  {
    type: "bar",
    title: "Functionality Breakdown",
    rationale: "Compares working vs non-working water points",
    col_span: 12,
    form: 101,
    question: 201,
    config: { measure: "current_state" },
  },
  {
    type: "kpi",
    title: "Total Population Served",
    rationale: "Key summary metric for coverage",
    col_span: 6,
    form: 101,
    question: 202,
    config: { aggregation: "sum" },
  },
];

describe("AISuggestionDrawer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    dashboardAi.getStatus.mockResolvedValue({
      data: { ai_available: true, provider: "openai" },
    });
    dashboardAi.suggestWidgets.mockResolvedValue({
      data: { ai_available: true, suggestions: mockSuggestions },
    });
  });

  it("renders unavailable alert and empty state when ai_available is false", async () => {
    dashboardAi.getStatus.mockResolvedValue({
      data: { ai_available: false, provider: "none" },
    });
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    expect(
      await screen.findByText("AI Suggestions Unavailable")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AI widget suggestions require an AI service/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText(/Ask AI for specific widgets/i)
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh/i })).toBeEnabled();
    expect(
      screen.queryByText("Functionality Breakdown")
    ).not.toBeInTheDocument();
    expect(dashboardAi.suggestWidgets).not.toHaveBeenCalled();
  });

  it("automatically loads default suggestions on open", async () => {
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    expect(
      await screen.findByText("Functionality Breakdown")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Compares working vs non-working water points")
    ).toBeInTheDocument();
    expect(screen.getByText("Total Population Served")).toBeInTheDocument();
    expect(
      screen.getByText("Key summary metric for coverage")
    ).toBeInTheDocument();

    expect(dashboardAi.suggestWidgets).toHaveBeenCalledWith(
      1,
      { existing_widget_types: [] },
      expect.anything()
    );
  });

  it("calls onAddWidget when 'Add to Dashboard' button is clicked", async () => {
    const onAddWidget = jest.fn();
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    const addButtons = await screen.findAllByRole("button", {
      name: /add to dashboard/i,
    });
    expect(addButtons.length).toBeGreaterThan(0);

    fireEvent.click(addButtons[0]);

    expect(onAddWidget).toHaveBeenCalledWith(mockSuggestions[0]);
  });

  it("does not call API while typing, only when user clicks Suggest button", async () => {
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    await screen.findByText("Functionality Breakdown");
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);

    const searchInput = screen.getByPlaceholderText(
      /Ask AI for specific widgets/i
    );
    await userEvent.type(searchInput, "Focus on population");

    // Typing should NOT trigger any new API calls
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);

    const generateBtn = screen.getByRole("button", { name: /^suggest$/i });
    await userEvent.click(generateBtn);

    // Clicking Suggest triggers the second call with the prompt_hint
    await waitFor(() => {
      expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(2);
      expect(dashboardAi.suggestWidgets).toHaveBeenLastCalledWith(
        1,
        {
          existing_widget_types: [],
          prompt_hint: "Focus on population",
        },
        expect.anything()
      );
    });

    expect(
      await screen.findByText("Functionality Breakdown")
    ).toBeInTheDocument();
  });

  it("displays empty recommendation state with search bar active when ai_available is true but suggestions array is empty", async () => {
    dashboardAi.suggestWidgets.mockResolvedValue({
      data: { ai_available: true, provider: "openai", suggestions: [] },
    });

    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    expect(
      await screen.findByText(/No recommendations available/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Ask AI for specific widgets/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByText("AI Suggestions Unavailable")
    ).not.toBeInTheDocument();
  });

  it("does not reload suggestions when drawer is closed and reopened with existing content", async () => {
    const { rerender } = render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    expect(
      await screen.findByText("Functionality Breakdown")
    ).toBeInTheDocument();
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);

    // Close the drawer
    rerender(
      <AISuggestionDrawer
        visible={false}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    // Re-open the drawer
    rerender(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    // Content should still be present without a new API request
    expect(screen.getByText("Functionality Breakdown")).toBeInTheDocument();
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);
  });

  it("does not reload suggestions when a suggested widget is added and existingWidgets updates", async () => {
    let widgetsList = [];
    const onAddWidget = jest.fn((w) => {
      widgetsList = [...widgetsList, w];
    });

    const { rerender } = render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    expect(
      await screen.findByText("Functionality Breakdown")
    ).toBeInTheDocument();
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);

    const addButtons = await screen.findAllByRole("button", {
      name: /add to dashboard/i,
    });
    fireEvent.click(addButtons[0]);

    expect(onAddWidget).toHaveBeenCalledWith(mockSuggestions[0]);

    // Parent re-renders with new existingWidgets array
    rerender(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    // Should NOT have triggered a second API call
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Functionality Breakdown")).toBeInTheDocument();
  });

  it("displays error alert when suggestion API request fails", async () => {
    dashboardAi.suggestWidgets.mockRejectedValue(new Error("Network failure"));

    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    expect(
      await screen.findByText(/Failed to load AI suggestions/i)
    ).toBeInTheDocument();
  });

  it("handles unknown questions and empty sources gracefully without crashing", async () => {
    dashboardAi.suggestWidgets.mockResolvedValue({
      data: {
        suggestions: [
          {
            type: "bar",
            title: "Unknown Metric",
            form: 9999,
            question: 8888,
            col_span: 12,
            rationale: "Handles unmapped question IDs safely.",
          },
        ],
      },
    });

    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={{}}
        onAddWidget={jest.fn()}
      />
    );

    expect(await screen.findByText("Unknown Metric")).toBeInTheDocument();
    expect(
      screen.getByText("Handles unmapped question IDs safely.")
    ).toBeInTheDocument();
  });

  it("updates button state to 'Added' when widget is present in existingWidgets and re-enables on removal", async () => {
    let widgetsList = [];
    const onAddWidget = jest.fn((w) => {
      widgetsList = [...widgetsList, { ...w, id: 999 }];
    });
    const { rerender } = render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    const addButtons = await screen.findAllByRole("button", {
      name: /add to dashboard/i,
    });
    expect(addButtons.length).toBe(2);
    fireEvent.click(addButtons[0]);

    expect(onAddWidget).toHaveBeenCalledWith(mockSuggestions[0]);

    // Re-render with widget added to dashboard
    rerender(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    expect(
      await screen.findByRole("button", { name: /added/i })
    ).toBeInTheDocument();

    // Now simulate deleting the widget from dashboard canvas
    widgetsList = [];
    rerender(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    // Button should revert back to "Add to Dashboard"
    const buttonsAfterRemoval = await screen.findAllByRole("button", {
      name: /add to dashboard/i,
    });
    expect(buttonsAfterRemoval.length).toBe(2);
  });

  it("resets prompt hint and reloads default recommendations on Reset click", async () => {
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    await screen.findByText("Functionality Breakdown");
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);

    const searchInput = screen.getByPlaceholderText(
      /Ask AI for specific widgets/i
    );
    await userEvent.type(searchInput, "Custom filter");
    await userEvent.click(screen.getByRole("button", { name: /^suggest$/i }));

    await waitFor(() => {
      expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(2);
    });

    const resetBtn = await screen.findByRole("button", {
      name: /reset to default recommendations/i,
    });
    await userEvent.click(resetBtn);

    await waitFor(() => {
      expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(3);
      expect(dashboardAi.suggestWidgets).toHaveBeenLastCalledWith(
        1,
        { existing_widget_types: [] },
        expect.anything()
      );
      expect(searchInput).toHaveValue("");
    });
  });

  it("loads suggestions when clicking a prompt chip", async () => {
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    await screen.findByText("Functionality Breakdown");
    expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(1);

    const chip = screen.getByText("Monthly Trends");
    fireEvent.click(chip);

    await waitFor(() => {
      expect(dashboardAi.suggestWidgets).toHaveBeenCalledTimes(2);
      expect(dashboardAi.suggestWidgets).toHaveBeenLastCalledWith(
        1,
        {
          existing_widget_types: [],
          prompt_hint: "Monthly Trends",
        },
        expect.anything()
      );
    });
  });

  it("adds all widgets to dashboard when clicking Add All button", async () => {
    let widgetsList = [];
    const onAddWidget = jest.fn((w) => {
      widgetsList = [...widgetsList, { ...w, id: widgetsList.length + 1 }];
    });
    const { rerender } = render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    await screen.findByText("Functionality Breakdown");

    const addAllBtn = await screen.findByRole("button", {
      name: /add all \(2\)/i,
    });
    fireEvent.click(addAllBtn);

    expect(onAddWidget).toHaveBeenCalledTimes(2);
    expect(onAddWidget).toHaveBeenNthCalledWith(1, mockSuggestions[0]);
    expect(onAddWidget).toHaveBeenNthCalledWith(2, mockSuggestions[1]);

    rerender(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={widgetsList}
        sources={mockSources}
        onAddWidget={onAddWidget}
      />
    );

    expect(
      await screen.findByRole("button", { name: /all added/i })
    ).toBeDisabled();
  });

  it("enforces max length 250 and displays character count on search input", async () => {
    render(
      <AISuggestionDrawer
        visible={true}
        onClose={jest.fn()}
        dashboardId={1}
        existingWidgets={[]}
        sources={mockSources}
        onAddWidget={jest.fn()}
      />
    );

    const searchInput = await screen.findByPlaceholderText(
      /Ask AI for specific widgets/i
    );
    expect(searchInput).toHaveAttribute("maxlength", "250");

    await userEvent.type(searchInput, "Focus on wells");
    expect(await screen.findByText("14 / 250")).toBeInTheDocument();
  });
});
