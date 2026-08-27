import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardViewFilters from "../DashboardViewFilters";

// The dropdown fetches the user's administration root on mount; that is
// AdministrationDropdownLocal's own concern and it has its own tests.
jest.mock("../../filters/AdministrationDropdownLocal", () => {
  const MockAdm = () => <div data-testid="adm-dropdown" />;
  MockAdm.displayName = "AdministrationDropdownLocal";
  return MockAdm;
});

// =========================================================
// The filter bar matches Manage Data's
// =========================================================
//
// Manage Data renders its filters as plain bordered antd controls in a
// Space (DataFilters.js:469-495): a RangePicker with From/To placeholders
// and a calendar suffix, then the administration dropdown bare.
//
// This bar was built from the VIZ mockup instead: each control sat inside
// a bordered `.dashboard-view-chip` pill, with the picker set
// `bordered={false}` so the pill could act as its border. Two screens, two
// idioms, and a bordered select nested inside a bordered pill.

const BOTH = {
  date: { enabled: true },
  administration: { enabled: true },
};

const draw = (defaultFilters = BOTH) =>
  render(
    <DashboardViewFilters
      defaultFilters={defaultFilters}
      value={{
        from_date: null,
        to_date: null,
        date_question_id: null,
        administration_id: null,
      }}
      onChange={jest.fn()}
    />
  );

describe("it uses the same controls as Manage Data", () => {
  test("no chip wrappers", () => {
    const { container } = draw();
    expect(container.querySelector(".dashboard-view-chip")).toBeNull();
  });

  test("the range picker carries Manage Data's placeholders", () => {
    draw();
    expect(screen.getByPlaceholderText("From")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("To")).toBeInTheDocument();
  });

  test("the range picker keeps its border and antd's calendar suffix", () => {
    const { container } = draw();
    // `bordered={false}` renders .ant-picker-borderless; the shared idiom
    // is the default bordered picker.
    expect(container.querySelector(".ant-picker-borderless")).toBeNull();
    expect(container.querySelector(".anticon-calendar")).toBeInTheDocument();
  });
});

describe("what each filter's toggle controls is unchanged", () => {
  test("both disabled renders no bar at all", () => {
    const { container } = draw({
      date: { enabled: false },
      administration: { enabled: false },
    });
    expect(container.querySelector(".dashboard-view-filters")).toBeNull();
  });

  test("administration only", () => {
    draw({ date: { enabled: false }, administration: { enabled: true } });
    expect(screen.getByTestId("adm-dropdown")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("From")).not.toBeInTheDocument();
  });

  test("date only", () => {
    draw({ date: { enabled: true }, administration: { enabled: false } });
    expect(screen.getByPlaceholderText("From")).toBeInTheDocument();
    expect(screen.queryByTestId("adm-dropdown")).not.toBeInTheDocument();
  });
});

describe("the white belongs to the controls, not to a strip", () => {
  test("the controls sit in a card of their own", () => {
    const { container } = draw();
    expect(
      container.querySelector(".dashboard-view-filters-card")
    ).not.toBeNull();
  });

  test("the card holds both controls, so it is one card and not two", () => {
    const { container } = draw();
    const cards = container.querySelectorAll(".dashboard-view-filters-card");
    expect(cards).toHaveLength(1);
    expect(cards[0].querySelector(".ant-picker")).not.toBeNull();
    expect(
      cards[0].querySelector('[data-testid="adm-dropdown"]')
    ).not.toBeNull();
  });
});
