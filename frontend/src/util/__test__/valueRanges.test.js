import { quantileRanges, colorForValue, rangeLabel } from "../valueRanges";

// =========================================================
// Value ranges (#387)
// =========================================================
//
// A value question's points are coloured by which band they fall in.
// The bands are seeded from the data once and then belong to the
// author, so this helper runs exactly at the moment they turn ranges on
// — never again on its own.
//
// Quantiles rather than equal intervals: population, volumes and
// beneficiary counts cluster low with a long tail, and equal intervals
// would drop nearly every point into the first band and colour the map
// one colour.

const PALETTE = ["#d73027", "#fee08b", "#1a9850"];

describe("quantileRanges", () => {
  test("three bands from an even spread", () => {
    const ranges = quantileRanges([10, 20, 30, 40, 50, 60], PALETTE, 3);
    expect(ranges).toHaveLength(3);
    expect(ranges.map((r) => r.to)).toEqual([26.67, 43.33, null]);
    expect(ranges.map((r) => r.color)).toEqual(PALETTE);
  });

  test("the top band is always open", () => {
    const ranges = quantileRanges([1, 2, 3, 4, 5, 6, 7, 8, 9], PALETTE, 3);
    expect(ranges[ranges.length - 1].to).toBeNull();
  });

  test("a long tail still splits, where equal intervals would not", () => {
    // Eight small values and one huge one — the shape this data always
    // has. Equal intervals would put all eight in band one.
    const ranges = quantileRanges([1, 2, 3, 4, 5, 6, 7, 8, 10000], PALETTE, 3);
    const below = (to) => [1, 2, 3, 4, 5, 6, 7, 8, 10000].filter((v) => v < to);
    expect(below(ranges[0].to).length).toBeGreaterThan(1);
    expect(below(ranges[1].to).length).toBeLessThan(9);
  });

  test("values that are all the same collapse to one open band", () => {
    // Every break lands on the same number, and a band whose floor
    // equals its ceiling can never contain a point.
    const ranges = quantileRanges([7, 7, 7, 7], PALETTE, 3);
    expect(ranges).toEqual([{ to: null, color: "#d73027" }]);
  });

  test("ties collapse only the duplicated breaks", () => {
    const ranges = quantileRanges([5, 5, 5, 5, 5, 90], PALETTE, 3);
    expect(ranges.length).toBeLessThan(3);
    expect(ranges[ranges.length - 1].to).toBeNull();
    // Whatever survives is strictly ascending.
    const tos = ranges.slice(0, -1).map((r) => r.to);
    expect([...tos].sort((a, b) => a - b)).toEqual(tos);
  });

  test("a single point is one open band", () => {
    expect(quantileRanges([42], PALETTE, 3)).toEqual([
      { to: null, color: "#d73027" },
    ]);
  });

  test("no data is still a usable starting point", () => {
    // The author gets one row to type into rather than an empty editor.
    expect(quantileRanges([], PALETTE, 3)).toEqual([
      { to: null, color: "#d73027" },
    ]);
  });

  test("non-numeric answers are ignored, not counted as zero", () => {
    // A zero would drag the lowest break down and hand band one to
    // sites that simply have no answer.
    const withJunk = quantileRanges(
      [10, 20, 30, 40, 50, 60, null, "", "n/a"],
      PALETTE,
      3
    );
    expect(withJunk).toEqual(
      quantileRanges([10, 20, 30, 40, 50, 60], PALETTE, 3)
    );
  });

  test("the palette repeats rather than running out of colours", () => {
    const ranges = quantileRanges([1, 2, 3, 4, 5, 6, 7, 8], ["#111"], 3);
    expect(ranges.every((r) => r.color === "#111")).toBe(true);
  });
});

describe("colorForValue", () => {
  const RANGES = [
    { to: 340, color: "#d73027" },
    { to: 890, color: "#fee08b" },
    { to: null, color: "#1a9850" },
  ];

  test("a value below the first break takes the first colour", () => {
    expect(colorForValue(12, RANGES, "#999")).toBe("#d73027");
  });

  test("a value in the middle band takes the middle colour", () => {
    expect(colorForValue(500, RANGES, "#999")).toBe("#fee08b");
  });

  test("a value above every break takes the open band", () => {
    expect(colorForValue(90000, RANGES, "#999")).toBe("#1a9850");
  });

  test("a break belongs to the band above it", () => {
    // The label reads "340 to 890", so 340 is in it — not in "under 340".
    expect(colorForValue(340, RANGES, "#999")).toBe("#fee08b");
  });

  test("no ranges configured falls back", () => {
    expect(colorForValue(500, [], "#999")).toBe("#999");
  });

  test("a point with no value falls back rather than colouring as zero", () => {
    expect(colorForValue(null, RANGES, "#999")).toBe("#999");
  });
});

describe("rangeLabel", () => {
  const RANGES = [
    { to: 340, color: "#d73027" },
    { to: 890, color: "#fee08b" },
    { to: null, color: "#1a9850" },
  ];

  test("the first band reads as a ceiling", () => {
    expect(rangeLabel(RANGES, 0)).toBe("under 340");
  });

  test("a middle band reads as an interval", () => {
    expect(rangeLabel(RANGES, 1)).toBe("340 – 890");
  });

  test("the open band reads as a floor", () => {
    expect(rangeLabel(RANGES, 2)).toBe("890 and above");
  });

  test("a lone open band names no bound at all", () => {
    expect(rangeLabel([{ to: null, color: "#d73027" }], 0)).toBe("All values");
  });

  test("large numbers are grouped for reading", () => {
    expect(rangeLabel([{ to: 12000, color: "#a" }, { to: null }], 0)).toBe(
      "under 12,000"
    );
  });
});
