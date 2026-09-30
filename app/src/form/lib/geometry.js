import { kinks } from '@turf/kinks';
import { boundingBox } from '../../lib/geometry-index';

const EARTH_RADIUS_M = 6378137;
const SQM_PER_HECTARE = 10000;
// The shortest ring that can enclose anything. Not the rule's threshold - that lives in
// polygon-rules.js; this is only a guard so the helpers below never reason about a non-ring.
const MIN_RING_POINTS = 3;

/**
 * Planar shoelace area of a polygon given as [[lat, lng], ...] - ARF's axis order (GEO-001 D-1b).
 *
 * Coordinates are projected equirectangularly around the polygon's mean latitude before the
 * shoelace sum, so the cos(lat) convergence of meridians is accounted for. Accurate to well
 * under a percent for field-sized plots, which is the only thing this is used for.
 *
 * ponytail: equirectangular, not geodesic. Swap for a spherical excess formula if a plot ever
 * spans more than a degree or two of latitude.
 */
export const polygonArea = (points = []) => {
  if (!Array.isArray(points) || points.length < 3) {
    return 0;
  }
  const meanLat = points.reduce((sum, [lat]) => sum + lat, 0) / points.length;
  const cosLat = Math.cos((meanLat * Math.PI) / 180);
  const projected = points.map(([lat, lng]) => [
    ((lng * Math.PI) / 180) * EARTH_RADIUS_M * cosLat,
    ((lat * Math.PI) / 180) * EARTH_RADIUS_M,
  ]);
  const twiceSignedArea = projected.reduce((sum, [x, y], index) => {
    const [nextX, nextY] = projected[(index + 1) % projected.length];
    return sum + (x * nextY - nextX * y);
  }, 0);
  return Math.abs(twiceSignedArea) / 2;
};

export const polygonAreaHectares = (points = []) => polygonArea(points) / SQM_PER_HECTARE;

/**
 * ARF's `[[lat, lng], ...]` (unclosed) -> a closed GeoJSON linear ring in `[lng, lat]`.
 *
 * Two conversions in one place, both of them easy to get wrong silently: GeoJSON is
 * longitude-first, and a linear ring must repeat its first coordinate at the end. Our format
 * does neither (GEO-001 D-1b), so every turf call goes through here. See GEO-013 D-4 for why
 * this belongs to the rule rather than to the caller.
 *
 * Twin: `frontend/src/lib/geometry.js`.
 */
export const toGeoJsonRing = (points = []) => {
  const ring = points.map(([lat, lng]) => [lng, lat]);
  const [first] = ring;
  const last = ring[ring.length - 1];
  if (first && last && (first[0] !== last[0] || first[1] !== last[1])) {
    return [...ring, [...first]];
  }
  return ring;
};

/**
 * Does the boundary cross itself?
 *
 * Below 3 points there is no ring to cross, so this answers `false` rather than throwing -
 * the rule registry gates it behind the vertex count anyway (GEO-013 D-2), and a geometry
 * helper should not be the thing that decides an answer is too short.
 */
export const selfIntersects = (points = []) => {
  if (!Array.isArray(points) || points.length < MIN_RING_POINTS) {
    return false;
  }
  const feature = {
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [toGeoJsonRing(points)] },
  };
  return kinks(feature).features.length > 0;
};

/**
 * The viewport that shows every one of `polygons` at once, as a Leaflet `LatLngBounds` literal
 * `[[south, west], [north, east]]`. `null` when there is nothing to fit.
 *
 * Lives here rather than on a screen because all three map surfaces need it - capture, the
 * detail preview and overlap review - and because keeping it out of the Leaflet page is what
 * makes "the map zooms out far enough" an ordinary assertion instead of a device test.
 */
export const fitBoundsFor = (polygons) => {
  const vertices = (Array.isArray(polygons) ? polygons : []).flat();
  const box = boundingBox(vertices);
  if (!box) {
    return null;
  }
  return [
    [box.minLat, box.minLon],
    [box.maxLat, box.maxLon],
  ];
};
