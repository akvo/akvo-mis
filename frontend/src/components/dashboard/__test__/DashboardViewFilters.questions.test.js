import React from "react";
import { render, fireEvent, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardViewFilters from "../DashboardViewFilters";

jest.mock("../../filters/AdministrationDropdownLocal", () => {
  const MockAdm = () => <div data-testid="adm-dropdown" />;
  MockAdm.displayName = "AdministrationDropdownLocal";
  return MockAdm;
});

// VIZ-027 §7: one multi-select per question in the published snapshot's
// default_filters.questions. A change applies when the dropdown closes,
// so picking three options sends one request per widget, not three.
//
// The same two questions as the backend fixture (global_filter_mixin.py):
//   700301 "Is the infrastructure operational?"  Operational | Non-operational
//   700101 "What is the water source?"  Ground water | Surface water | Rainwater

const STATUS = {
  question: 700301,
  form: 7003,
  label: "Is the infrastructure operational?",
  options: [
    { value: "operational", label: "Operational" },
    { value: "non_operational", label: "Non-operational" },
  ],
};
const SOURCE = {
  question: 700101,
  form: 7001,
  label: "What is the water source?",
  options: [
    { value: "ground_water", label: "Ground water" },
    { value: "surface_water", label: "Surface water" },
    { value: "rainwater", label: "Rainwater" },
  ],
};

const EMPTY = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
  exclusions: {},
};

const draw = ({ questions = [STATUS, SOURCE], value = EMPTY } = {}) => {
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
    />
  );
  return { ...utils, onChange };
};

const selectFor = (qid) => screen.getByTestId(`question-filter-${qid}`);

const open = (qid) =>
  fireEvent.mouseDown(selectFor(qid).querySelector(".ant-select-selector"));

const close = (qid) => fireEvent.blur(selectFor(qid).querySelector("input"));

const pick = (label) =>
  fireEvent.click(
    document.querySelector(`.ant-select-item-option[title="${label}"]`)
  );

describe("rendering", () => {
  test("one multi-select per question the dashboard offers", () => {
    draw();
    expect(selectFor(700301)).toBeInTheDocument();
    expect(selectFor(700101)).toBeInTheDocument();
    expect(
      selectFor(700301).querySelector(".ant-select-multiple")
    ).not.toBeNull();
  });

  test("shown even with the date and administration filters off", () => {
    const { container } = draw();
    expect(container.querySelector(".dashboard-view-filters")).not.toBeNull();
    expect(screen.queryByTestId("adm-dropdown")).not.toBeInTheDocument();
  });

  test("no questions and both toggles off still renders nothing", () => {
    const { container } = draw({ questions: [] });
    expect(container.querySelector(".dashboard-view-filters")).toBeNull();
  });

  test("offers the snapshot's options: the three water sources", () => {
    draw();
    open(700101);
    ["Ground water", "Surface water", "Rainwater"].forEach((label) => {
      expect(
        document.querySelector(`.ant-select-item-option[title="${label}"]`)
      ).not.toBeNull();
    });
  });

  test("shows what is already filtered out", () => {
    // The viewer had filtered out Non-operational before this render.
    draw({ value: { ...EMPTY, exclusions: { 700301: ["non_operational"] } } });
    expect(selectFor(700301)).toHaveTextContent("Non-operational");
  });
});

describe("when a change applies", () => {
  test("picking Surface water and Rainwater: one change, on close", () => {
    // Expect: no request while the viewer is still clicking; one change
    // with both water sources once the dropdown closes.
    const { onChange } = draw();
    open(700101);
    pick("Surface water");
    pick("Rainwater");
    expect(onChange).not.toHaveBeenCalled();

    close(700101);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      ...EMPTY,
      exclusions: { 700101: ["surface_water", "rainwater"] },
    });
  });

  test("a second question keeps the first question's filter", () => {
    // Non-operational is already filtered out; now Rainwater too.
    // Expect: both filters in the change, not just the newest.
    const { onChange } = draw({
      value: { ...EMPTY, exclusions: { 700301: ["non_operational"] } },
    });
    open(700101);
    pick("Rainwater");
    close(700101);
    expect(onChange).toHaveBeenCalledWith({
      ...EMPTY,
      exclusions: { 700301: ["non_operational"], 700101: ["rainwater"] },
    });
  });

  test("opening and closing without picking changes nothing", () => {
    const { onChange } = draw();
    open(700101);
    close(700101);
    expect(onChange).not.toHaveBeenCalled();
  });

  test("removing the Non-operational tag applies at once", () => {
    // The tag's x never opens the dropdown, so waiting for a close
    // would never apply it. Expect: the change goes out immediately.
    const { onChange } = draw({
      value: { ...EMPTY, exclusions: { 700301: ["non_operational"] } },
    });
    fireEvent.click(
      selectFor(700301).querySelector(".ant-select-selection-item-remove")
    );
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      ...EMPTY,
      exclusions: { 700301: [] },
    });
  });
});
