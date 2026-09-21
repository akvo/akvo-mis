import {
  polygonArea,
  polygonAreaHectares,
  selfIntersects,
  toPolygonPoints,
} from "./geometry";

/**
 * The web half of polygon validation: it EVALUATES rules but never resolves severity.
 *
 * Severity answers "may this be submitted?", which was settled on the device at capture time.
 * The inputs are not even available here - the enumerator's device setting never syncs, and
 * `required` belongs to the form version in force back then. So the badge reports what is true
 * about the geometry and claims nothing about what it blocked. GEO-013 D-3.
 *
 * Twin: `app/src/form/lib/polygon-rules.js` - same filename, same export names, deliberately
 * duplicated because `app/` and `frontend/` share no package. Change a threshold here and you
 * must change it there; the literal-value test in each repo exists to make you notice.
 */

// Thresholds. Must equal the mobile twin's.
export const MIN_VERTICES = 3;
export const MIN_AREA_SQM = 10;

/**
 * The one threshold that is per-question rather than universal, and absent by default.
 *
 * This is the exception to "the web resolves nothing": it is not severity, it is the rule's own
 * threshold, and without it the badge would silently under-report exactly the oversized shapes a
 * form went to the trouble of forbidding. GEO-003 D-5.
 */
export const MAX_AREA_KEY = "maxAreaHa";

const maxAreaHa = (geoConfig) => {
  const configured = geoConfig?.[MAX_AREA_KEY];
  return Number.isFinite(configured) && configured > 0 ? configured : null;
};

const isPair = (point) =>
  Array.isArray(point) &&
  point.length >= 2 &&
  Number.isFinite(point[0]) &&
  Number.isFinite(point[1]);

/** An absence, not a broken answer - nothing to report either way. */
export const isNoAnswer = (value) =>
  value === null ||
  typeof value === "undefined" ||
  (Array.isArray(value) && !value.length);

/**
 * `gating: true` means a failure makes every LATER rule meaningless, so they are skipped rather
 * than evaluated: a two-point line has no area worth printing, and a bowtie's area is
 * mathematically ambiguous. GEO-013 D-2.
 */
export const POLYGON_RULES = [
  {
    key: "parseable",
    gating: true,
    message: () => "Not a valid shape",
    evaluate: (points) => ({
      pass: Array.isArray(points) && points.length > 0 && points.every(isPair),
    }),
  },
  {
    key: "minVertices",
    gating: true,
    message: ({ actual, threshold }) =>
      `Only ${actual} of ${threshold} points needed for a shape`,
    evaluate: (points) => ({
      pass: points.length >= MIN_VERTICES,
      params: { actual: points.length, threshold: MIN_VERTICES },
    }),
  },
  {
    key: "selfIntersection",
    gating: true,
    message: () => "Boundary crosses itself",
    evaluate: (points) => ({ pass: !selfIntersects(points) }),
  },
  {
    key: "minArea",
    gating: false,
    message: ({ actual, threshold }) =>
      `Area ${actual} m², below the ${threshold} m² minimum`,
    evaluate: (points) => {
      const actual = polygonArea(points);
      return {
        pass: actual >= MIN_AREA_SQM,
        params: { actual: Math.round(actual), threshold: MIN_AREA_SQM },
      };
    },
  },
  {
    key: "maxArea",
    gating: false,
    message: ({ actual, threshold }) =>
      `Area ${actual} ha, above the ${threshold} ha maximum`,
    evaluate: (points, ctx) => {
      const threshold = maxAreaHa(ctx?.geoConfig);
      if (threshold === null) {
        return { pass: true };
      }
      const actual = polygonAreaHectares(points);
      return {
        pass: actual <= threshold,
        params: { actual: Number(actual.toFixed(2)), threshold },
      };
    },
  },
];

/**
 * One result per rule. A skipped result is not a pass; it carries the key that gated it.
 *
 * Returns nothing for an absence, and also for anything `toPolygonPoints` cannot coerce - the
 * cell already renders "-" for those, so a badge saying "not a valid shape" would be a second
 * opinion on a question already answered. `parseable` is consequently a formality on this side
 * and a real check on the mobile one, where the raw value reaches the rule uncoerced.
 */
export const runPolygonRules = (value, geoConfig = null) => {
  const points = toPolygonPoints(value);
  if (isNoAnswer(value) || !points.length) {
    return [];
  }
  return POLYGON_RULES.reduce(
    (acc, rule) => {
      if (acc.gatedBy) {
        return {
          gatedBy: acc.gatedBy,
          results: [
            ...acc.results,
            {
              key: rule.key,
              pass: null,
              skipped: true,
              skippedBy: acc.gatedBy,
            },
          ],
        };
      }
      const { pass, params = {} } = rule.evaluate(points, { geoConfig });
      return {
        gatedBy: !pass && rule.gating ? rule.key : null,
        results: [
          ...acc.results,
          {
            key: rule.key,
            pass,
            params,
            skipped: false,
            label: rule.message(params),
          },
        ],
      };
    },
    { results: [], gatedBy: null }
  ).results;
};

/**
 * Is the area readout meaningless for this geometry?
 *
 * On a self-crossing ring the shoelace sum is ALGEBRAIC - opposite-wound lobes subtract - so a
 * symmetric bowtie spanning kilometres reports ~0 ha. Any surface printing an area must mark it
 * untrustworthy rather than state it as fact. GEO-003 D-6.
 *
 * Accepts either full results or the `polygonWarnings` shape, since only the key matters.
 *
 * Twin: `app/src/form/lib/polygon-rules.js`.
 */
export const areaIsAmbiguous = (results = []) =>
  results.some((r) => r.key === "selfIntersection" && r.pass !== true);

export const failedRules = (results = []) =>
  results.filter((r) => !r.skipped && !r.pass);

/** Convenience for a render path that only wants the sentences. */
export const polygonWarnings = (value, geoConfig = null) =>
  failedRules(runPolygonRules(value, geoConfig)).map((r) => ({
    key: r.key,
    label: r.label,
  }));
