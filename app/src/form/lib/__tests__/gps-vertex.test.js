import {
  ACCURACY_OPTIONS,
  DEFAULT_ACCURACY_THRESHOLD,
  DEFAULT_INTERVAL_SECONDS,
  INTERVAL_OPTIONS,
  LOCK_MAX_AGE_MS,
  accuracyThreshold,
  configuredAccuracyThreshold,
  formatInterval,
  hasSatelliteLock,
  isPoorVertex,
  poorVertexCount,
  selectableAccuracyOptions,
  tappingAllowed,
  toVertex,
  vertexAccuracy,
} from '../gps-vertex';

const fix = (accuracy) => ({ latitude: 9.03, longitude: 38.74, accuracy });

describe('toVertex', () => {
  it('writes accuracy as the optional third element', () => {
    expect(toVertex(fix(4.2))).toEqual([9.03, 38.74, 4.2]);
  });

  it('omits the third element rather than writing 0', () => {
    /**
     * The backend refuses a literal 0 outright: ODK spells "not measured" that way and the
     * adaptive overlap threshold would read it as perfect precision. Some Android devices do
     * report 0, so writing it through would 400 the submission and revert it to a draft.
     */
    expect(toVertex(fix(0))).toEqual([9.03, 38.74]);
  });

  it('omits the third element for a negative or non-finite reading', () => {
    expect(toVertex(fix(-1))).toEqual([9.03, 38.74]);
    expect(toVertex(fix(NaN))).toEqual([9.03, 38.74]);
    expect(toVertex(fix(undefined))).toEqual([9.03, 38.74]);
    expect(toVertex(fix('wide'))).toEqual([9.03, 38.74]);
  });

  it('returns null when there is no usable position', () => {
    // Callers skip rather than appending [undefined, undefined], which would reach the
    // backend as a non-numeric pair and be refused for the whole ring.
    expect(toVertex(undefined)).toBeNull();
    expect(toVertex({ latitude: 9.03 })).toBeNull();
    expect(toVertex({ latitude: 'x', longitude: 38.74 })).toBeNull();
  });

  it('keeps latitude first, matching the stored format', () => {
    const [lat, lng] = toVertex(fix(5));
    expect(lat).toBe(9.03);
    expect(lng).toBe(38.74);
  });
});

describe('vertexAccuracy', () => {
  it('reads the third element', () => {
    expect(vertexAccuracy([9.03, 38.74, 6.5])).toBe(6.5);
  });

  it('is null for a tapped vertex', () => {
    expect(vertexAccuracy([9.03, 38.74])).toBeNull();
  });

  it('is null for a 0 or malformed third element', () => {
    expect(vertexAccuracy([9.03, 38.74, 0])).toBeNull();
    expect(vertexAccuracy([9.03, 38.74, null])).toBeNull();
    expect(vertexAccuracy('nonsense')).toBeNull();
  });
});

describe('isPoorVertex', () => {
  it('marks a fix worse than the threshold', () => {
    expect(isPoorVertex([9.03, 38.74, 40], 15)).toBe(true);
  });

  it('leaves a fix at or under the threshold alone', () => {
    expect(isPoorVertex([9.03, 38.74, 15], 15)).toBe(false);
    expect(isPoorVertex([9.03, 38.74, 4.2], 15)).toBe(false);
  });

  it('never marks a tapped vertex', () => {
    /**
     * A tapped vertex makes no claim about accuracy, so it has nothing to fail. Marking it
     * would tell the enumerator to re-walk a point that was never walked.
     */
    expect(isPoorVertex([9.03, 38.74], 15)).toBe(false);
  });

  it('defaults to ARF’s 15 m', () => {
    expect(isPoorVertex([9.03, 38.74, 16])).toBe(true);
    expect(isPoorVertex([9.03, 38.74, 14])).toBe(false);
    expect(DEFAULT_ACCURACY_THRESHOLD).toBe(15);
  });
});

