import { UIState } from '../store';

/**
 * The one place a tile URL is decided.
 *
 * Every map surface in the app — capture, the detail preview, overlap review — takes its
 * template from here and nowhere else, so the hardcoded `tile.openstreetmap.org` line that used
 * to sit in `map-draw.html` is gone. GEO-008 D-1.
 */
export const TILE_SOURCE = {
  /** A pack downloaded onto the device. Path B; not shipped yet. */
  local: 'local',
  network: 'network',
  /** No tiles at all. The polygons still render on a blank canvas. */
  none: 'none',
};

/**
 * OpenStreetMap *street* tiles, which is what the app has always drawn. GEO-008's "satellite
 * basemap when online" needs a licensed provider, and that is the same vendor conversation as
 * offline redistribution (`doc/claude/offline-satellite-imagery-plan.md` §12.3) — swapping the
 * template here is the whole of that change.
 */
export const NETWORK_TILE_TEMPLATE = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/**
 * Path A: the local branch of the resolution order, stubbed to always miss.
 *
 * Injected rather than inlined so the order itself is testable today, and so Phase 3 replaces a
 * default argument instead of unpicking an `if (false)`.
 */
const noLocalPack = () => null;

/**
 * Local pack → network → nothing, in that order (imagery plan §7).
 *
 * The order is the seam. A pack wins even when the device is online, because a tile already on
 * the device is free; the network is next; and only when both miss is there no imagery at all.
 *
 * @returns {{ kind: string, template: string|null, hasTiles: boolean }}
 */
export const resolveTileSource = ({
  bounds = null,
  online = false,
  findLocalPack = noLocalPack,
} = {}) => {
  const local = findLocalPack(bounds);
  if (local?.template) {
    return { kind: TILE_SOURCE.local, template: local.template, hasTiles: true };
  }
  if (online) {
    return { kind: TILE_SOURCE.network, template: NETWORK_TILE_TEMPLATE, hasTiles: true };
  }
  return { kind: TILE_SOURCE.none, template: null, hasTiles: false };
};

/**
 * The resolver as the screens call it, against the connectivity `App.js` already tracks.
 *
 * **The offline notice reads this verdict, never `UIState.online` directly.** A device can be
 * offline and still have imagery the moment packs exist, and a connectivity check would keep
 * claiming otherwise (D-1).
 *
 * Async although nothing here awaits yet: Phase 3's pack lookup reads a manifest, and making
 * every caller add an `await` then would touch three screens for a signature that was always
 * going to be async.
 */
export const currentTileSource = async ({ bounds = null, findLocalPack } = {}) =>
  resolveTileSource({
    bounds,
    online: Boolean(UIState.getRawState()?.online),
    ...(findLocalPack ? { findLocalPack } : {}),
  });
