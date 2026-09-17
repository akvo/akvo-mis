import {
  areaIsAmbiguous,
  MIN_AREA_SQM,
  MIN_VERTICES,
  POLYGON_RULES,
  SEVERITY,
  failedRules,
  hasBlockingFailure,
  isNoAnswer,
  resolveSeverity,
  runPolygonRules,
} from '../polygon-rules';
import { toGeoJsonRing, selfIntersects, polygonAreaHectares } from '../geometry';
import { QUESTION_TYPES } from '../../../lib/constants';

// A metre of latitude is ~1/111320 of a degree. Squares built from this are used to hit the
// area threshold from both sides without depending on the projection's exact output.
const M = 1 / 111320;
const squareOfSide = (metres, lat = 0) => {
  const d = metres * M;
  return [
    [lat, 0],
    [lat, d],
    [lat + d, d],
    [lat + d, 0],
  ];
};

const TRIANGLE = [
  [0, 0],
  [0, 0.01],
  [0.01, 0],
];
const BOWTIE = [
  [0, 0],
  [0.01, 0.01],
  [0.01, 0],
  [0, 0.01],
];

const question = (overrides = {}) => ({
  id: 1,
  type: QUESTION_TYPES.geoshape,
  required: true,
  ...overrides,
});

const byKey = (results, key) => results.find((r) => r.key === key);

describe('thresholds', () => {
  /**
   * Looks tautological, is not. `frontend/src/lib/polygon-rules.js` holds the same two numbers
   * and nothing links the files. Changing one side turns this red, and the failing diff is what
   * reminds the author the twin exists. GEO-013 D-3.
   */
  it('match the values the frontend twin must also carry', () => {
    expect(MIN_VERTICES).toBe(3);
    expect(MIN_AREA_SQM).toBe(10);
  });
});

describe('toGeoJsonRing', () => {
  it('swaps to lng-first and closes the ring', () => {
    // lat and lng are deliberately different magnitudes: a transposition cannot pass quietly.
    const ring = toGeoJsonRing([
      [7, 110],
      [8, 111],
      [9, 112],
    ]);
    expect(ring).toEqual([
      [110, 7],
      [111, 8],
      [112, 9],
      [110, 7],
    ]);
  });

  it('does not double-close an already closed ring', () => {
    const ring = toGeoJsonRing([
      [7, 110],
      [8, 111],
      [7, 110],
    ]);
    expect(ring).toHaveLength(3);
  });
});

describe('selfIntersects', () => {
  it('is false for a simple triangle and true for a bowtie', () => {
    expect(selfIntersects(TRIANGLE)).toBe(false);
    expect(selfIntersects(BOWTIE)).toBe(true);
  });

  it('is false below three points rather than throwing', () => {
    expect(selfIntersects([[0, 0]])).toBe(false);
    expect(selfIntersects([])).toBe(false);
  });
});

describe('isNoAnswer', () => {
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['cleared', []],
  ])('treats %s as an absence', (_label, value) => {
    expect(isNoAnswer(value)).toBe(true);
  });

  it('treats any drawn geometry as an answer', () => {
    expect(isNoAnswer(TRIANGLE)).toBe(false);
  });
});

