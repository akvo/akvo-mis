import {
  DEFAULT_OVERLAP_CEILING,
  DEFAULT_OVERLAP_FLOOR,
  adaptiveThreshold,
  answerKey,
  detectOverlapsEnabled,
  intersectionArea,
  overlapPercent,
  signatureOf,
} from '../overlap';

/** ~111 m on a side at the equator, so a hectare-scale plot without magic numbers. */
const square = (west, east) => [
  [0, west],
  [0, east],
  [0.001, east],
  [0.001, west],
];

const PLOT = square(0, 0.001);

describe('overlapPercent', () => {
  it('reports 100 % for identical polygons', () => {
    expect(overlapPercent(PLOT, PLOT)).toBeCloseTo(100, 1);
  });

  it('reports 0 % for disjoint polygons', () => {
    const elsewhere = [
      [1, 1],
      [1, 1.001],
      [1.001, 1.001],
      [1.001, 1],
    ];
    expect(overlapPercent(PLOT, elsewhere)).toBe(0);
    expect(intersectionArea(PLOT, elsewhere)).toBe(0);
  });

  it('is a percentage of the SMALLER polygon, not of the new one', () => {
    // A tenth the width, entirely inside the big plot: fully swallowed, so 100 % of itself.
    const sliver = square(0.0002, 0.0003);
    expect(overlapPercent(PLOT, sliver)).toBeCloseTo(100, 0);
  });

  it('measures partial overlap along a shared edge', () => {
    expect(overlapPercent(PLOT, square(0.0005, 0.0015))).toBeCloseTo(50, 0);
  });

  it('returns 0 rather than throwing on a degenerate answer', () => {
    expect(overlapPercent([], PLOT)).toBe(0);
    expect(overlapPercent([[0, 0]], PLOT)).toBe(0);
  });
});

describe('adaptiveThreshold', () => {
  const HECTARE = 10000;
  const combined = { accA: 15, accB: 15 }; // 30 m combined, the figure in GEO-007 D-3

  it('clamps to the authored ceiling on a small plot', () => {
    // 1 ha computes 30 %, which the ceiling must cut back to 20 - otherwise a small plot
    // becomes unfailable, the fail-open GEO-005 exists to prevent.
    const { threshold } = adaptiveThreshold({
      ...combined,
      areaA: HECTARE,
      areaB: HECTARE,
    });
    expect(threshold).toBe(DEFAULT_OVERLAP_CEILING);
  });

  it('tightens below the ceiling on a large plot', () => {
    const { threshold, adaptive } = adaptiveThreshold({
      ...combined,
      areaA: 10 * HECTARE,
      areaB: 10 * HECTARE,
    });
    expect(adaptive).toBe(true);
    expect(threshold).toBeCloseTo(9.49, 1);
    expect(threshold).toBeLessThan(DEFAULT_OVERLAP_CEILING);
  });

  it('never drops below the floor', () => {
    const { threshold } = adaptiveThreshold({
      ...combined,
      areaA: 50 * HECTARE,
      areaB: 50 * HECTARE,
    });
    // 50 ha computes 4.24 %, below the 5 % floor.
    expect(threshold).toBe(DEFAULT_OVERLAP_FLOOR);
  });

  it('falls back to the ceiling when either polygon has no measured accuracy', () => {
    expect(adaptiveThreshold({ accA: 15, accB: null, areaA: HECTARE, areaB: HECTARE })).toEqual({
      threshold: DEFAULT_OVERLAP_CEILING,
      adaptive: false,
    });
    expect(adaptiveThreshold({ accA: null, accB: 15, areaA: HECTARE, areaB: HECTARE })).toEqual({
      threshold: DEFAULT_OVERLAP_CEILING,
      adaptive: false,
    });
  });

  it('can never be more permissive than the authored ceiling', () => {
    // The guarantee that makes this safe to ship: no existing configuration changes meaning.
    const areas = [0.01, 0.1, 1, 10, 50, 500].map((ha) => ha * HECTARE);
    areas.forEach((area) => {
      const { threshold } = adaptiveThreshold({
        accA: 50,
        accB: 50,
        areaA: area,
        areaB: area,
        geoConfig: { overlapThreshold: 12, overlapThresholdFloor: 3 },
      });
      expect(threshold).toBeLessThanOrEqual(12);
    });
  });

  it('honours an authored ceiling and floor', () => {
    const { threshold } = adaptiveThreshold({
      accA: 15,
      accB: 15,
      areaA: 10 * HECTARE,
      areaB: 10 * HECTARE,
      geoConfig: { overlapThreshold: 8, overlapThresholdFloor: 2 },
    });
    expect(threshold).toBe(8);
  });

  it('falls back to the ceiling on a zero-area polygon instead of dividing by zero', () => {
    const { threshold, adaptive } = adaptiveThreshold({
      accA: 5,
      accB: 5,
      areaA: 0,
      areaB: HECTARE,
    });
    expect(adaptive).toBe(false);
    expect(threshold).toBe(DEFAULT_OVERLAP_CEILING);
  });
});

describe('helpers', () => {
  it('keys repeat 0 bare and later repeats with a suffix', () => {
    expect(answerKey(987, 0)).toBe('987');
    expect(answerKey(987)).toBe('987');
    expect(answerKey(987, 2)).toBe('987-2');
  });

  it('treats only a real boolean true as detection enabled', () => {
    expect(detectOverlapsEnabled({ extra: { geoConfig: { detectOverlaps: true } } })).toBe(true);
    expect(detectOverlapsEnabled({ extra: { geoConfig: { detectOverlaps: 'true' } } })).toBe(false);
    expect(detectOverlapsEnabled({ extra: {} })).toBe(false);
    expect(detectOverlapsEnabled(null)).toBe(false);
  });

  it('changes signature when a single vertex moves', () => {
    const moved = [...PLOT.slice(0, 3), [0.001, 0.0009]];
    expect(signatureOf(PLOT)).not.toBe(signatureOf(moved));
    expect(signatureOf(PLOT)).toBe(signatureOf([...PLOT]));
  });
});
