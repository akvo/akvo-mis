import { tileLayer } from "../tileLayer";
import geo from "../../lib/geo";

describe("util/tileLayer", () => {
  test("re-exports geo.tile", () => {
    expect(tileLayer).toBe(geo.tile);
    expect(tileLayer.url).toContain("cartocdn.com");
  });
});
