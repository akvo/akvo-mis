import React from "react";
import { render, fireEvent, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardViewFilters from "../DashboardViewFilters";

jest.mock("../../filters/AdministrationDropdownLocal", () => {
  const MockAdm = () => <div data-testid="adm-dropdown" />;
  MockAdm.displayName = "AdministrationDropdownLocal";
  return MockAdm;
});

// VIZ-027 D-16, D-21: a "Filters" button opens a checklist per question in
// the published snapshot's default_filters.questions. Nothing is ticked
// at first (no filter); ticking options shows only those, as in the WAI
// portal. Changes apply once, on Apply.
//
// The same two questions as the backend fixture (global_filter_mixin.py):
//   7003 infrastructure_status  Operational | Non-operational
//   7001 water_source           Ground water | Surface water | Rainwater

const STATUS = {
  form: 7003,
  name: "infrastructure_status",
  label: "Is the infrastructure operational?",
  options: [
    { value: "operational", label: "Operational" },
    { value: "non_operational", label: "Non-operational" },
  ],
};
const SOURCE = {
  form: 7001,
  name: "water_source",
  label: "What is the water source?",
  options: [
    { value: "ground_water", label: "Ground water" },
    { value: "surface_water", label: "Surface water" },
    { value: "rainwater", label: "Rainwater" },
  ],
};
const STATUS_KEY = "7003:infrastructure_status";
const SOURCE_KEY = "7001:water_source";

const EMPTY = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
  selections: {},
  match: "all",
};

const draw = ({
  questions = [STATUS, SOURCE],
  value = EMPTY,
  disabled = false,
} = {}) => {
  const onChange = jest.fn();
  const utils = render(
    <DashboardViewFilters
      defaultFilters={{
        date: { enabled: false },
        administration: { enabled: false },
        questions,
      }}
      value={value}
      onChange={onChange}
      disabled={disabled}
    />
  );
  return { ...utils, onChange };
};

const button = () => screen.getByTestId("question-filters-button");
const togglePanel = () => fireEvent.click(button());
const group = (question) =>
  screen.getByTestId(`question-filter-${question.form}-${question.name}`);
const box = (label) => screen.getByLabelText(label);
const apply = () => screen.getByTestId("question-filters-apply");
const clearAll = () => screen.getByTestId("question-filters-clear");

describe("rendering", () => {
  test("no questions and both toggles off renders nothing", () => {
    const { container } = draw({ questions: [] });
    expect(container).toBeEmptyDOMElement();
  });

  test("questions with both toggles off show the bar and the button", () => {
    draw();
    expect(button()).toBeInTheDocument();
  });

  test("the panel lists every option of every question, none ticked", () => {
    draw();
    togglePanel();
    expect(within(group(STATUS)).getByText(STATUS.label)).toBeInTheDocument();
    expect(within(group(SOURCE)).getByText(SOURCE.label)).toBeInTheDocument();
    [
      "Operational",
      "Non-operational",
      "Ground water",
      "Surface water",
      "Rainwater",
    ].forEach((label) => expect(box(label)).not.toBeChecked());
  });

  test("the panel says what ticking does", () => {
    draw();
    togglePanel();
    expect(screen.getByText(/only the ticked/i)).toBeInTheDocument();
    expect(screen.getByText(/without an answer/i)).toBeInTheDocument();
  });

  test("the applied selection shows as ticked, and the badge counts it", () => {
    draw({
      value: { ...EMPTY, selections: { [STATUS_KEY]: ["operational"] } },
    });
    expect(button()).toHaveAccessibleName(/1/);
    togglePanel();
    expect(box("Operational")).toBeChecked();
    expect(box("Non-operational")).not.toBeChecked();
    expect(box("Rainwater")).not.toBeChecked();
  });

  test("the builder canvas shows the button disabled", () => {
    draw({ disabled: true });
    expect(button()).toBeDisabled();
  });
});

