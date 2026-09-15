const EARTH_RADIUS_M = 6378137;
const SQM_PER_HECTARE = 10000;

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
