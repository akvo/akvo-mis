import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import BuilderInspector from "../BuilderInspector";

jest.mock("../../../lib/api");

// VIZ-027 FE-7 (D-18): the author picks the date the dashboard's date
// range uses. A date question asked on several forms under one name is
// one choice; the backend matches it by name on each widget's form.
// Also FE-5: the filter-question picker sits in the same panel.

const SOURCES = {
  forms: [
    {
      id: 7001,
      name: "Water point registration",
      type: "registration",
      questions: [
        {
          id: 700110,
          label: "Registration date",
          name: "registered_on",
          type: "date",
        },
      ],
    },
    {
      id: 7002,
      name: "Water quality visit",
      type: "monitoring",
      parent: 7001,
      questions: [
        {
          id: 700203,
          label: "Visit date",
          name: "visit_date",
          type: "date",
        },
      ],
    },
    {
      id: 7003,
      name: "Quick status check",
      type: "monitoring",
      parent: 7001,
      questions: [
        {
          id: 700303,
          label: "Date of the check",
          name: "visit_date",
          type: "date",
        },
      ],
    },
  ],
};

const draw = (defaultFilters) => {
  const onDashboardChange = jest.fn();
  render(
    <BuilderInspector
      widget={null}
      sources={SOURCES}
      widgets={[]}
      dashboardName="Water Points"
      dashboardDesc=""
      defaultFilters={defaultFilters}
      isPublic={false}
      isPublished={false}
      onWidgetChange={jest.fn()}
      onDashboardChange={onDashboardChange}
      onVisibilityChange={jest.fn()}
    />
  );
  return onDashboardChange;
};

const openPicker = () =>
  fireEvent.mouseDown(
    screen
      .getByTestId("date-question-picker")
      .querySelector(".ant-select-selector")
  );

const optionTitled = (title) =>
  document.querySelector(`.ant-select-item-option[title="${title}"]`);

test("hidden while the date filter is off", () => {
  draw({ date: { enabled: false } });
  expect(screen.queryByTestId("date-question-picker")).toBeNull();
});

test("offers the submission date and each date name once", () => {
  draw({ date: { enabled: true } });
  openPicker();
  expect(optionTitled("Submission date")).not.toBeNull();
  expect(
    optionTitled("Visit date — Water quality visit, Quick status check")
  ).not.toBeNull();
  expect(
    optionTitled("Registration date — Water point registration")
  ).not.toBeNull();
  expect(document.querySelectorAll(".ant-select-item-option").length).toBe(3);
});

test("picking a name stores its first question, keeping the date toggle", () => {
  const onDashboardChange = draw({
    date: { enabled: true },
    administration: { enabled: true },
  });
  openPicker();
  fireEvent.click(
    optionTitled("Visit date — Water quality visit, Quick status check")
  );
  expect(onDashboardChange).toHaveBeenCalledWith("default_filters", {
    date: { enabled: true, date_question: 700203 },
    administration: { enabled: true },
  });
});

test("the submission date clears the stored question", () => {
  const onDashboardChange = draw({
    date: { enabled: true, date_question: 700203 },
  });
  openPicker();
  fireEvent.click(optionTitled("Submission date"));
  expect(onDashboardChange).toHaveBeenCalledWith("default_filters", {
    date: { enabled: true, date_question: null },
  });
});

test("the filter-question picker sits in the dashboard panel (FE-5)", () => {
  draw({ date: { enabled: true } });
  expect(
    screen.getByRole("button", { name: /choose questions/i })
  ).toBeInTheDocument();
});

test("a stored id of any form in the group shows as the group", () => {
  draw({ date: { enabled: true, date_question: 700303 } });
  expect(
    screen
      .getByTestId("date-question-picker")
      .querySelector(".ant-select-selection-item")
  ).toHaveTextContent("Visit date — Water quality visit, Quick status check");
});

test("an id in no group shows as a saved date question, not a number", () => {
  draw({ date: { enabled: true, date_question: 999999 } });
  expect(
    screen
      .getByTestId("date-question-picker")
      .querySelector(".ant-select-selection-item")
  ).toHaveTextContent("Saved date question");
});