describe("when a change applies", () => {
  test("ticking two water sources applies once, on Apply", () => {
    const { onChange } = draw();
    togglePanel();
    fireEvent.click(box("Surface water"));
    fireEvent.click(box("Ground water"));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(apply());
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toMatchObject({
      // In the options' order, whatever the ticking order.
      selections: { [SOURCE_KEY]: ["ground_water", "surface_water"] },
      match: "all",
    });
  });

  test("a second question keeps the first question's selection", () => {
    const { onChange } = draw({
      value: { ...EMPTY, selections: { [STATUS_KEY]: ["operational"] } },
    });
    togglePanel();
    fireEvent.click(box("Rainwater"));
    fireEvent.click(apply());
    expect(onChange.mock.calls[0][0].selections).toEqual({
      [STATUS_KEY]: ["operational"],
      [SOURCE_KEY]: ["rainwater"],
    });
  });

  test("unticking every option of a question removes its filter", () => {
    const { onChange } = draw({
      value: { ...EMPTY, selections: { [STATUS_KEY]: ["operational"] } },
    });
    togglePanel();
    fireEvent.click(box("Operational"));
    fireEvent.click(apply());
    expect(onChange.mock.calls[0][0].selections).toEqual({});
  });

  test("ticking every option is a filter: only answered data", () => {
    const { onChange } = draw();
    togglePanel();
    fireEvent.click(box("Operational"));
    fireEvent.click(box("Non-operational"));
    fireEvent.click(apply());
    expect(onChange.mock.calls[0][0].selections).toEqual({
      [STATUS_KEY]: ["operational", "non_operational"],
    });
  });

  test("closing without Apply discards the change", () => {
    const { onChange } = draw();
    togglePanel();
    fireEvent.click(box("Rainwater"));
    togglePanel();
    expect(onChange).not.toHaveBeenCalled();
    togglePanel();
    expect(box("Rainwater")).not.toBeChecked();
  });

  test("Apply is disabled while nothing changed", () => {
    draw();
    togglePanel();
    expect(apply()).toBeDisabled();
    fireEvent.click(box("Rainwater"));
    fireEvent.click(box("Rainwater"));
    expect(apply()).toBeDisabled();
  });

  test("Clear all applies at once when something was filtered", () => {
    const { onChange } = draw({
      value: { ...EMPTY, selections: { [STATUS_KEY]: ["operational"] } },
    });
    togglePanel();
    fireEvent.click(clearAll());
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].selections).toEqual({});
  });

  test("Clear all does nothing when nothing was filtered", () => {
    const { onChange } = draw();
    togglePanel();
    expect(clearAll()).toBeDisabled();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("match: all filters or any filter (D-21)", () => {
  test("hidden with one filtered question", () => {
    draw();
    togglePanel();
    fireEvent.click(box("Rainwater"));
    expect(screen.queryByTestId("question-filters-match")).toBeNull();
  });

  test("with two filtered questions, any applies as match any", () => {
    const { onChange } = draw({
      value: { ...EMPTY, selections: { [STATUS_KEY]: ["operational"] } },
    });
    togglePanel();
    fireEvent.click(box("Rainwater"));
    const match = screen.getByTestId("question-filters-match");
    fireEvent.click(within(match).getByLabelText(/any/i));
    fireEvent.click(apply());
    expect(onChange.mock.calls[0][0].match).toBe("any");
  });
});

describe("review fixes", () => {
  const MANY = {
    form: 7001,
    name: "village",
    label: "Which village?",
    options: Array.from({ length: 60 }, (_, i) => ({
      value: `v${i}`,
      label: `Village ${i}`,
    })),
  };

  test("more than 50 ticked values cannot be applied (backend cap)", () => {
    draw({ questions: [MANY] });
    togglePanel();
    MANY.options.slice(0, 51).forEach((o) => fireEvent.click(box(o.label)));
    expect(apply()).toBeDisabled();
    expect(screen.getByText(/at most 50/i)).toBeInTheDocument();
    fireEvent.click(box("Village 0"));
    expect(apply()).toBeEnabled();
  });

  test("a question without options is left out of the panel", () => {
    const { onChange } = draw({
      questions: [
        STATUS,
        { form: 7002, name: "empty", label: "Empty", options: [] },
      ],
    });
    togglePanel();
    expect(screen.queryByText("Empty")).toBeNull();
    fireEvent.click(box("Non-operational"));
    fireEvent.click(apply());
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  test("saved entries without options (builder preview) disable the button", () => {
    draw({
      questions: [
        { form: 7003, name: "infrastructure_status" },
        { form: 7001, name: "water_source" },
      ],
    });
    expect(button()).toBeDisabled();
  });

  test("Escape closes the panel and drops the draft", () => {
    const { onChange } = draw();
    togglePanel();
    fireEvent.click(box("Rainwater"));
    fireEvent.keyDown(box("Operational"), { key: "Escape" });
    expect(onChange).not.toHaveBeenCalled();
    togglePanel();
    expect(box("Rainwater")).not.toBeChecked();
  });

  test("the button says whether the panel is open", () => {
    draw();
    expect(button()).toHaveAttribute("aria-expanded", "false");
    togglePanel();
    expect(button()).toHaveAttribute("aria-expanded", "true");
  });
});

describe("active filters show as chips (ActiveFilterChips)", () => {
  test("no chip section without a filter", () => {
    const { container } = draw();
    expect(container.querySelector(".dashboard-view-filters-chips")).toBeNull();
  });

  test("a section of its own under the bar once something is applied", () => {
    const { container } = draw({
      value: { ...EMPTY, selections: { [STATUS_KEY]: ["operational"] } },
    });
    const section = container.querySelector(".dashboard-view-filters-chips");
    expect(section).not.toBeNull();
    expect(
      container.querySelector(
        ".dashboard-view-filters-inner .dashboard-view-filters-chips"
      )
    ).toBeNull();
  });
});
