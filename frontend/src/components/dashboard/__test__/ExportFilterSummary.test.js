import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import ExportFilterSummary from "../ExportFilterSummary";
import DashboardViewFilters from "../DashboardViewFilters";
import { uiText } from "../../../lib";

// The picked administration, as AdministrationDropdownLocal reports it.
jest.mock("../../filters/AdministrationDropdownLocal", () => {
  const MockAdm = ({ onChange }) => (
    <button onClick={() => onChange({ id: 12, name: "Jakarta" })}>
      pick Jakarta
    </button>
  );
  MockAdm.displayName = "AdministrationDropdownLocal";
  return MockAdm;
});

// VIZ-027: the export leaves the filter bar out and, when something is
// filtered, says what in one line, so the numbers do not read as the
// whole.

const TYPE = {
  form: 7001,
  name: "project_type",
  label: "Type of Project?",
  options: [
    { value: "villages", label: "Villages" },
    { value: "school", label: "School" },
    { value: "households", label: "Households" },
  ],
};
const WEATHER = {
  form: 7003,
  name: "weather",
  label: "Weather",
  options: [{ value: "rainy", label: "Rainy" }],
};
const NOTHING = {
  from_date: null,
  to_date: null,
  administration_id: null,
  selections: {},
  match: "all",
};

const summarise = (value, administrationName = null) =>
  render(
    <ExportFilterSummary
      questions={[TYPE, WEATHER]}
      value={{ ...NOTHING, ...value }}
      administrationName={administrationName}
      text={uiText.en}
    />
  );

test("nothing filtered: no line at all", () => {
  const { container } = summarise({});
  expect(container).toBeEmptyDOMElement();
});

test("each active filter, in words", () => {
  summarise(
    {
      from_date: "2026-10-01",
      to_date: "2026-10-07",
      administration_id: 12,
      selections: { "7001:project_type": ["households", "school"] },
    },
    "Jakarta"
  );
  expect(screen.getByTestId("export-filter-summary")).toHaveTextContent(
    "Filtered by Date: 2026-10-01 – 2026-10-07 · Location: Jakarta · " +
      "Type of Project?: School, Households"
  );
});

test("an open-ended range says so", () => {
  summarise({ from_date: "2026-10-01" });
  expect(screen.getByTestId("export-filter-summary")).toHaveTextContent(
    "Date: 2026-10-01 – …"
  );
});

test("'any filter' is said only when it changes something", () => {
  summarise({
    selections: { "7001:project_type": ["school"], "7003:weather": ["rainy"] },
    match: "any",
  });
  expect(screen.getByTestId("export-filter-summary")).toHaveTextContent(
    "Show data matching: Any filter"
  );
});

test("hidden on screen: shown only in the copy the export draws", () => {
  summarise({ from_date: "2026-10-01" });
  expect(screen.getByTestId("export-filter-summary")).toHaveClass(
    "dashboard-export-only"
  );
});

describe("in the filter bar", () => {
  const drawBar = (value = NOTHING) => {
    const onChange = jest.fn();
    const utils = render(
      <DashboardViewFilters
        defaultFilters={{
          date: { enabled: true },
          administration: { enabled: true },
          questions: [TYPE],
        }}
        value={value}
        onChange={onChange}
      />
    );
    return { ...utils, onChange };
  };

  test("the bar itself is left out of the export", () => {
    const { container } = drawBar();
    expect(container.querySelector(".dashboard-view-filters")).toHaveAttribute(
      "data-html2canvas-ignore"
    );
  });

  test("the picked administration is named in the summary", () => {
    const { onChange, rerender } = drawBar();
    fireEvent.click(screen.getByText("pick Jakarta"));
    rerender(
      <DashboardViewFilters
        defaultFilters={{
          date: { enabled: true },
          administration: { enabled: true },
          questions: [TYPE],
        }}
        value={onChange.mock.calls[0][0]}
        onChange={onChange}
      />
    );
    expect(screen.getByTestId("export-filter-summary")).toHaveTextContent(
      "Location: Jakarta"
    );
  });
});