describe('runPolygonRules', () => {
  it('returns nothing at all when there is no answer', () => {
    expect(runPolygonRules(null, question())).toEqual([]);
    expect(runPolygonRules([], question())).toEqual([]);
  });

  it('passes a three-vertex triangle - the MIN_VERTICES = 4 regression guard (GEO-002 D-2)', () => {
    const results = runPolygonRules(TRIANGLE, question());
    expect(results.every((r) => r.pass)).toBe(true);
    expect(failedRules(results)).toHaveLength(0);
  });

  it('exempts geotrace entirely', () => {
    expect(runPolygonRules(BOWTIE, question({ type: QUESTION_TYPES.geotrace }))).toEqual([]);
  });

  it('fails an unparseable value and SKIPS every later rule', () => {
    const results = runPolygonRules(['nonsense'], question());
    expect(byKey(results, 'parseable').pass).toBe(false);
    ['minVertices', 'selfIntersection', 'minArea'].forEach((key) => {
      expect(byKey(results, key)).toMatchObject({ skipped: true, skippedBy: 'parseable' });
      expect(byKey(results, key).pass).not.toBe(true);
    });
  });

  it('fails two points and skips the measurements', () => {
    const results = runPolygonRules(
      [
        [0, 0],
        [0, 0.01],
      ],
      question(),
    );
    expect(byKey(results, 'minVertices')).toMatchObject({
      pass: false,
      params: { actual: 2, threshold: 3 },
    });
    expect(byKey(results, 'minArea').skipped).toBe(true);
  });

  it('skips the area check on a bowtie, because its area is ambiguous', () => {
    const results = runPolygonRules(BOWTIE, question());
    expect(byKey(results, 'selfIntersection').pass).toBe(false);
    expect(byKey(results, 'minArea')).toMatchObject({
      skipped: true,
      skippedBy: 'selfIntersection',
    });
  });

  it('reports at most one failure in phase 1 (GEO-002 2.1.5)', () => {
    [
      ['nonsense'],
      [
        [0, 0],
        [0, 0.01],
      ],
      BOWTIE,
      squareOfSide(2),
    ].forEach((points) => {
      expect(failedRules(runPolygonRules(points, question())).length).toBeLessThanOrEqual(1);
    });
  });
});

describe('minArea threshold', () => {
  it('fails below 10 m2 and passes above it', () => {
    expect(byKey(runPolygonRules(squareOfSide(2), question()), 'minArea').pass).toBe(false);
    expect(byKey(runPolygonRules(squareOfSide(4), question()), 'minArea').pass).toBe(true);
  });

  it.each([0, 25, 51])('holds at latitude %i', (lat) => {
    expect(byKey(runPolygonRules(squareOfSide(2, lat), question()), 'minArea').pass).toBe(false);
    expect(byKey(runPolygonRules(squareOfSide(4, lat), question()), 'minArea').pass).toBe(true);
  });
});

describe('maxArea (GEO-003 D-5)', () => {
  const withCeiling = (maxAreaHa) => question({ extra: { geoConfig: { maxAreaHa } } });

  it('is inert when no ceiling is authored - the default for every existing form', () => {
    // A square roughly 1 km on a side: far beyond any plot, and still fine without a ceiling.
    const huge = squareOfSide(1000);
    expect(byKey(runPolygonRules(huge, question()), 'maxArea').pass).toBe(true);
    expect(failedRules(runPolygonRules(huge, question()))).toHaveLength(0);
  });

  it('fails a shape above the authored ceiling and passes one below it', () => {
    // 200 m x 200 m = 4 ha.
    const fourHectares = squareOfSide(200);
    expect(byKey(runPolygonRules(fourHectares, withCeiling(2)), 'maxArea').pass).toBe(false);
    expect(byKey(runPolygonRules(fourHectares, withCeiling(20)), 'maxArea').pass).toBe(true);
  });

  it('reports hectares, not square metres', () => {
    const results = runPolygonRules(squareOfSide(200), withCeiling(2));
    const { params } = byKey(results, 'maxArea');
    expect(params.threshold).toBe(2);
    expect(params.actual).toBeCloseTo(4, 1);
  });

  it.each([
    ['a quoted number', '20'],
    ['zero', 0],
    ['a negative', -5],
    ['nonsense', 'big'],
  ])('ignores %s rather than guessing a ceiling', (_label, value) => {
    expect(byKey(runPolygonRules(squareOfSide(1000), withCeiling(value)), 'maxArea').pass).toBe(
      true,
    );
  });

  it('cannot fail at the same time as minArea, so the count stays at one', () => {
    [squareOfSide(2), squareOfSide(200)].forEach((points) => {
      expect(failedRules(runPolygonRules(points, withCeiling(2))).length).toBeLessThanOrEqual(1);
    });
  });

  it('is skipped behind a failing structural rule like the floor is', () => {
    const results = runPolygonRules(BOWTIE, withCeiling(0.0001));
    expect(byKey(results, 'maxArea')).toMatchObject({
      skipped: true,
      skippedBy: 'selfIntersection',
    });
  });
});

