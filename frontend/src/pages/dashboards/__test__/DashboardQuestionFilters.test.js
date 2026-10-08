import React from "react";
import { render, fireEvent, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardQuestionFilters from "../DashboardQuestionFilters";

// VIZ-027: the builder picks which filters the published filter bar
// offers. A filter is a question NAME with a scope (D-20): "All forms"
// (the registration form's id: every form of the family that asks it) or
// one monitoring form. Questions the widgets use are suggested first,
// without restricting the choice (D-17). They are chosen in a modal,
// under their question groups: the same label can sit in two groups.
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
          group: "Water point",
          options: [{ value: "ground_water", label: "Ground water" }],
        },
        {
          id: 700199,
          label: "How many people live nearby?",
          name: "population",
          type: "number",
          group: "Water point",
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
          group: "Visit",
          options: [{ value: "ground_water", label: "Ground water" }],
        },
        {
          id: 700205,
          label: "Which tests were done?",
          name: "tests_done",
          type: "multiple_option",
          group: "Tests",
          options: [{ value: "ecoli", label: "E. coli" }],
        },
        {
          id: 700206,
          label: "What is the weather during the visit?",
          name: "weather",
          type: "option",
          group: "Visit",
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
          group: "Check",
          options: [{ value: "rainy", label: "Rainy" }],
        },
      ],
    },
  ],
};

const BAR_ON_VISIT_WEATHER = {
  id: 1,
  type: "bar",
  form: 7002,
  question: 700206,
  config: { group_by: "option" },
};
const TABLE_ON_SOURCE = {
  id: 2,
  type: "table",
  form: 7002,
  question: null,
  config: { criteria: [{ type: "option_in", question: 700101, value: "x" }] },
};
const KPI_ON_NUMBER = {
  id: 3,
  type: "kpi",
  form: 7001,
  question: 700199,
  config: {},
};

const draw = (value = [], widgets = [], sources = SOURCES) => {
  const onChange = jest.fn();
  const utils = render(
    <DashboardQuestionFilters
      sources={sources}
      widgets={widgets}
      value={value}
      onChange={onChange}
    />
  );
  return { ...utils, onChange };
};

const openModal = () =>
  fireEvent.click(screen.getByRole("button", { name: /choose questions/i }));

const chooseScope = (label) => {
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "Answers from" }));
  fireEvent.click(
    document.querySelector(`.ant-select-item-option[title="${label}"]`)
  );
};

const row = (form, name) =>
  screen.queryByTestId(`question-filter-option-${form}:${name}`);

const tick = (form, name) =>
  fireEvent.click(within(row(form, name)).getByRole("checkbox"));

const apply = () =>
  fireEvent.click(screen.getByRole("button", { name: "Apply" }));

// The section a row sits in: a question group, or the widgets' one.
const sectionOf = (form, name) =>
  row(form, name).closest("section").getAttribute("aria-label");

const entry = (form, name) =>
  screen.getByTestId(`question-filter-entry-${form}-${name}`);

