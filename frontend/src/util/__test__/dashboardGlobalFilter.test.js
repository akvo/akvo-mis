import { serializeGlobalCriteria } from "../dashboardGlobalFilter";

// VIZ-027 D-20, D-21: a selection is {"<form>:<name>": [ticked values]};
// each ticked value becomes one `option_in:<form>:<name>:<value>`.
const STATUS = "7003:infrastructure_status";
const SOURCE = "7001:water_source";

describe("serializeGlobalCriteria", () => {
  test("show only Operational", () => {
    expect(serializeGlobalCriteria({ [STATUS]: ["operational"] })).toEqual([
      "option_in:7003:infrastructure_status:operational",
    ]);
  });

  test("two water sources: one entry each, sorted", () => {
    expect(
      serializeGlobalCriteria({ [SOURCE]: ["surface_water", "ground_water"] })
    ).toEqual([
      "option_in:7001:water_source:ground_water",
      "option_in:7001:water_source:surface_water",
    ]);
  });

  test("two questions: sorted by form as numbers, then by name", () => {
    expect(
      serializeGlobalCriteria({
        [STATUS]: ["operational"],
        "99:sample_taken": ["yes"],
        [SOURCE]: ["ground_water"],
        "7001:weather": ["fine"],
      })
    ).toEqual([
      "option_in:99:sample_taken:yes",
      "option_in:7001:water_source:ground_water",
      "option_in:7001:weather:fine",
      "option_in:7003:infrastructure_status:operational",
    ]);
  });

  test("a value with `:`, `,` and `|` is passed through untouched", () => {
    expect(
      serializeGlobalCriteria({ [STATUS]: ["pump:_broken,_leaking|pipe"] })
    ).toEqual([
      "option_in:7003:infrastructure_status:pump:_broken,_leaking|pipe",
    ]);
  });

  test("a question with nothing ticked is left out", () => {
    expect(
      serializeGlobalCriteria({ [SOURCE]: [], [STATUS]: ["operational"] })
    ).toEqual(["option_in:7003:infrastructure_status:operational"]);
  });

  test("no selection is null, so compact() drops the parameter", () => {
    expect(serializeGlobalCriteria({})).toBeNull();
    expect(serializeGlobalCriteria({ [SOURCE]: [] })).toBeNull();
    expect(serializeGlobalCriteria(null)).toBeNull();
    expect(serializeGlobalCriteria()).toBeNull();
  });

  test("the viewer's selection is not reordered in place", () => {
    const selections = { [SOURCE]: ["surface_water", "ground_water"] };
    serializeGlobalCriteria(selections);
    expect(selections).toEqual({
      [SOURCE]: ["surface_water", "ground_water"],
    });
  });
});
