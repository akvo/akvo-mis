import React from "react";
import {
  render,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import "@testing-library/jest-dom";
import ActiveFilterChips from "../ActiveFilterChips";
import { uiText } from "../../../lib";

// VIZ-027: the applied filter values, one chip each, in their own section
// under the filter bar. What does not fit the row collapses into "+N",
// which opens a popover below with the rest, each still removable.

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
const THREE = {
  selections: {
    [STATUS_KEY]: ["operational"],
    [SOURCE_KEY]: ["ground_water", "rainwater"],
  },
  match: "all",
};

// jsdom measures nothing, so "responsive" cannot be exercised here: a
// number stands in for the row's width.
const draw = ({ value = THREE, maxCount = 10, disabled = false } = {}) => {
  const onChange = jest.fn();
  const utils = render(
    <ActiveFilterChips
      questions={[STATUS, SOURCE]}
      value={value}
      onChange={onChange}
      disabled={disabled}
      text={uiText.en}
      maxCount={maxCount}
    />
  );
  return { ...utils, onChange };
};

const chipTexts = () =>
  screen
    .queryAllByTestId(/^question-filter-chip-/)
    .map((chip) => chip.textContent);

test("nothing applied renders no section", () => {
  const { container } = draw({ value: { selections: {}, match: "all" } });
  expect(container).toBeEmptyDOMElement();
});

test("one chip per applied value: the option, kept short", () => {
  draw();
  expect(chipTexts()).toEqual(["Operational", "Ground water", "Rainwater"]);
});

test("its info icon names the question, as the WAI portal's tags do", async () => {
  // "Yes" alone does not say which question it answers.
  draw();
  const chip = screen.getByTestId(
    `question-filter-chip-${SOURCE_KEY}:rainwater`
  );
  expect(
    within(chip).getByRole("img", { name: SOURCE.label })
  ).toBeInTheDocument();
  fireEvent.mouseEnter(chip);
  expect(await screen.findByRole("tooltip")).toHaveTextContent(SOURCE.label);
});

test("closing a chip removes that value at once", () => {
  const { onChange } = draw();
  fireEvent.click(
    screen.getByRole("button", {
      name: "Remove filter What is the water source?: Rainwater",
    })
  );
  expect(onChange).toHaveBeenCalledTimes(1);
  expect(onChange.mock.calls[0][0].selections).toEqual({
    [STATUS_KEY]: ["operational"],
    [SOURCE_KEY]: ["ground_water"],
  });
});

test("closing the last chip of a question removes its filter", () => {
  const { onChange } = draw();
  fireEvent.click(
    screen.getByRole("button", {
      name: "Remove filter Is the infrastructure operational?: Operational",
    })
  );
  expect(onChange.mock.calls[0][0].selections).toEqual({
    [SOURCE_KEY]: ["ground_water", "rainwater"],
  });
  expect(onChange.mock.calls[0][0].match).toBe("all");
});

test("what does not fit collapses into +N", () => {
  draw({ maxCount: 1 });
  expect(chipTexts()).toEqual(["Operational"]);
  expect(screen.getByTestId("question-filter-chips-rest")).toHaveTextContent(
    "+2"
  );
});

test("+N opens the rest below, each still removable", async () => {
  const { onChange } = draw({ maxCount: 1 });
  fireEvent.click(screen.getByTestId("question-filter-chips-rest"));
  await waitFor(() =>
    expect(
      screen.getByTestId(`question-filter-chip-${SOURCE_KEY}:rainwater`)
    ).toBeInTheDocument()
  );
  fireEvent.click(
    screen.getByRole("button", {
      name: "Remove filter What is the water source?: Rainwater",
    })
  );
  expect(onChange.mock.calls[0][0].selections).toEqual({
    [STATUS_KEY]: ["operational"],
    [SOURCE_KEY]: ["ground_water"],
  });
});

test("in the builder the chips cannot be removed", () => {
  draw({ disabled: true });
  expect(screen.queryByRole("button", { name: /remove filter/i })).toBeNull();
});