describe('poorVertexCount', () => {
  it('counts only the measured vertices that are too poor', () => {
    const mixed = [
      [9.03, 38.74, 4.2],
      [9.04, 38.74],
      [9.04, 38.75, 40],
      [9.03, 38.75, 32],
    ];
    expect(poorVertexCount(mixed, 15)).toBe(2);
  });

  it('is 0 for an empty or malformed list', () => {
    expect(poorVertexCount([], 15)).toBe(0);
    expect(poorVertexCount(undefined, 15)).toBe(0);
  });
});

describe('accuracyThreshold', () => {
  it('reads the per-question value when the form sets one', () => {
    expect(accuracyThreshold({ geoConfig: { accuracyThreshold: 8 } })).toBe(8);
  });

  it('falls back to 15 m when absent or nonsensical', () => {
    expect(accuracyThreshold(null)).toBe(15);
    expect(accuracyThreshold({})).toBe(15);
    expect(accuracyThreshold({ geoConfig: {} })).toBe(15);
    expect(accuracyThreshold({ geoConfig: { accuracyThreshold: 0 } })).toBe(15);
    expect(accuracyThreshold({ geoConfig: { accuracyThreshold: '20' } })).toBe(20);
  });
});

describe('hasSatelliteLock', () => {
  const now = 1_700_000_000_000;

  it('is true for a recent fix', () => {
    expect(hasSatelliteLock({ coords: fix(30), timestamp: now - 1000 }, now)).toBe(true);
  });

  it('does not require a GOOD fix, only a fix', () => {
    /**
     * Requiring accuracy under the threshold would refuse to start under canopy, which is
     * where boundaries are walked, and would contradict D-1 - poor fixes are recorded and
     * marked, not prevented.
     */
    expect(hasSatelliteLock({ coords: fix(120), timestamp: now }, now)).toBe(true);
  });

  it('is false with no fix at all', () => {
    expect(hasSatelliteLock(null, now)).toBe(false);
    expect(hasSatelliteLock({}, now)).toBe(false);
    expect(hasSatelliteLock({ coords: fix(0) }, now)).toBe(false);
  });

  it('is false for a stale fix', () => {
    const stale = { coords: fix(5), timestamp: now - LOCK_MAX_AGE_MS - 1 };
    expect(hasSatelliteLock(stale, now)).toBe(false);
  });

  it('tolerates a fix as old as Home.js\u2019s 60 s refresh cadence', () => {
    /**
     * Regression. The window was 30 s - HALF the `buildParams.gpsInterval` that refreshes the
     * shared fix this screen falls back to. The last fix was therefore stale more often than
     * not, and Start read as permanently dead with nothing on screen explaining why.
     */
    expect(LOCK_MAX_AGE_MS).toBeGreaterThan(60000);
    const oneMinuteOld = { coords: fix(12), timestamp: now - 60000 };
    expect(hasSatelliteLock(oneMinuteOld, now)).toBe(true);
  });

  it('accepts a fix carrying no timestamp', () => {
    // Staleness cannot be judged, and refusing on that basis is a dead button for a reason
    // the enumerator cannot act on.
    expect(hasSatelliteLock({ coords: fix(5) }, now)).toBe(true);
  });
});

describe('ODK parity of the option lists', () => {
  it('offers ODK\u2019s recording intervals, in ODK\u2019s order', () => {
    // 1s, 5s, 10s, 20s, 30s, 1min, 5min, 10min, 20min, 30min - the list an enumerator sees in
    // ODK Collect. Parity is the whole point: they move between the two apps.
    expect(INTERVAL_OPTIONS).toEqual([1, 5, 10, 20, 30, 60, 300, 600, 1200, 1800]);
  });

  it('offers ODK\u2019s accuracy values, with None first', () => {
    expect(ACCURACY_OPTIONS).toEqual([null, 3, 5, 10, 15, 20]);
  });

  it('keeps our defaults rather than ODK\u2019s 20 s / 10 m', () => {
    // A default carries no transition cost - the control's position does.
    expect(DEFAULT_INTERVAL_SECONDS).toBe(10);
    expect(DEFAULT_ACCURACY_THRESHOLD).toBe(15);
  });
});

