import { readFileSync } from 'fs';
import { join } from 'path';

import loadMapDrawHtml from '../map-draw-html';

/**
 * The real bundled page, not the stub the other suites load.
 *
 * `String.replace` on a placeholder that is not there is a silent no-op, so an attribute renamed
 * in the HTML ships a page that draws nothing and fails no test that mocks the asset away. These
 * are the only assertions in the app that read the file Jest actually bundles.
 *
 * The `mock` prefix is not cosmetic: jest.mock factories may not close over ordinary locals.
 */
const mockPage = readFileSync(join(__dirname, '../../../assets/map-draw.html'), 'utf8');

jest.mock('expo-asset', () => ({
  Asset: {
    loadAsync: jest.fn(() => Promise.resolve([{ localUri: 'the-real-page' }])),
  },
}));

jest.mock('expo-file-system', () => ({
  readAsStringAsync: jest.fn(() => Promise.resolve(mockPage)),
}));

describe('the bundled map page', () => {
  /**
   * GEO-008 D-1: one resolver decides the tile source. A provider named in the page is a second
   * decision point, and the one that survives a refactor of `map-tiles.js` unnoticed.
   */
  it('names no tile provider of its own', () => {
    expect(mockPage).not.toMatch(/tile\.openstreetmap\.org/);
    expect(mockPage).toMatch(/data-tile-url="\{\{tileUrl\}\}"/);
  });

  it('has a slot for every value the loader bakes in', async () => {
    const html = await loadMapDrawHtml({
      points: [
        [0, 0],
        [0, 1],
        [1, 1],
      ],
      center: [0, 0],
      readonly: true,
      accuracyThreshold: 15,
      tileUrl: null,
    });
    expect(html).not.toContain('{{');
  });
});
