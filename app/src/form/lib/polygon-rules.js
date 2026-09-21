/**
 * Polygon validation rules, their severity resolver, and the runner that ties them together.
 *
 * Contract, gating semantics and the reasoning behind all of it: GEO-013.
 * Enumerator-facing behaviour, including how `required` participates: GEO-002 section 2.1.
 *
 * Twin: `frontend/src/lib/polygon-rules.js` - same filename, same export names, deliberately
 * duplicated because `app/` and `frontend/` share no package. If you change a threshold here,
 * change it there. The literal-value test in each repo exists to make you notice.
 */
import { polygonArea, polygonAreaHectares, selfIntersects } from './geometry';
import { QUESTION_TYPES } from '../../lib/constants';

// Thresholds. Fixed floors, not configuration - GEO-002 D-1/D-2 and GEO-003 D-2.
export const MIN_VERTICES = 3;
export const MIN_AREA_SQM = 10;

/**
 * The upper bound is the one threshold that IS configurable, and it is absent by default.
 *
 * A floor can be universal - nothing anyone captures is smaller than a doormat - but there is no
 * universal ceiling: 20 ha is large for a smallholder plot and small for a forest concession or a
 * watershed. So this is read per question and does nothing at all unless a form authors it.
 * Hectares, not m2, because authoring 20 ha as 200000 invites a lost zero. GEO-003 D-5.
 */
export const MAX_AREA_KEY = 'maxAreaHa';

const maxAreaHa = (geoConfig) => {
  const configured = geoConfig?.[MAX_AREA_KEY];
  return Number.isFinite(configured) && configured > 0 ? configured : null;
};

export const SEVERITY = {
  block: 'block',
  warn: 'warn',
};

// Only geoshape is validated. A geotrace is an open line: it encloses nothing, so neither the
// area nor the self-intersection question means anything for it (GEO-002 D-3, GEO-009 D-3).
const POLYGON_TYPES = [QUESTION_TYPES.geoshape];

const isPair = (point) =>
  Array.isArray(point) &&
  point.length >= 2 &&
  Number.isFinite(point[0]) &&
  Number.isFinite(point[1]);

/**
 * "The enumerator never answered" - distinct from "the answer is broken".
 *
 * A cleared polygon arrives as `[]` and an unopened one as null or undefined; both are an
 * absence, and rules must not run on an absence or an optional question would report "fewer
 * than 3 vertices" for every polygon nobody touched. Whether an absence is an error is Yup's
 * question, via `required` - see GEO-002 section 2.1.2.
 */
export const isNoAnswer = (value) =>
  value === null || typeof value === 'undefined' || (Array.isArray(value) && !value.length);

/**
 * `gating: true` means a failure here makes every LATER rule meaningless, so they are skipped
 * rather than evaluated. One boolean, not a dependency graph - GEO-013 D-2.
 */
