/**
 * Overlap maths: the ratio, and the adaptive threshold it is judged against.
 *
 * Pure. No database, no store, no turf beyond `intersect` — everything here is testable with
 * two arrays of `[lat, lng]`. The database half lives in `overlap-check.js`.
 *
 * Reasoning: GEO-007 D-3 (ratio and why the authored percentage became a ceiling) and
 * GEO-014 D-5 (the accuracy-derived threshold).
 */
import { intersect } from '@turf/intersect';

import { polygonArea, toGeoJsonRing } from './geometry';

/** The rule key overlap reports under, alongside `minArea`, `selfIntersection` and the rest. */
export const OVERLAP_RULE_KEY = 'overlap';

/** Severity for overlap resolves through `validateOverlap` (GEO-007 D-9). */
export const OVERLAP_CONFIG_KEY = 'validateOverlap';

export const DEFAULT_OVERLAP_CEILING = 20;
export const DEFAULT_OVERLAP_FLOOR = 5;

const SQM_PER_HECTARE = 10000;

const asPolygonFeature = (points) => ({
  type: 'Feature',
  properties: {},
  geometry: { type: 'Polygon', coordinates: [toGeoJsonRing(points)] },
});

/** A GeoJSON ring is `[lng, lat]`; everything else in this app is `[lat, lng]` (GEO-001 D-1b). */
const ringToLatLng = (ring = []) => ring.map(([lng, lat]) => [lat, lng]);

/**
 * Area of one GeoJSON polygon's rings: outer ring minus its holes.
 *
 * Holes cannot arise from intersecting two simple rings, and the self-intersection rule gates
 * anything that is not simple — but subtracting them is two lines and the alternative is a
 * silently inflated overlap, which is the direction that wrongly blocks an enumerator.
 */
const ringsArea = (rings = []) =>
  rings.reduce((total, ring, index) => {
    const area = polygonArea(ringToLatLng(ring));
    return index === 0 ? area : total - area;
  }, 0);

/**
 * Area shared by two polygons, in m². `0` when they do not meet.
 *
 * turf 7 takes a FeatureCollection rather than two arguments. The collection is built as a
 * literal so `@turf/helpers` does not have to be a dependency for one object shape.
 */
export const intersectionArea = (pointsA, pointsB) => {
  if (!Array.isArray(pointsA) || !Array.isArray(pointsB)) {
    return 0;
  }
  if (pointsA.length < 3 || pointsB.length < 3) {
    return 0;
  }
  let shared = null;
  try {
    shared = intersect({
      type: 'FeatureCollection',
      features: [asPolygonFeature(pointsA), asPolygonFeature(pointsB)],
    });
  } catch {
    /**
     * turf throws on degenerate rings rather than returning null. Treating that as "no
     * measurable overlap" would be a false pass, so it is raised to the caller as a local
     * failure instead — see `overlap-check.js`, which turns it into an unavailable result.
     */
    throw new Error('intersect failed');
  }
  if (!shared?.geometry) {
    return 0;
  }
  const { type, coordinates } = shared.geometry;
  if (type === 'Polygon') {
    return ringsArea(coordinates);
  }
  if (type === 'MultiPolygon') {
    return coordinates.reduce((total, rings) => total + ringsArea(rings), 0);
  }
  return 0;
};

/**
 * Overlap as a percentage **of the smaller polygon** (GEO-007 technical AC).
 *
 * Of the smaller, not of the new one: encroaching a 10 m² sliver onto a 50 ha neighbour and
 * having a 50 ha claim swallow a 10 m² plot are the same ratio only under this definition, and
 * the second is the one that matters.
 */
export const overlapPercent = (pointsA, pointsB) => {
  const areaA = polygonArea(pointsA);
  const areaB = polygonArea(pointsB);
  const smaller = Math.min(areaA, areaB);
  if (!(smaller > 0)) {
    return 0;
  }
  return (intersectionArea(pointsA, pointsB) / smaller) * 100;
};

const clamp = (value, floor, ceiling) => Math.min(ceiling, Math.max(floor, value));

