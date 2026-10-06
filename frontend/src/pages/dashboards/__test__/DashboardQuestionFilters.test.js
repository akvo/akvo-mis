import React from "react";
import { render, fireEvent, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardQuestionFilters from "../DashboardQuestionFilters";

// VIZ-027 §7: the builder picks which questions the published filter bar
// offers. Only option questions can be filtered "out", and picking a
// registration question that a child form re-asks under the same name
// gets a warning (D-8).
//
// Sources are the backend fixture's water point family
// (global_filter_mixin.py), trimmed to what these tests need.

const SOURCES = {
  forms: [
    {
      id: 7001,
      name: "Water point registration",
      type: "registration",
      questions: [
        {
          id: 700101,
          label: "What is the water source?",
          name: "water_source",
          type: "option",
          options: [{ value: "ground_water", label: "Ground water" }],
        },
        {
          id: 700199,
          label: "How many people live nearby?",
          name: "population",
          type: "number",
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
          id: 700204,
          label: "What is the water source? (seen on visit)",
          name: "water_source",
          type: "option",
          options: [{ value: "ground_water", label: "Ground water" }],
        },
        {
          id: 700205,
          label: "Which tests were done?",
          name: "tests_done",
          type: "multiple_option",
          options: [{ value: "ecoli", label: "E. coli" }],
        },
        {
          id: 700206,
          label: "What is the weather during the visit?",
          name: "weather",
          type: "option",
          options: [{ value: "rainy", label: "Rainy" }],
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
          id: 700302,
          label: "What is the weather during the check?",
          name: "weather",
          type: "option",
          options: [{ value: "rainy", label: "Rainy" }],
        },
      ],
    },
  ],
};

const draw = (value = []) => {
  const onChange = jest.fn();
  render(
    <DashboardQuestionFilters
      sources={SOURCES}
      value={value}
      onChange={onChange}
    />
  );
  return onChange;
};

const openPicker = () =>
  fireEvent.mouseDown(
    screen
      .getByTestId("question-filter-picker")
      .querySelector(".ant-select-selector")
  );

const optionTitled = (title) =>
  document.querySelector(`.ant-select-item-option[title="${title}"]`);

describe("what the author can pick", () => {
  test("option and multiple-option questions from every family form", () => {
    draw();
    openPicker();
    expect(optionTitled("What is the water source?")).not.toBeNull();
    expect(
      optionTitled("What is the water source? (seen on visit)")
    ).not.toBeNull();
    expect(optionTitled("Which tests were done?")).not.toBeNull();
  });

  test("a number question is not offered: nothing to filter out", () => {
    draw();
    openPicker();
    expect(optionTitled("How many people live nearby?")).toBeNull();
  });

  test("picking a question adds it with its form", () => {
    const onChange = draw();
    openPicker();
    fireEvent.click(optionTitled("Which tests were done?"));
    expect(onChange).toHaveBeenCalledWith([{ question: 700205, form: 7002 }]);
  });

  test("a picked question can be removed", () => {
    const onChange = draw([
      { question: 700205, form: 7002 },
      { question: 700204, form: 7002 },
    ]);
    fireEvent.click(
      within(screen.getByTestId("question-filter-entry-700205")).getByRole(
        "button",
        { name: /remove/i }
      )
    );
    expect(onChange).toHaveBeenCalledWith([{ question: 700204, form: 7002 }]);
  });
});

describe("the water source is asked again on the visit form (D-8)", () => {
  test("picking the registration question shows a warning", () => {
    // The visit may record a different source than registration did,
    // and the filter would only see the registration answer.
    draw([{ question: 700101, form: 7001 }]);
    const entry = screen.getByTestId("question-filter-entry-700101");
    expect(within(entry).getByRole("alert")).toBeInTheDocument();
  });

  test("the warning offers the visit question and swaps it in place", () => {
    const onChange = draw([
      { question: 700205, form: 7002 },
      { question: 700101, form: 7001 },
    ]);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Use Water quality visit question instead",
      })
    );
    expect(onChange).toHaveBeenCalledWith([
      { question: 700205, form: 7002 },
      { question: 700204, form: 7002 },
    ]);
  });

  test("picking the visit question shows no warning", () => {
    draw([{ question: 700204, form: 7002 }]);
    const entry = screen.getByTestId("question-filter-entry-700204");
    expect(within(entry).queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("the weather is asked on two monitoring forms (D-14)", () => {
  test("the entry says where else it is asked", () => {
    // The filter reads the latest weather answer from either form, so
    // the author must see that it is not just the check form.
    draw([{ question: 700302, form: 7003 }]);
    const entry = screen.getByTestId("question-filter-entry-700302");
    expect(entry).toHaveTextContent("Also asked on: Water quality visit");
  });

  test("it is information, not a warning", () => {
    draw([{ question: 700302, form: 7003 }]);
    const entry = screen.getByTestId("question-filter-entry-700302");
    expect(within(entry).queryByRole("alert")).not.toBeInTheDocument();
  });

  test("a question asked on one form only gets no hint", () => {
    draw([{ question: 700205, form: 7002 }]);
    expect(
      screen.getByTestId("question-filter-entry-700205")
    ).not.toHaveTextContent("Also asked on");
  });
});

describe("the weather options differ between the two forms (D-14)", () => {
  // The visit form's weather question also offers "Stormy"; the check
  // form's does not. The filter bar will offer it, but the author should
  // know where it comes from, in case it is a spelling slip.
  const withStormy = {
    forms: SOURCES.forms.map((form) => ({
      ...form,
      questions: form.questions.map((q) =>
        q.id === 700206
          ? {
              ...q,
              options: [
                { value: "rainy", label: "Rainy" },
                { value: "stormy", label: "Stormy" },
              ],
            }
          : q
      ),
    })),
  };

  const drawMixed = () => {
    const onChange = jest.fn();
    render(
      <DashboardQuestionFilters
        sources={withStormy}
        value={[{ question: 700302, form: 7003 }]}
        onChange={onChange}
      />
    );
    return onChange;
  };

  test("a warning names the option and the form that has it", () => {
    drawMixed();
    const alert = within(
      screen.getByTestId("question-filter-entry-700302")
    ).getByRole("alert");
    expect(alert).toHaveTextContent("Stormy");
    expect(alert).toHaveTextContent("Water quality visit");
  });

  test("the warning does not block: the entry stays, nothing is changed", () => {
    const onChange = drawMixed();
    expect(
      screen.getByTestId("question-filter-entry-700302")
    ).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
