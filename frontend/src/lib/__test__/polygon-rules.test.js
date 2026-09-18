import {
  areaIsAmbiguous,
  MIN_AREA_SQM,
  MIN_VERTICES,
  failedRules,
  polygonWarnings,
  runPolygonRules,
} from "../polygon-rules";
import {
  toGeoJsonRing,
  selfIntersects,
  polygonAreaHectares,
} from "../geometry";

const M = 1 / 111320;
const squareOfSide = (metres, lat = 0) => {
  const d = metres * M;
  return [
    [lat, 0],
    [lat, d],
    [lat + d, d],
    [lat + d, 0],
  ];
};

const TRIANGLE = [
  [0, 0],
  [0, 0.01],
  [0.01, 0],
];
const BOWTIE = [
  [0, 0],
  [0.01, 0.01],
  [0.01, 0],
  [0, 0.01],
];

const byKey = (results, key) => results.find((r) => r.key === key);

describe("thresholds", () => {
  /**
   * Deliberately tautological. `app/src/form/lib/polygon-rules.js` carries the same two numbers
   * and nothing links the files, so this is the tripwire: change one side and this repo's own
   * test goes red, and the diff reminds you the twin exists. GEO-013 D-3.
   */
  it("match the values the mobile twin must also carry", () => {
    expect(MIN_VERTICES).toBe(3);
    expect(MIN_AREA_SQM).toBe(10);
  });
});

describe("toGeoJsonRing", () => {
  it("swaps to lng-first and closes the ring", () => {
    // lat and lng differ in magnitude on purpose: a transposition cannot pass quietly.
    expect(
      toGeoJsonRing([
        [7, 110],
        [8, 111],
        [9, 112],
      ])
    ).toEqual([
      [110, 7],
      [111, 8],
      [112, 9],
      [110, 7],
    ]);
  });
});

describe("selfIntersects", () => {
  it("separates a triangle from a bowtie", () => {
    expect(selfIntersects(TRIANGLE)).toBe(false);
    expect(selfIntersects(BOWTIE)).toBe(true);
  });

  it("accepts the stringified form a round-tripped answer arrives in", () => {
    expect(selfIntersects(JSON.stringify(BOWTIE))).toBe(true);
  });
});

describe("runPolygonRules", () => {
  it("says nothing about an absence or an uncoercible value", () => {
    [null, [], "", "junk"].forEach((value) => {
      expect(runPolygonRules(value)).toEqual([]);
    });
    // Called with no argument at all, rather than naming `undefined`: eslint no-undefined.
    expect(runPolygonRules()).toEqual([]);
  });

  it("passes a valid triangle", () => {
    expect(failedRules(runPolygonRules(TRIANGLE))).toHaveLength(0);
  });

  it("skips the area check on a bowtie rather than reporting an ambiguous area", () => {
    const results = runPolygonRules(BOWTIE);
    expect(byKey(results, "selfIntersection").pass).toBe(false);
    expect(byKey(results, "minArea")).toMatchObject({
      skipped: true,
      skippedBy: "selfIntersection",
    });
  });

  it("skips measurements when there are too few points", () => {
    const results = runPolygonRules([
      [0, 0],
      [0, 0.01],
    ]);
    expect(byKey(results, "minVertices").pass).toBe(false);
    expect(byKey(results, "minArea").skipped).toBe(true);
  });

  it("flags an undersized shape and clears a large one", () => {
    expect(byKey(runPolygonRules(squareOfSide(2)), "minArea").pass).toBe(false);
    expect(byKey(runPolygonRules(squareOfSide(4)), "minArea").pass).toBe(true);
  });
});

describe("maxArea", () => {
  it("is inert when the question authors no ceiling", () => {
    expect(polygonWarnings(squareOfSide(1000))).toEqual([]);
  });

  it("flags a shape above an authored ceiling, in hectares", () => {
    const [warning] = polygonWarnings(squareOfSide(200), { maxAreaHa: 2 });
    expect(warning.key).toBe("maxArea");
    expect(warning.label).toMatch(/above the 2 ha maximum/);
  });

  it("stays quiet below the ceiling", () => {
    expect(polygonWarnings(squareOfSide(200), { maxAreaHa: 20 })).toEqual([]);
  });

  it("ignores a ceiling that is not a positive number", () => {
    [{ maxAreaHa: "20" }, { maxAreaHa: 0 }, { maxAreaHa: -1 }, {}].forEach(
      (geoConfig) => {
        expect(polygonWarnings(squareOfSide(1000), geoConfig)).toEqual([]);
      }
    );
  });
});

describe("areaIsAmbiguous", () => {
  /**
   * Pins the number that justifies gating the area checks behind self-intersection: the
   * shoelace sum is algebraic, so opposite-wound lobes cancel and a bowtie spanning kilometres
   * reports ~0. Twin of the mobile test of the same name.
   */
  it("a symmetric bowtie reports ~0 area despite spanning kilometres", () => {
    const d = 0.02;
    const symmetricBowtie = [
      [0, 0],
      [d, d],
      [d, 0],
      [0, d],
    ];
    expect(polygonAreaHectares(squareOfSide(2200))).toBeGreaterThan(400);
    expect(polygonAreaHectares(symmetricBowtie)).toBeLessThan(1);
  });

  it("flags ambiguity exactly when the ring crosses itself", () => {
    expect(areaIsAmbiguous(polygonWarnings(BOWTIE))).toBe(true);
    expect(areaIsAmbiguous(polygonWarnings(TRIANGLE))).toBe(false);
  });
});

describe("polygonWarnings", () => {
  it("returns a readable sentence per failure", () => {
    expect(polygonWarnings(BOWTIE)).toEqual([
      { key: "selfIntersection", label: "Boundary crosses itself" },
    ]);
  });

  it("quotes both the measured area and the floor", () => {
    const [warning] = polygonWarnings(squareOfSide(2));
    expect(warning.label).toMatch(/below the 10 m² minimum/);
  });

  it("is empty for geometry that passes", () => {
    expect(polygonWarnings(TRIANGLE)).toEqual([]);
  });
});
