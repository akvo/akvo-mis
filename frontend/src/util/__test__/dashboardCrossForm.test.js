import { stackAcrossForms } from "../dashboardCrossForm";

// =========================================================
// The cross-form join (VIZ-015.a)
// =========================================================
//
// Bars from one form, stacks from another, joined on `group` — the
// registration datapoint id both responses carry. The rule that separates
// this from VIZ-015's same-form cross-tab is that it counts SITES: a site
// monitored twelve times contributes one.

const category = (rows) => ({ data: rows });
const series = (rows) => ({ data: rows });

describe("stackAcrossForms", () => {
  test("joins two responses on group", () => {
    const rows = stackAcrossForms({
      category: category([
        { label: "Nadi", group: 7, Surface: 1, Borehole: 0 },
        { label: "Sigatoka", group: 20, Surface: 0, Borehole: 1 },
      ]),
      series: series([
        { label: "Nadi", group: 7, WAF: 0, MRD: 1 },
        { label: "Sigatoka", group: 20, WAF: 1, MRD: 0 },
      ]),
    });
    expect(rows).toEqual([
      { label: "Surface", MRD: 1 },
      { label: "Borehole", WAF: 1 },
    ]);
  });

  test("a site counts once however large the series count is", () => {
    // The response counts submissions; this chart counts sites. Reading
    // row[option] instead of adding one would silently turn it back into
    // a submission count — the single line that separates the two models.
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 1 }]),
      series: series([{ label: "Nadi", group: 7, WAF: 12 }]),
    });
    expect(rows).toEqual([{ label: "Surface", WAF: 1 }]);
  });

  test("a multi-select series adds to every option selected", () => {
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 1 }]),
      series: series([{ label: "Nadi", group: 7, WAF: 1, MRD: 1, RPW: 0 }]),
    });
    expect(rows).toEqual([{ label: "Surface", WAF: 1, MRD: 1 }]);
  });

  test("a site in series but not in category is dropped", () => {
    // Registered but never monitored: there is no bar to put it in, and
    // inventing one would be inventing data.
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 1 }]),
      series: series([
        { label: "Nadi", group: 7, WAF: 1 },
        { label: "Unmonitored", group: 99, WAF: 1 },
      ]),
    });
    expect(rows).toEqual([{ label: "Surface", WAF: 1 }]);
  });

  test("a site with no category answer is dropped, series and all", () => {
    const rows = stackAcrossForms({
      category: category([
        { label: "Nadi", group: 7, Surface: 1, Borehole: 0 },
        { label: "Blank", group: 8, Surface: 0, Borehole: 0 },
      ]),
      series: series([
        { label: "Nadi", group: 7, WAF: 1 },
        { label: "Blank", group: 8, WAF: 1 },
      ]),
    });
    expect(rows).toEqual([{ label: "Surface", WAF: 1 }]);
  });

  test("bars keep first-seen category order", () => {
    // Not Map iteration luck: the order a reader sees must be the order
    // the category response arrived in.
    const rows = stackAcrossForms({
      category: category([
        { label: "A", group: 1, Borehole: 1, Surface: 0 },
        { label: "B", group: 2, Borehole: 0, Surface: 1 },
      ]),
      series: series([]),
    });
    expect(rows.map((r) => r.label)).toEqual(["Borehole", "Surface"]);
  });

  test("an empty category response returns nothing", () => {
    expect(
      stackAcrossForms({ category: category([]), series: series([]) })
    ).toEqual([]);
  });

  test("an empty series response leaves bars with no segments", () => {
    // The chart is empty rather than absent, which is the honest render
    // of "these sites exist, none answered the stacking question".
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 1 }]),
      series: series([]),
    });
    expect(rows).toEqual([{ label: "Surface" }]);
  });

  test("label and group are never treated as option columns", () => {
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 1 }]),
      series: series([{ label: "Nadi", group: 7, WAF: 1 }]),
    });
    expect(rows[0]).not.toHaveProperty("group");
    expect(rows[0].label).toBe("Surface");
  });

  test("a zero column contributes nothing", () => {
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 1 }]),
      series: series([{ label: "Nadi", group: 7, WAF: 0, MRD: 1 }]),
    });
    expect(rows[0]).not.toHaveProperty("WAF");
  });

  test("the category side tolerates counts above one", () => {
    // monitoring=all returns them; truthiness decides the bar, not size.
    const rows = stackAcrossForms({
      category: category([{ label: "Nadi", group: 7, Surface: 9 }]),
      series: series([{ label: "Nadi", group: 7, WAF: 1 }]),
    });
    expect(rows).toEqual([{ label: "Surface", WAF: 1 }]);
  });

  test("survives being called with nothing", () => {
    expect(stackAcrossForms()).toEqual([]);
    expect(stackAcrossForms({})).toEqual([]);
  });
});