describe("what the author can pick", () => {
  test("All forms offers each option question of the family by name", () => {
    draw();
    openModal();
    ["water_source", "tests_done", "weather"].forEach((name) =>
      expect(row(7001, name)).not.toBeNull()
    );
    expect(row(7002, "tests_done")).toBeNull();
  });

  test("a monitoring form offers its own questions", () => {
    draw();
    openModal();
    chooseScope("Water quality visit");
    ["water_source", "tests_done", "weather"].forEach((name) =>
      expect(row(7002, name)).not.toBeNull()
    );
    expect(row(7003, "weather")).toBeNull();
  });

  test("a number question is not offered: nothing to filter by", () => {
    draw();
    openModal();
    expect(row(7001, "population")).toBeNull();
  });

  test("a name with ':' is not offered: the backend refuses it", () => {
    const withColon = {
      forms: [
        {
          ...SOURCES.forms[0],
          questions: [
            {
              id: 700198,
              label: "Pump status",
              name: "pump:status",
              type: "option",
              group: "Pump",
              options: [{ value: "ok", label: "OK" }],
            },
            SOURCES.forms[0].questions[0],
          ],
        },
      ],
    };
    draw([], [], withColon);
    openModal();
    expect(screen.queryByText("Pump status")).toBeNull();
  });

  test("ticking under All forms stores the registration form and the name", () => {
    const { onChange } = draw();
    openModal();
    tick(7001, "tests_done");
    apply();
    expect(onChange).toHaveBeenCalledWith([{ form: 7001, name: "tests_done" }]);
  });

  test("ticking under one monitoring form stores that form", () => {
    const { onChange } = draw();
    openModal();
    chooseScope("Water quality visit");
    tick(7002, "tests_done");
    apply();
    expect(onChange).toHaveBeenCalledWith([{ form: 7002, name: "tests_done" }]);
  });

  test("a picked filter shows ticked; unticking it removes it", () => {
    const { onChange } = draw([
      { form: 7001, name: "tests_done" },
      { form: 7003, name: "weather" },
    ]);
    openModal();
    const checkbox = within(row(7001, "tests_done")).getByRole("checkbox");
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    apply();
    expect(onChange).toHaveBeenCalledWith([{ form: 7003, name: "weather" }]);
  });

  test("ticks are a draft: Cancel changes nothing", () => {
    const { onChange } = draw();
    openModal();
    tick(7001, "tests_done");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  test("a picked filter can be removed from the inspector", () => {
    const { onChange } = draw([
      { form: 7001, name: "tests_done" },
      { form: 7003, name: "weather" },
    ]);
    fireEvent.click(
      within(entry(7001, "tests_done")).getByRole("button", {
        name: /remove/i,
      })
    );
    expect(onChange).toHaveBeenCalledWith([{ form: 7003, name: "weather" }]);
  });
});

describe("question groups tell same-labelled questions apart", () => {
  const twoPowerSupplies = {
    forms: [
      SOURCES.forms[0],
      {
        ...SOURCES.forms[2],
        questions: [
          {
            id: 700310,
            label: "Type of Power Supply",
            name: "borehole_power_supply",
            type: "option",
            group: "Borehole Inspection",
            options: [{ value: "solar", label: "Solar" }],
          },
          {
            id: 700311,
            label: "Type of Power Supply",
            name: "desalination_power_supply",
            type: "option",
            group: "Desalination Inspection",
            options: [{ value: "grid", label: "Grid" }],
          },
        ],
      },
    ],
  };

  test("each sits under its own group, with its name and options", () => {
    draw([], [], twoPowerSupplies);
    openModal();
    chooseScope("Quick status check");
    expect(sectionOf(7003, "borehole_power_supply")).toBe(
      "Borehole Inspection"
    );
    expect(sectionOf(7003, "desalination_power_supply")).toBe(
      "Desalination Inspection"
    );
    expect(row(7003, "borehole_power_supply")).toHaveTextContent(
      "borehole_power_supply · Solar"
    );
  });

  test("under All forms a monitoring form's group names its form", () => {
    draw([], [], twoPowerSupplies);
    openModal();
    expect(sectionOf(7001, "borehole_power_supply")).toBe(
      "Borehole Inspection — Quick status check"
    );
    expect(sectionOf(7001, "water_source")).toBe("Water point");
  });

  test("the search reads the label, the name and the group", () => {
    draw([], [], twoPowerSupplies);
    openModal();
    chooseScope("Quick status check");
    fireEvent.change(screen.getByRole("textbox", { name: /search by/i }), {
      target: { value: "desalination" },
    });
    expect(row(7003, "desalination_power_supply")).not.toBeNull();
    expect(row(7003, "borehole_power_supply")).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: /search by/i }), {
      target: { value: "nothing like this" },
    });
    expect(screen.getByText("No question matches")).toBeInTheDocument();
  });

  test("the inspector entry shows its group", () => {
    draw([{ form: 7003, name: "desalination_power_supply" }], [], {
      forms: twoPowerSupplies.forms,
    });
    expect(entry(7003, "desalination_power_supply")).toHaveTextContent(
      "Desalination Inspection"
    );
  });
});

