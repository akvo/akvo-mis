/**
 * Distance helpers for the Submission list's "sort by distance" (APP-586). Pure, offline.
 * Datapoint `geo` is stored as the string "lat|lng"; the device origin comes from
 * UserState.currentLocation.coords ({ latitude, longitude }).
 */
const EARTH_RADIUS_M = 6371000;

const toRad = (deg) => (deg * Math.PI) / 180;

/** Parse a stored "lat|lng" geo string. Returns { lat, lng } or null when absent/unparseable. */
export const parseGeo = (geo) => {
  if (typeof geo !== 'string') {
    return null;
  }
  const [latStr, lngStr] = geo.split('|');
  const lat = parseFloat(latStr);
  const lng = parseFloat(lngStr);
  if (Number.isNaN(lat) || Number.isNaN(lng)) {
    return null;
  }
  return { lat, lng };
};

/**
 * Fallback for datapoints whose `geo` column is empty (server-downloaded master data keeps the
 * GPS only in the answers): read the first `geo`-type question's answer, stored as [lat, lng].
 * `rawJson` is the datapoint's answers (string with `''`-escaped quotes, or an object).
 */
export const geoFromAnswers = (rawJson, geoQuestionIds = []) => {
  if (!rawJson || !geoQuestionIds.length) {
    return null;
  }
  let answers;
  try {
    answers = typeof rawJson === 'string' ? JSON.parse(rawJson.replace(/''/g, "'")) : rawJson;
  } catch (e) {
    return null;
  }
  const point = geoQuestionIds
    .map((id) => answers?.[id])
    .find((v) => Array.isArray(v) && v.length >= 2);
  if (!point) {
    return null;
  }
  const lat = parseFloat(point[0]);
  const lng = parseFloat(point[1]);
  if (Number.isNaN(lat) || Number.isNaN(lng)) {
    return null;
  }
  return { lat, lng };
};

/** Great-circle distance in metres between two { lat, lng } points, or null if either is missing. */
export const haversineMeters = (a, b) => {
  if (!a || !b) {
    return null;
  }
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
};

/**
 * Human label (APP-586 Q2): "{m} m away" below 1 km, "{km} km away" with one decimal from
 * 1–10 km, and no decimal past ~10 km. `trans.distanceMeters` / `trans.distanceKm` carry the
 * `{m}` / `{km}` placeholders.
 */
export const formatDistance = (meters, trans) => {
  if (meters == null || Number.isNaN(meters)) {
    return '';
  }
  if (meters < 1000) {
    return trans.distanceMeters.replace('{m}', String(Math.round(meters)));
  }
  const km = meters / 1000;
  const val = km >= 10 ? String(Math.round(km)) : km.toFixed(1);
  return trans.distanceKm.replace('{km}', val);
};
