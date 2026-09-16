const EARTH_RADIUS_M = 6378137;
const SQM_PER_HECTARE = 10000;

/**
 * Coerce a stored geoshape answer to `[[lat, lng], ...]`.
 *
 * The value normally arrives as a real array, but a datapoint whose answers were
 * round-tripped through JSON can present it as a string, so both are accepted and
 * anything else becomes an empty shape rather than throwing in a render path.
 */
export const toPolygonPoints = (value) => {
  if (Array.isArray(value)) {
    return value.filter((p) => Array.isArray(p) && p.length >= 2);
  }
  if (typeof value === "string" && value.startsWith("[")) {
    try {
      return toPolygonPoints(JSON.parse(value));
    } catch (err) {
      return [];
    }
  }
  return [];
};

/**
 * Planar shoelace area in m² of a polygon given as [[lat, lng], ...] — latitude first,
 * matching akvo-react-form and the mobile app (GEO-001 D-1b).
 *
 * Coordinates are projected equirectangularly around the polygon's mean latitude before
 * the shoelace sum, so the cos(lat) convergence of meridians is accounted for. Accurate to
 * well under a percent at field-plot scale, which is all this is used for.
 */
export const polygonArea = (points = []) => {
  const ring = toPolygonPoints(points);
  if (ring.length < 3) {
    return 0;
  }
  const meanLat = ring.reduce((sum, [lat]) => sum + lat, 0) / ring.length;
  const cosLat = Math.cos((meanLat * Math.PI) / 180);
  const projected = ring.map(([lat, lng]) => [
    ((lng * Math.PI) / 180) * EARTH_RADIUS_M * cosLat,
    ((lat * Math.PI) / 180) * EARTH_RADIUS_M,
  ]);
  const twiceSignedArea = projected.reduce((sum, [x, y], index) => {
    const [nextX, nextY] = projected[(index + 1) % projected.length];
    return sum + (x * nextY - nextX * y);
  }, 0);
  return Math.abs(twiceSignedArea) / 2;
};

export const polygonAreaHectares = (points = []) =>
  polygonArea(points) / SQM_PER_HECTARE;