describe('formatInterval', () => {
  const trans = { gpsIntervalSeconds: '{count} seconds', gpsIntervalMinutes: '{count} mins' };

  it('reads seconds below a minute and minutes above it', () => {
    expect(formatInterval(20, trans)).toBe('20 seconds');
    expect(formatInterval(60, trans)).toBe('1 mins');
    expect(formatInterval(1800, trans)).toBe('30 mins');
  });
});

describe('selectableAccuracyOptions', () => {
  it('offers everything, None included, when the form has no opinion', () => {
    expect(selectableAccuracyOptions(null)).toEqual([null, 3, 5, 10, 15, 20]);
  });

  it('withdraws None and every looser value once the form sets a threshold', () => {
    /**
     * The form's value is a ceiling, not just a default (GEO-004 D-7). In phase 3 the same
     * number blocks submission, so an unrestricted dropdown would let the gate be switched off
     * from inside the screen it gates.
     */
    expect(selectableAccuracyOptions(10)).toEqual([3, 5, 10]);
    expect(selectableAccuracyOptions(3)).toEqual([3]);
  });

  it('adds a ceiling that is not on ODK\u2019s list rather than rounding it away', () => {
    // A form asking for 7 m must be exactly choosable, or the enumerator cannot comply with it.
    expect(selectableAccuracyOptions(7)).toEqual([3, 5, 7]);
  });

  it('never leaves the list empty', () => {
    expect(selectableAccuracyOptions(1)).toEqual([1]);
  });
});

describe('configuredAccuracyThreshold', () => {
  it('separates "the form set 15" from "the form set nothing"', () => {
    // Both produce a threshold of 15, but only one of them caps the dropdown.
    expect(configuredAccuracyThreshold({ geoConfig: { accuracyThreshold: 15 } })).toBe(15);
    expect(configuredAccuracyThreshold({})).toBeNull();
    expect(accuracyThreshold({})).toBe(15);
  });
});

describe('None means no marking', () => {
  it('flags nothing when the threshold is null', () => {
    /**
     * Without an explicit branch, `metres > null` coerces to `metres > 0` and every measured
     * vertex turns red - the loosest setting producing the loudest screen.
     */
    expect(isPoorVertex([9.03, 38.74, 120], null)).toBe(false);
    expect(
      poorVertexCount(
        [
          [9.03, 38.74, 120],
          [9.04, 38.74, 80],
        ],
        null,
      ),
    ).toBe(0);
  });
});

describe('tappingAllowed', () => {
  it('allows tapping unless a form says otherwise', () => {
    // Default true, so every form authored before the key existed behaves as it always did.
    expect(tappingAllowed(null)).toBe(true);
    expect(tappingAllowed({})).toBe(true);
    expect(tappingAllowed({ geoConfig: {} })).toBe(true);
    expect(tappingAllowed({ geoConfig: { allowTapping: true } })).toBe(true);
  });

  it('withdraws tapping only on a literal false', () => {
    expect(tappingAllowed({ geoConfig: { allowTapping: false } })).toBe(false);
  });

  it('does not disable capture on a truthy lookalike', () => {
    /**
     * The backend refuses `"false"` outright, so this should never arrive. If it does, allowing
     * tapping is the safe direction: disabling it on the strength of a string would remove the
     * only capture mode available to an enumerator with no GPS.
     */
    expect(tappingAllowed({ geoConfig: { allowTapping: 'false' } })).toBe(true);
    expect(tappingAllowed({ geoConfig: { allowTapping: 0 } })).toBe(true);
  });

  it('is independent of detectOverlaps', () => {
    /**
     * GEO-014 D-4, revised 2026-09-21. Overlap detection used to disable tapping as a side
     * effect; the two are separate keys now, so this combination is legal and deliberate.
     */
    expect(tappingAllowed({ geoConfig: { detectOverlaps: true } })).toBe(true);
    expect(tappingAllowed({ geoConfig: { detectOverlaps: false, allowTapping: false } })).toBe(
      false,
    );
  });
});
