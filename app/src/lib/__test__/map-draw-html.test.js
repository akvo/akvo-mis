import * as FileSystem from 'expo-file-system';
import loadMapDrawHtml from '../map-draw-html';

const TEMPLATE =
  '<div id="map" data-points="{{points}}" data-center="{{center}}" data-readonly="{{readonly}}" data-mylocation="{{myLocation}}" data-closed="{{closed}}"></div>';

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

  it('handles an empty polygon', async () => {
    const html = await loadMapDrawHtml({});
    expect(html).toContain('data-points="[]"');
    expect(html).toContain('data-center="[0,0]"');
  });
});