const configuredPercent = (geoConfig, key, fallback) => {
  const value = geoConfig?.[key];
  return Number.isFinite(value) && value > 0 ? value : fallback;
};

/**
 * The threshold this pair of polygons is judged against, as a percentage.
 *
 * ```
 * combined  = accA + accB                                  // metres, conservative sum
 * computed  = 100 * combined / sqrt(min(areaA, areaB))      // GEO-014 D-5
 * threshold = clamp(computed, floor, ceiling)
 * ```
 *
 * Spurious overlap from GPS error is a band of width ≈ accuracy along a shared edge, so the
 * noise ratio scales as `accuracy / √area` — it shrinks as plots grow. A flat percentage is
 * therefore wrong in both directions and only right near 1 ha (GEO-007 D-3).
 *
 * Two properties the clamp buys, both load-bearing:
 * - **Never more permissive than today.** The authored `overlapThreshold` is the ceiling, so no
 *   existing programme's configuration changes meaning and there is no regression path.
 * - **Never fail-open.** Without a ceiling a 0.01 ha plot computes 300 % and no overlap could
 *   ever fail. That is the exact failure GEO-005 §2 exists to prevent.
 *
 * When either polygon has no measured accuracy the computed value is meaningless, so the
 * threshold falls back to the ceiling — i.e. exactly phase-1 behaviour. That branch is a normal
 * path, not a legacy edge case: `allowTapping` lets a boundary be traced rather than walked, and
 * webform answers never carry accuracy at all (GEO-014 D-4).
 */
export const adaptiveThreshold = ({ accA, accB, areaA, areaB, geoConfig } = {}) => {
  const ceiling = configuredPercent(geoConfig, 'overlapThreshold', DEFAULT_OVERLAP_CEILING);
  const floor = configuredPercent(geoConfig, 'overlapThresholdFloor', DEFAULT_OVERLAP_FLOOR);
  const measured = Number.isFinite(accA) && Number.isFinite(accB);
  const smaller = Math.min(areaA, areaB);
  if (!measured || !(smaller > 0)) {
    return { threshold: ceiling, adaptive: false };
  }
  const computed = (100 * (accA + accB)) / Math.sqrt(smaller);
  return { threshold: clamp(computed, floor, ceiling), adaptive: true };
};

/**
 * The numeric question id, with any repeat suffix stripped.
 *
 * `transformForm` renders repeat instance *n* with the id `"987-1"`, and that string reaches
 * every field prop. `geometry_index.questionId` is the bare INTEGER, with the instance kept
 * separately in `repeatIndex`, so passing the suffixed id into `WHERE questionId = ?` compares
 * an INTEGER column against text SQLite cannot coerce: **zero rows, every time**. The polygon
 * then passes with no candidates examined — silently, and only ever for repeat instances.
 */
export const baseQuestionId = (id) => {
  const parsed = parseInt(`${id}`.split('-')[0], 10);
  return Number.isFinite(parsed) ? parsed : null;
};

/**
 * Answers are keyed `"<questionId>"` at repeat 0 and `"<questionId>-<n>"` after — the same
 * convention `geoshapeAnswersFromJson` reads when the index is written (GEO-006).
 */
export const answerKey = (questionId, repeatIndex = 0) =>
  repeatIndex ? `${questionId}-${repeatIndex}` : `${questionId}`;

/** Detection is switched on by `detectOverlaps` alone; severity never disables it (D-9). */
export const detectOverlapsEnabled = (question) =>
  question?.extra?.geoConfig?.detectOverlaps === true;

export const areaHectares = (points) => polygonArea(points) / SQM_PER_HECTARE;

/**
 * Identifies the exact geometry a stored verdict belongs to.
 *
 * Editing the polygon must return the field to "not validated" (GEO-007 D-1), and comparing the
 * stored signature is how every surface notices — including the submit gate, which never sees
 * the edit happen. Stringifying ~180 vertices costs a few KB held in memory for one question,
 * against the alternative of a length-or-first-vertex heuristic that says "unchanged" when an
 * enumerator drags one point.
 */
export const signatureOf = (points) => JSON.stringify(points || []);
