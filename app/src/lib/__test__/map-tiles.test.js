import { UIState } from '../../store';
import {
  NETWORK_TILE_TEMPLATE,
  TILE_SOURCE,
  currentTileSource,
  resolveTileSource,
} from '../map-tiles';

const BOUNDS = { minLat: 8.9, maxLat: 9.1, minLon: 38.7, maxLon: 38.9 };

/** Stands in for Phase 3's pack lookup. Path A ships the always-missing stub below. */
const packFinder = (template) => () => ({ template });

describe('resolveTileSource', () => {
  it('serves a stored pack in preference to the network', () => {
    // Online and offline alike: a downloaded pack is the point of downloading it, and paying
    // for a tile that is already on the device would be the bug FR-B5 exists to prevent.
    const resolved = resolveTileSource({
      bounds: BOUNDS,
      online: true,
      findLocalPack: packFinder('file:///tiles/{z}/{x}/{y}.jpeg'),
    });
    expect(resolved.kind).toBe(TILE_SOURCE.local);
    expect(resolved.template).toBe('file:///tiles/{z}/{x}/{y}.jpeg');
    expect(resolved.hasTiles).toBe(true);
  });

  it('falls back to the network when nothing is stored for the viewport', () => {
    const resolved = resolveTileSource({ bounds: BOUNDS, online: true });
    expect(resolved.kind).toBe(TILE_SOURCE.network);
    expect(resolved.template).toBe(NETWORK_TILE_TEMPLATE);
    expect(resolved.hasTiles).toBe(true);
  });

  /**
   * This verdict, not a connectivity check, is what the "imagery unavailable" notice reads
   * (GEO-008 D-1). An `isConnected` test would still say "unavailable" on a device holding a
   * full pack, which is the day Path B ships.
   */
  it('reports no tiles when offline with nothing stored', () => {
    const resolved = resolveTileSource({ bounds: BOUNDS, online: false });
    expect(resolved.kind).toBe(TILE_SOURCE.none);
    expect(resolved.template).toBe(null);
    expect(resolved.hasTiles).toBe(false);
  });
});

describe('currentTileSource', () => {
  it('reads the connectivity the app already tracks', async () => {
    UIState.update((s) => {
      s.online = false;
    });
    expect((await currentTileSource({ bounds: BOUNDS })).kind).toBe(TILE_SOURCE.none);

    UIState.update((s) => {
      s.online = true;
    });
    expect((await currentTileSource({ bounds: BOUNDS })).kind).toBe(TILE_SOURCE.network);
  });

  it('ships with the local branch always missing', async () => {
    // Path A. When a pack lookup lands in Phase 3 this is the one line that changes.
    UIState.update((s) => {
      s.online = true;
    });
    const resolved = await currentTileSource({ bounds: BOUNDS });
    expect(resolved.kind).not.toBe(TILE_SOURCE.local);
  });
});
