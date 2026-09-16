import { toPolygonPoints, polygonArea, polygonAreaHectares } from "../geometry";

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

describe("toPolygonPoints", () => {
  test("passes an array of pairs through", () => {
    expect(toPolygonPoints(triangle)).toEqual(triangle);
  });

  test("parses a JSON string answer", () => {
    expect(toPolygonPoints(JSON.stringify(triangle))).toEqual(triangle);
  });

  test("returns an empty shape for anything unusable", () => {
    expect(toPolygonPoints(null)).toEqual([]);
    expect(toPolygonPoints("")).toEqual([]);
    expect(toPolygonPoints("[not json")).toEqual([]);
    expect(toPolygonPoints(42)).toEqual([]);
  });

  test("drops malformed vertices rather than throwing in a render path", () => {
    expect(toPolygonPoints([[1, 2], null, [3], [4, 5]])).toEqual([
      [1, 2],
      [4, 5],
    ]);
  });
});

describe("polygonArea", () => {
  test("is zero below three points", () => {
    expect(polygonArea([])).toBe(0);
    expect(polygonArea(triangle.slice(0, 2))).toBe(0);
  });

  test("measures a square of known size", () => {
    // At the equator 0.01 degrees is ~1113.2 m on both axes.
    const square = [
      [0, 0],
      [0, 0.01],
      [0.01, 0.01],
      [0.01, 0],
    ];
    expect(polygonAreaHectares(square)).toBeCloseTo(123.9, 0);
  });

  test("is unaffected by winding direction", () => {
    expect(polygonArea([...triangle].reverse())).toBeCloseTo(
      polygonArea(triangle),
      5
    );
  });

  /**
   * The stored format is akvo-react-form's [lat, lng] — latitude first (GEO-001 D-1b).
   * Reading it as GeoJSON's [lng, lat] does not crash, it silently measures the wrong
   * place, so the fixture is deliberately asymmetric: near the equator, far from the
   * prime meridian. A symmetric one would pass either way.
   */
  test("reads latitude first - axis-order regression", () => {
    const swapped = triangle.map(([lat, lng]) => [lng, lat]);
    expect(polygonArea(triangle)).toBeGreaterThan(polygonArea(swapped) * 1.2);
  });
});
