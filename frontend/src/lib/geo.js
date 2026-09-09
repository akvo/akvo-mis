import { scaleQuantize } from "d3-scale";

// =========================================================
// Map helpers — TopoJSON-free
// =========================================================
// The per-country TopoJSON global (window.topojson) is gone: a SaaS
// instance has no country shapefile. What survives is everything that
// never depended on polygons: the tile config, colour scales, and
// coordinate normalization around the antimeridian.

const cartoKey = process.env.REACT_APP_CARTO_API_KEY || "";
const tile = {
  url: cartoKey
    ? `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${cartoKey}`
    : "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
};

// Neutral world viewport. Keeps the legacy { coordinates, bbox } shape the
// polygon-derived version returned, so callers need no reshaping.
const defaultPos = () => ({
  coordinates: [0, 0],
  bbox: [
    [-60, -180],
    [75, 180],
  ],
});

const getColorScale = ({ method, colors, colorRange }) => {
  if (method === "percent") {
    return scaleQuantize().domain([0, 100]).range(colorRange);
  }
  const domain = colors
    .reduce(
      (acc, curr) => {
        const v = curr.value;
        const [minVal, maxVal] = acc;
        return [minVal, v > maxVal ? v : maxVal];
      },
      [0, 0]
    )
    .map((acc, index) => {
      if (acc !== 0 && acc < 10) {
        return Math.ceil(acc / 10) * 10;
      }
      if (index && acc) {
        acc = acc < 10 ? 10 : acc;
        const floored = 100 * Math.floor((acc + 50) / 100);
        acc = floored ? floored : acc;
      }
      return acc;
    });
  return scaleQuantize().domain(domain).range(colorRange);
};

/**
 * Coordinate normalization functions for handling International Date Line
 */
const normalizeLon = (lat) => {
  // Normalize latitude to be within -90 to 90 degrees
  return ((lat + 180) % 360) - 180;
};

const shiftLonPositive = (lat) => {
  // Shift latitude to be within 0 to 180 degrees
  return lat % 360;
};

const fixCoordinates = (coords) => {
  if (!Array.isArray(coords) || coords.length < 2) {
    return coords;
  }
  const [lat, lon] = coords;
  const normalizedLon = normalizeLon(lon);
  const fixedLon = shiftLonPositive(normalizedLon);
  return [lat, fixedLon];
};

const hasValidPoint = (row) => Array.isArray(row?.geo) && row.geo.length === 2;

const geo = {
  tile,
  defaultPos,
  getColorScale,
  hasValidPoint,
  normalizeLon,
  shiftLonPositive,
  fixCoordinates,
};

export default geo;
