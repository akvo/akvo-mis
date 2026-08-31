import "@testing-library/jest-dom";
import geo from "../geo";

describe("geo", () => {
  test("exports exactly the topojson-free helpers", () => {
    expect(Object.keys(geo).sort()).toEqual([
      "defaultPos",
      "fixCoordinates",
      "getColorScale",
      "normalizeLon",
      "shiftLonPositive",
      "tile",
    ]);
  });

  test("defaultPos returns the neutral world viewport", () => {
    expect(geo.defaultPos()).toEqual({
      coordinates: [0, 0],
      bbox: [
        [-60, -180],
        [75, 180],
      ],
    });
  });

  test("fixCoordinates wraps a longitude past the antimeridian", () => {
    expect(geo.fixCoordinates([10, 190])).toEqual([10, -170]);
  });

  test("fixCoordinates leaves malformed input untouched", () => {
    expect(geo.fixCoordinates([10])).toEqual([10]);
    expect(geo.fixCoordinates("nope")).toEqual("nope");
  });

  test("getColorScale with percent method spans 0-100", () => {
    const scale = geo.getColorScale({
      method: "percent",
      colors: [],
      colorRange: ["#a", "#b"],
    });
    expect(scale.domain()).toEqual([0, 100]);
  });
});
