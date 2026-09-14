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
  // Leaflet puts this on the tile <img> elements, which is what lets
  // html2canvas read them back out instead of tainting the export
  // canvas (VIZ-023). akvo-charts spreads this object into L.tileLayer's
  // options, so the key reaches Leaflet untouched. It lives here rather
  // than on one widget's local tile config so every map exports the same
  // way. Safe because basemaps.cartocdn.com answers with
  // access-control-allow-origin: * — checked against the CARTO host this
  // config now points at, not inherited from the OSM one it replaced.
  crossOrigin: "anonymous",
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

const boundsFromPoints = (pts) => {
  if (!pts || pts.length === 0) {
    return defaultPos();
  }

  const lats = pts.map((p) => p[0]);
  const lons = pts.map((p) => p[1]);

  const latMin = Math.min(...lats);
  const latMax = Math.max(...lats);
  const latCenter = (latMin + latMax) / 2;

  let lonMin = Math.min(...lons);
  let lonMax = Math.max(...lons);
  let lonCenter;

  if (lonMax - lonMin > 180) {
    const shifted = lons.map((l) => (l < 0 ? l + 360 : l));
    lonMin = Math.min(...shifted);
    lonMax = Math.max(...shifted);
    lonCenter = (lonMin + lonMax) / 2;
    if (lonCenter > 180) {
      lonCenter -= 360;
    }
    lonMin = lonMin > 180 ? lonMin - 360 : lonMin;
    lonMax = lonMax > 180 ? lonMax - 360 : lonMax;
  } else {
    lonCenter = (lonMin + lonMax) / 2;
  }

  return {
    coordinates: [latCenter, lonCenter],
    bbox: [
      [latMin, Math.min(lonMin, lonMax)],
      [latMax, Math.max(lonMin, lonMax)],
    ],
  };
};

const geo = {
  tile,
  defaultPos,
  getColorScale,
  hasValidPoint,
  boundsFromPoints,
  normalizeLon,
  shiftLonPositive,
  fixCoordinates,
};

export default geo;
