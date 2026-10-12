import * as FileSystem from 'expo-file-system';
import loadMapDrawHtml from '../map-draw-html';

const TEMPLATE =
  '<div id="map" data-points="{{points}}" data-center="{{center}}" data-readonly="{{readonly}}" data-mylocation="{{myLocation}}" data-closed="{{closed}}" data-tile-url="{{tileUrl}}" data-review="{{review}}" data-conflicts="{{conflicts}}" data-fit-bounds="{{fitBounds}}"></div>';

jest.mock('expo-asset', () => ({
  Asset: {
    loadAsync: jest.fn(() => Promise.resolve([{ localUri: 'mocked-uri' }])),
  },
}));

jest.mock('expo-file-system', () => ({
  readAsStringAsync: jest.fn(),
}));

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

/**
 * Reads an attribute back the way the page does: HTML-decode, then JSON.parse. Asserting the
 * escaped form instead would pin `&quot;` and JSON key order, neither of which is the contract.
 */
const baked = (html, name) => {
  const raw = new RegExp(`data-${name}="([^"]*)"`).exec(html)[1];
  return JSON.parse(raw.replace(/&quot;/g, '"'));
};

describe('loadMapDrawHtml', () => {
  beforeEach(() => {
    FileSystem.readAsStringAsync.mockResolvedValue(TEMPLATE);
  });

  it('leaves no placeholder behind', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(html).not.toContain('{{');
  });

  it('escapes quotes so the JSON survives inside an HTML attribute', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(html).toContain('data-points="[[9.03,38.74],[9.03,38.75],[9.04,38.75]]"');
    expect(html).not.toContain('data-points="["');
  });

  it('keeps latitude first in the baked-in points', async () => {
    const html = await loadMapDrawHtml({ points: [[9.03, 38.74]], center: [0, 0] });
    expect(html).toContain('[[9.03,38.74]]');
  });

  it('defaults to editable', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(html).toContain('data-readonly="false"');
  });

  it('marks the page read-only when asked', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0], readonly: true });
    expect(html).toContain('data-readonly="true"');
  });

  it('bakes in the current position so the blue dot shows before the first bridge message', async () => {
    const html = await loadMapDrawHtml({
      points: triangle,
      center: triangle[0],
      myLocation: [9.03, 38.74, 18.4],
    });
    expect(html).toContain('data-mylocation="[9.03,38.74,18.4]"');
  });

  it('renders no dot when there is no fix yet', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(html).toContain('data-mylocation="null"');
  });

  it('defaults to a closed shape', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(html).toContain('data-closed="true"');
  });

  it('marks a geotrace as an open line', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0], closed: false });
    expect(html).toContain('data-closed="false"');
  });

  /**
   * The page holds no tile URL of its own any more (GEO-008 D-1). Whatever the resolver decided
   * is what gets drawn, so adding offline imagery later is a change in `map-tiles.js` and not a
   * second edit here.
   */
  it('bakes in the tile template the resolver returned', async () => {
    const html = await loadMapDrawHtml({
      points: triangle,
      center: triangle[0],
      tileUrl: 'file:///data/user/0/tiles/{z}/{x}/{y}.jpeg',
    });
    // Quoted, because the page reads it back with JSON.parse - the same round trip the points
    // and myLocation attributes already make.
    expect(html).toContain(
      'data-tile-url="&quot;file:///data/user/0/tiles/{z}/{x}/{y}.jpeg&quot;"',
    );
  });

  it('bakes in no tile layer at all when the resolver found nothing', async () => {
    // The offline case. An empty string would still build a layer and request it; `null` is
    // what tells the page to leave the canvas blank under the polygons.
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0], tileUrl: null });
    expect(html).toContain('data-tile-url="null"');
  });

  it('handles an empty polygon', async () => {
    const html = await loadMapDrawHtml({});
    expect(html).toContain('data-points="[]"');
    expect(html).toContain('data-center="[0,0]"');
  });
});

describe('loadMapDrawHtml for the overlap review screen', () => {
  beforeEach(() => {
    FileSystem.readAsStringAsync.mockResolvedValue(TEMPLATE);
  });

  const conflicts = [
    {
      label: '#1',
      coordinates: [
        [9.04, 38.75],
        [9.04, 38.76],
        [9.05, 38.76],
      ],
    },
  ];

  it('is not the review screen unless asked', async () => {
    // Capture and the detail preview must keep drawing exactly what they draw today: one
    // polygon, no labels, no scale bar, and a map click that still places a vertex.
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(html).toContain('data-review="false"');
    expect(baked(html, 'conflicts')).toEqual([]);
  });

  it('bakes in the conflicting polygons with the labels the error text used', async () => {
    const html = await loadMapDrawHtml({
      points: triangle,
      center: triangle[0],
      review: true,
      conflicts,
    });
    expect(html).toContain('data-review="true"');
    expect(baked(html, 'conflicts')).toEqual(conflicts);
  });

  /**
   * Baked rather than computed in the page, so "the viewport covers every polygon" stays an
   * ordinary assertion (GEO-008 §9). A fit around the current polygon alone would leave the
   * neighbour that overlaps it off the edge - and the overlap is the whole subject.
   */
  it('bakes in the viewport that covers all of them', async () => {
    const html = await loadMapDrawHtml({
      points: triangle,
      center: triangle[0],
      review: true,
      conflicts,
      fitBounds: [
        [9.03, 38.74],
        [9.05, 38.76],
      ],
    });
    expect(baked(html, 'fit-bounds')).toEqual([
      [9.03, 38.74],
      [9.05, 38.76],
    ]);
  });

  it('falls back to the current polygon when no bounds were given', async () => {
    const html = await loadMapDrawHtml({ points: triangle, center: triangle[0] });
    expect(baked(html, 'fit-bounds')).toBe(null);
  });
});
