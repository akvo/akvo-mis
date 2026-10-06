import { serializeGlobalCriteria } from "../dashboardGlobalFilter";

// VIZ-027 §7, D-15: the list every widget request carries, one
// "option_not_in:<qid>:<value>" per value. Equal selections must produce
// equal lists, or two widgets stop sharing a cache key.
//
// Questions, as in the backend fixture (global_filter_mixin.py):
//   700101 "What is the water source?"
//   700301 "Is the infrastructure operational?"

describe("serializeGlobalCriteria", () => {
  test("filter out Non-operational", () => {
    expect(serializeGlobalCriteria({ 700301: ["non_operational"] })).toEqual([
      "option_not_in:700301:non_operational",
    ]);
  });

  test("two water sources: one entry each, sorted", () => {
    expect(
      serializeGlobalCriteria({ 700101: ["surface_water", "rainwater"] })
    ).toEqual([
      "option_not_in:700101:rainwater",
      "option_not_in:700101:surface_water",
    ]);
  });

  test("two questions: sorted by id as numbers, not as strings", () => {
    // 99 would sort after 700101 as a string.
    expect(
      serializeGlobalCriteria({
        700301: ["non_operational"],
        99: ["no"],
        700101: ["rainwater"],
      })
    ).toEqual([
      "option_not_in:99:no",
      "option_not_in:700101:rainwater",
      "option_not_in:700301:non_operational",
    ]);
  });

  test("a value with `:`, `,` and `|` is passed through untouched", () => {
    // Older forms can hold such values (D-15); the backend splits each
    // entry at most twice, so nothing is escaped here.
    expect(
      serializeGlobalCriteria({ 700301: ["pump:_broken,_leaking|pipe"] })
    ).toEqual(["option_not_in:700301:pump:_broken,_leaking|pipe"]);
  });

  test("a question with nothing ticked is left out", () => {
    expect(
      serializeGlobalCriteria({ 700101: [], 700301: ["non_operational"] })
    ).toEqual(["option_not_in:700301:non_operational"]);
  });

  test("nothing ticked is null, so compact() drops the parameter", () => {
    expect(serializeGlobalCriteria({})).toBeNull();
    expect(serializeGlobalCriteria({ 700101: [] })).toBeNull();
    expect(serializeGlobalCriteria(null)).toBeNull();
    expect(serializeGlobalCriteria()).toBeNull();
  });

  test("the viewer's selection is not reordered in place", () => {
    const exclusions = { 700101: ["surface_water", "rainwater"] };
    serializeGlobalCriteria(exclusions);
    expect(exclusions).toEqual({ 700101: ["surface_water", "rainwater"] });
  });
});
