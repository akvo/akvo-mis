import { fitBoundsFor, polygonArea, polygonAreaHectares } from '../geometry';

describe('polygonArea', () => {
  it('returns 0 for fewer than three points', () => {
    expect(polygonArea([])).toBe(0);
    expect(polygonArea([[0, 0]])).toBe(0);
    expect(
      polygonArea([
        [0, 0],
        [0, 1],
      ]),
    ).toBe(0);
  });

  it('returns 0 for a non-array value', () => {
    expect(polygonArea(null)).toBe(0);
    expect(polygonArea('')).toBe(0);
  });

  it('measures a square of known size', () => {
    /**
     * At the equator 0.01 degrees is ~1113.2m in both axes, so the square is ~1.239 km2.
     */
    const square = [
      [0, 0],
      [0, 0.01],
      [0.01, 0.01],
      [0.01, 0],
    ];
    expect(polygonArea(square)).toBeCloseTo(1113195 * 1.1132, -4);
    expect(polygonAreaHectares(square)).toBeCloseTo(123.9, 0);
  });

  it('is unaffected by winding direction', () => {
    const clockwise = [
      [0, 0],
      [0, 0.01],
      [0.01, 0.01],
      [0.01, 0],
    ];
    expect(polygonArea([...clockwise].reverse())).toBeCloseTo(polygonArea(clockwise), 5);
  });

  it('narrows with latitude as meridians converge', () => {
    const atEquator = [
      [0, 0],
      [0, 0.01],
      [0.01, 0.01],
      [0.01, 0],
    ];
    const atSixty = atEquator.map(([lat, lng]) => [lat + 60, lng]);
    // cos(60deg) = 0.5, so the same degree-box covers about half the ground.
    expect(polygonArea(atSixty) / polygonArea(atEquator)).toBeCloseTo(0.5, 2);
  });

  /**
   * GEO-001 D-1b: the stored format is ARF's [lat, lng] - latitude first. A silent swap to
   * GeoJSON's [lng, lat] does not crash, it quietly measures the wrong place. The fixture is
   * deliberately asymmetric (near the equator, far from the prime meridian) so a swap changes
   * the answer; a symmetric fixture would pass either way.
   */
  it('reads latitude first - axis-order regression', () => {
    const addisAbabaPlot = [
      [9.03, 38.74],
      [9.03, 38.75],
      [9.04, 38.75],
      [9.04, 38.74],
    ];
    const swapped = addisAbabaPlot.map(([lat, lng]) => [lng, lat]);
    // Read correctly the mean latitude is ~9 (cos ~0.988); swapped it is ~38.7 (cos ~0.781).
    expect(polygonArea(addisAbabaPlot)).toBeGreaterThan(polygonArea(swapped) * 1.2);
    expect(polygonAreaHectares(addisAbabaPlot)).toBeCloseTo(122.4, 0);
  });
});

describe('fitBoundsFor', () => {
  const current = [
    [0.001, 0.001],
    [0.001, 0.002],
    [0.002, 0.002],
  ];
  const worst = [
    [0, 0],
    [0, 0.002],
    [0.002, 0.002],
  ];
  const furthest = [
    [-0.004, 0.001],
    [-0.004, 0.003],
    [-0.001, 0.003],
  ];

  /**
   * The overlap review screen's acceptance criterion: the viewport covers the current polygon
   * AND every conflict. The extremes here belong to neither the current polygon nor the worst
   * conflict, so a fit computed from the current polygon alone - or from the one the error
   * sentence led with - would leave part of the picture off screen.
   */
  it('covers every polygon it is given', () => {
    expect(fitBoundsFor([current, worst, furthest])).toEqual([
      [-0.004, 0],
      [0.002, 0.003],
    ]);
  });

  it('fits a single polygon on its own', () => {
    expect(fitBoundsFor([current])).toEqual([
      [0.001, 0.001],
      [0.002, 0.002],
    ]);
  });

  it('ignores the accuracy element of a measured vertex', () => {
    const walked = current.map(([lat, lng]) => [lat, lng, 12]);
    expect(fitBoundsFor([walked])).toEqual(fitBoundsFor([current]));
  });

  it('is null when there is nothing to fit', () => {
    expect(fitBoundsFor([])).toBe(null);
    expect(fitBoundsFor([[]])).toBe(null);
  });
});