describe('areaIsAmbiguous (GEO-003 D-6)', () => {
  /**
   * The number this pins is the entire justification for gating the area checks behind the
   * self-intersection check. Nothing else in the suite would notice if it stopped being true.
   *
   * The shoelace sum is ALGEBRAIC: lobes wound in opposite directions subtract. A symmetric
   * bowtie spanning kilometres therefore reports ~0 - so without gating, a 300-hectare shape
   * could be rejected for being "below the 10 m2 minimum".
   */
  it('a symmetric bowtie reports ~0 area despite spanning kilometres', () => {
    const d = 0.02; // ~2.2 km
    const symmetricBowtie = [
      [0, 0],
      [d, d],
      [d, 0],
      [0, d],
    ];
    const square = [
      [0, 0],
      [0, d],
      [d, d],
      [d, 0],
    ];
    expect(polygonAreaHectares(square)).toBeGreaterThan(400);
    expect(polygonAreaHectares(symmetricBowtie)).toBeLessThan(1);
  });

  it('flags the area as ambiguous exactly when the ring crosses itself', () => {
    expect(areaIsAmbiguous(failedRules(runPolygonRules(BOWTIE, question())))).toBe(true);
    expect(areaIsAmbiguous(failedRules(runPolygonRules(TRIANGLE, question())))).toBe(false);
  });

  it('says nothing about an unanswered question', () => {
    expect(areaIsAmbiguous(runPolygonRules(null, question()))).toBe(false);
  });
});

describe('resolveSeverity', () => {
  const [shapeRule] = POLYGON_RULES;

  it('defaults to block when nothing is configured', () => {
    expect(resolveSeverity(shapeRule, question(), {})).toBe(SEVERITY.block);
  });

  it('lets geoConfig outrank the device setting, both ways', () => {
    const settings = { validatePolygonShape: 0 };
    const on = question({ extra: { geoConfig: { validateShape: true } } });
    const off = question({ extra: { geoConfig: { validateShape: false } } });
    expect(resolveSeverity(shapeRule, on, settings)).toBe(SEVERITY.block);
    expect(resolveSeverity(shapeRule, off, { validatePolygonShape: 1 })).toBe(SEVERITY.warn);
  });

  it('falls back to the device setting when geoConfig is absent', () => {
    expect(resolveSeverity(shapeRule, question(), { validatePolygonShape: 0 })).toBe(SEVERITY.warn);
    expect(resolveSeverity(shapeRule, question(), { validatePolygonShape: 1 })).toBe(
      SEVERITY.block,
    );
  });

  it.each([
    ['a quoted string', 'true'],
    ['an array', ['true']],
    ['a number', 1],
    ['a quoted false', 'false'],
  ])('treats %s as malformed and falls through, never straight to warn', (_label, value) => {
    const q = question({ extra: { geoConfig: { validateShape: value } } });
    expect(resolveSeverity(shapeRule, q, {})).toBe(SEVERITY.block);
    expect(resolveSeverity(shapeRule, q, { validatePolygonShape: 0 })).toBe(SEVERITY.warn);
  });

  it('clamps an optional question to warn, whatever the config says', () => {
    const q = question({ required: false, extra: { geoConfig: { validateShape: true } } });
    expect(resolveSeverity(shapeRule, q, { validatePolygonShape: 1 })).toBe(SEVERITY.warn);
  });

  it('never upgrades: the switch off warns even on a required question (GEO-002 D-4)', () => {
    const results = runPolygonRules(BOWTIE, question(), { validatePolygonShape: 0 });
    expect(byKey(results, 'selfIntersection').severity).toBe(SEVERITY.warn);
    expect(hasBlockingFailure(results)).toBe(false);
  });

  it('blocks that same polygon in the default configuration', () => {
    expect(hasBlockingFailure(runPolygonRules(BOWTIE, question(), {}))).toBe(true);
  });
});