export const POLYGON_RULES = [
  {
    key: 'parseable',
    appliesTo: POLYGON_TYPES,
    configKey: 'validateShape',
    gating: true,
    evaluate: (points) => ({
      pass: Array.isArray(points) && points.every(isPair),
    }),
  },
  {
    key: 'minVertices',
    appliesTo: POLYGON_TYPES,
    configKey: 'validateShape',
    gating: true,
    evaluate: (points) => ({
      pass: points.length >= MIN_VERTICES,
      params: { actual: points.length, threshold: MIN_VERTICES },
    }),
  },
  {
    key: 'selfIntersection',
    appliesTo: POLYGON_TYPES,
    configKey: 'validateShape',
    gating: true,
    evaluate: (points) => ({ pass: !selfIntersects(points) }),
  },
  {
    key: 'minArea',
    appliesTo: POLYGON_TYPES,
    configKey: 'validateArea',
    gating: false,
    evaluate: (points) => {
      const actual = polygonArea(points);
      return {
        pass: actual >= MIN_AREA_SQM,
        params: { actual: Math.round(actual), threshold: MIN_AREA_SQM },
      };
    },
  },
  {
    key: 'maxArea',
    appliesTo: POLYGON_TYPES,
    configKey: 'validateArea',
    gating: false,
    /**
     * Inert unless the question authors `maxAreaHa`. Reported in hectares rather than m2 because
     * a ceiling is a land-sized number: "24.3 ha" reads, "243000 m2" does not - the mirror of
     * why the floor reports m2 and not "0.001 ha".
     */
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

const isRealBoolean = (value) => value === true || value === false;

/**
 * Which severity does this rule carry for this question?
 *
 * Question `geoConfig` -> `block`. Then one clamp: an optional question never blocks
 * (GEO-007 D-7), and the clamp only ever DOWNGRADES - `required` does not upgrade a warn.
 *
 * Anything that is not a real boolean - `"true"`, `["true"]`, `1` - is malformed config, not a
 * value, and falls through to `block` rather than straight to `warn`. Failing toward "ask a
 * human" is the posture GEO-010 D-2 sets, and since 2026-09-21 the write boundary refuses those
 * values outright, so this branch guards form versions captured before that check existed.
 *
 * **The device layer is gone (2026-09-21).** GEO-002 D-4 gave the enumerator a switch that
 * downgraded any rule to `warn`, and called it "the weakest of the three layers available,
 * because it is invisible to the programme and travels with the enumerator across every form".
 * Editor 2.0.6 made `validateShape` and `validateArea` authorable, so the programme can now say
 * this per question - and a device-wide toggle silently overriding every form is exactly the
 * invisibility D-4 warned about. Authority moves to the form author.
 *
 * D-4 anticipated this retreat and specified its shape: *"hide the two Settings entries … the
 * stored value stays at its `1` default and every rule resolves to `block`"*. The SQLite columns
 * and migration 11 stay for that reason - the migration is a rung in the version ladder, and
 * removing it would strand any device still on `user_version` 10.
 */
export const resolveSeverity = (rule, question = {}) => {
  if (!question?.required) {
    return SEVERITY.warn;
  }
  const configured = rule.configKey ? question?.extra?.geoConfig?.[rule.configKey] : null;
  if (isRealBoolean(configured)) {
    return configured ? SEVERITY.block : SEVERITY.warn;
  }
  return SEVERITY.block;
};

/**
 * Evaluate every applicable rule and return one result each.
 *
 * A skipped result is NOT a pass: it carries `skipped: true` and the key that gated it, so a
 * report can say "could not check area: the boundary crosses itself" instead of showing a green
 * tick. Returns `[]` when there is no answer to judge.
 */
export const runPolygonRules = (points, question = {}) => {
  if (isNoAnswer(points)) {
    return [];
  }
  return POLYGON_RULES.filter((rule) => rule.appliesTo.includes(question?.type)).reduce(
    (acc, rule) => {
      if (acc.gatedBy) {
        return {
          gatedBy: acc.gatedBy,
          results: [
            ...acc.results,
            { key: rule.key, pass: null, skipped: true, skippedBy: acc.gatedBy, params: {} },
          ],
        };
      }
      const { pass, params = {} } = rule.evaluate(points, {
        geoConfig: question?.extra?.geoConfig,
      });
      return {
        gatedBy: !pass && rule.gating ? rule.key : null,
        results: [
          ...acc.results,
          {
            key: rule.key,
            pass,
            params,
            skipped: false,
            severity: resolveSeverity(rule, question),
          },
        ],
      };
    },
    { results: [], gatedBy: null },
  ).results;
};

const I18N_KEYS = {
  parseable: 'geoRuleParseable',
  minVertices: 'geoRuleMinVertices',
  selfIntersection: 'geoRuleSelfIntersection',
  minArea: 'geoRuleMinArea',
  maxArea: 'geoRuleMaxArea',
};

/**
 * Turn one failed result into a sentence.
 *
 * Takes `trans` as an argument rather than reaching for the store, so the language is whatever
 * is active at RENDER time - a form whose language changes mid-session re-renders its failures
 * in the new language instead of freezing them (GEO-013 D-1).
 *
 * `label` is prepended for surfaces that need to say which question failed - the submit gate,
 * whose Toast shows a bare string with no other context. The inline hint sits directly under
 * the label already, so it passes none (GEO-002 2.1.5).
 */
export const formatRuleFailure = (result, trans = {}, label = null) => {
  const template = trans?.[I18N_KEYS[result?.key]] || '';
  const params = result?.params || {};
  const sentence = Object.keys(params).reduce(
    (text, name) => text.replace(`{${name}}`, params[name]),
    template,
  );
  return label ? `${label}: ${sentence}` : sentence;
};

/**
 * Is the area readout meaningless for this geometry?
 *
 * On a self-crossing ring the shoelace sum is ALGEBRAIC: lobes wound in opposite directions
 * subtract, so a symmetric bowtie spanning kilometres reports ~0 ha. Any surface printing an
 * area must mark it as untrustworthy rather than state it as fact - GEO-003 D-6.
 *
 * Takes results already computed by `runPolygonRules` so no surface pays for a second pass.
 *
 * Twin: `frontend/src/lib/polygon-rules.js`.
 */
export const areaIsAmbiguous = (results = []) =>
  results.some((r) => r.key === 'selfIntersection' && r.pass === false);

/** Failures only - skips are data for the report, not something to show inline (GEO-002 2.1.5). */
export const failedRules = (results = []) => results.filter((r) => !r.skipped && !r.pass);

export const hasBlockingFailure = (results = []) =>
  failedRules(results).some((r) => r.severity === SEVERITY.block);

/**
 * The one blocking string the submit gate needs, or null when nothing blocks.
 *
 * Joined rather than first-only because the list is what makes GEO-007 additive - in phase 1 the
 * gating cascade means it is never longer than one entry anyway (GEO-002 2.1.5).
 */
export const blockingMessage = (results = [], trans = {}, label = null) => {
  const blocking = failedRules(results).filter((r) => r.severity === SEVERITY.block);
  if (!blocking.length) {
    return null;
  }
  return blocking.map((r) => formatRuleFailure(r, trans, label)).join(' ');
};
