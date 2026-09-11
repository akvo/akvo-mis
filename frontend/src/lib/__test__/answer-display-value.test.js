import {
  getAnswerDisplayValue,
  getLastAnswerDisplayValue,
} from "../form-helpers";

const option = {
  type: "option",
  option: [
    { id: 1, value: "male", label: "Male" },
    { id: 2, value: "female", label: "Female" },
  ],
};
const multiple = { ...option, type: "multiple_option" };

describe("getAnswerDisplayValue for option questions", () => {
  test("shows the option label for a known value", () => {
    expect(getAnswerDisplayValue(option, ["male"])).toBe("Male");
  });

  test("shows a free-text 'other' answer as-is", () => {
    expect(getAnswerDisplayValue(option, ["tesssttt"])).toBe("tesssttt");
  });

  test("shows dash for an empty answer", () => {
    expect(getAnswerDisplayValue(option, [])).toBe("-");
    expect(getAnswerDisplayValue(option, null)).toBe("-");
  });

  test("multiple option mixes labels and 'other' text", () => {
    expect(getAnswerDisplayValue(multiple, ["male", "custom"])).toBe(
      "Male, custom"
    );
  });

  test("last value uses the same rule", () => {
    expect(getLastAnswerDisplayValue(option, ["custom"])).toBe("custom");
    expect(getLastAnswerDisplayValue(multiple, ["female"])).toBe("Female");
  });
});