describe("All forms covers every form that asks the name (D-20)", () => {
  test("the entry lists the forms it reads", () => {
    draw([{ form: 7001, name: "weather" }]);
    expect(entry(7001, "weather")).toHaveTextContent(
      "Covers: Water quality visit, Quick status check"
    );
  });

  test("so does the modal", () => {
    draw();
    openModal();
    expect(row(7001, "weather")).toHaveTextContent(
      "Covers: Water quality visit, Quick status check"
    );
  });

  test("a registration question re-asked on a visit covers both", () => {
    draw([{ form: 7001, name: "water_source" }]);
    expect(entry(7001, "water_source")).toHaveTextContent(
      "Covers: Water point registration, Water quality visit"
    );
  });

  test("it is information, not a warning", () => {
    draw([{ form: 7001, name: "weather" }]);
    expect(within(entry(7001, "weather")).queryByRole("alert")).toBeNull();
  });

  test("a single monitoring form has no Covers hint", () => {
    draw([{ form: 7003, name: "weather" }]);
    expect(entry(7003, "weather")).not.toHaveTextContent("Covers");
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

  test("a warning names the option and the form that has it", () => {
    draw([{ form: 7001, name: "weather" }], [], withStormy);
    const alert = within(entry(7001, "weather")).getByRole("alert");
    expect(alert).toHaveTextContent("Stormy");
    expect(alert).toHaveTextContent("Water quality visit");
  });

  test("the warning does not block: the entry stays, nothing is changed", () => {
    const { onChange } = draw(
      [{ form: 7001, name: "weather" }],
      [],
      withStormy
    );
    expect(entry(7001, "weather")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("questions the widgets use are suggested first (D-17)", () => {
  test("widget questions sit under 'Used in your widgets'", () => {
    draw([], [BAR_ON_VISIT_WEATHER, TABLE_ON_SOURCE]);
    openModal();
    expect(sectionOf(7001, "weather")).toBe("Used in your widgets");
    expect(sectionOf(7001, "water_source")).toBe("Used in your widgets");
    expect(sectionOf(7001, "tests_done")).toBe("Tests — Water quality visit");
  });

  test("a suggested row still names its group", () => {
    draw([], [BAR_ON_VISIT_WEATHER]);
    openModal();
    expect(row(7001, "weather")).toHaveTextContent("Visit");
  });

  test("nothing is restricted: a question no widget uses can be picked", () => {
    const { onChange } = draw([], [BAR_ON_VISIT_WEATHER]);
    openModal();
    tick(7001, "tests_done");
    apply();
    expect(onChange).toHaveBeenCalledWith([{ form: 7001, name: "tests_done" }]);
  });

  test("suggestions follow the canvas", () => {
    const { rerender } = draw([], [BAR_ON_VISIT_WEATHER]);
    rerender(
      <DashboardQuestionFilters
        sources={SOURCES}
        widgets={[]}
        value={[]}
        onChange={jest.fn()}
      />
    );
    openModal();
    expect(sectionOf(7001, "weather")).toBe("Visit — Water quality visit");
  });

  test("a widget on a number question suggests nothing", () => {
    draw([], [KPI_ON_NUMBER]);
    openModal();
    expect(screen.queryByRole("region", { name: "Used in your widgets" })).toBe(
      null
    );
  });
});

describe("review fixes", () => {
  test("a question without a name is not offered", () => {
    const nameless = {
      forms: [
        {
          ...SOURCES.forms[0],
          questions: [
            {
              id: 700197,
              label: "Old question",
              name: null,
              type: "option",
              group: "Old",
              options: [{ value: "a", label: "A" }],
            },
            SOURCES.forms[0].questions[0],
          ],
        },
      ],
    };
    draw([], [], nameless);
    openModal();
    expect(screen.queryByText("Old question")).toBeNull();
  });

  test("an entry no longer in the forms says so, and survives Apply", () => {
    const { onChange } = draw([{ form: 7001, name: "gone" }]);
    expect(entry(7001, "gone")).toHaveTextContent(/no longer in the form/i);
    openModal();
    tick(7001, "weather");
    apply();
    expect(onChange).toHaveBeenCalledWith([
      { form: 7001, name: "gone" },
      { form: 7001, name: "weather" },
    ]);
  });

  test("each Remove button names its entry", () => {
    draw([{ form: 7003, name: "weather" }]);
    expect(
      screen.getByRole("button", {
        name: "Remove What is the weather during the check? — Quick status check",
      })
    ).toBeInTheDocument();
  });

  test("no option question in the family: nothing to choose", () => {
    draw([], [], { forms: [{ ...SOURCES.forms[0], questions: [] }] });
    expect(
      screen.getByRole("button", { name: /choose questions/i })
    ).toBeDisabled();
  });
});
