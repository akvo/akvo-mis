import { useCallback, useEffect, useRef, useState } from 'react';
import * as Location from 'expo-location';
import * as Sentry from '@sentry/react-native';

import { DEFAULT_INTERVAL_SECONDS, toVertex } from '../form/lib/gps-vertex';

/**
 * A dedicated watch, deliberately, even though `Home.js` already runs one.
 *
 * GEO-004's technical criteria say not to open a second GPS watch because `Home.js` feeds
 * `UserState.currentLocation`. That holds for the accuracy strip and the live dot, and this
 * screen still reads it when nothing is being recorded. It does NOT hold for recording:
 * `buildParams.gpsInterval` is **60 seconds**, so the shared watch cannot feed a 10 s capture
 * interval - it would append the same stale fix six times in a row.
 *
 * So the watch here is scoped to a capture session - opened while the enumerator is choosing a
 * recording mode, kept open while recording, and removed the moment either ends. The criterion
 * the design actually cares about - "no path leaves a GPS watch or interval running" - is what
 * the cleanup below exists to satisfy.
 */
const WATCH_OPTIONS = {
  accuracy: Location.Accuracy.BestForNavigation,
  timeInterval: 1000,
  distanceInterval: 0,
};

/**
 * Drives boundary walking: one GPS watch and, in automatic mode, one interval.
 *
 * @param mode             `'automatic'` opens the watch AND an interval. Any other truthy value
 *                         — `'manual'`, or `'standby'` while the enumerator is still choosing —
 *                         opens the watch only. Falsy holds no subscription at all.
 *
 *                         `'standby'` exists because the satellite-lock gate was otherwise
 *                         circular: Start stayed disabled until a fix arrived, and no fix could
 *                         arrive because the watch only opened once Start had been pressed. The
 *                         screen fell back to `Home.js`'s fix, which is up to 60 s old and often
 *                         absent, so the button read as permanently dead.
 * @param onVertex         called with `[lat, lng, accuracy]` (or `[lat, lng]` when the fix
 *                         carries no usable accuracy) for each vertex to append.
 * @param intervalSeconds  automatic mode only; chosen by the enumerator from ODK's list
 *                         (GEO-004 D-6). Changing it restarts the interval, which is why it is
 *                         a dependency of the effect below.
 */
const useBoundaryRecorder = ({
  mode = null,
  onVertex = null,
  intervalSeconds = DEFAULT_INTERVAL_SECONDS,
} = {}) => {
  const [fix, setFix] = useState(null);
  const subscriptionRef = useRef(null);
  const intervalRef = useRef(null);
  const fixRef = useRef(null);
  const onVertexRef = useRef(onVertex);

  /**
   * The callback is held in a ref rather than in the effect's dependencies. MapDrawView
   * rebuilds its handler on every render, and a render happens on every GPS fix, so depending
   * on the identity would tear the watch down and reopen it once a second.
   */
  onVertexRef.current = onVertex;

  const recordNow = useCallback(() => {
    const vertex = toVertex(fixRef.current?.coords);
    if (!vertex) {
      return false;
    }
    onVertexRef.current?.(vertex);
    return true;
  }, []);

  useEffect(() => {
    /**
     * Guards the await below. `watchPositionAsync` resolves after the screen may already have
     * been popped, and a subscription created after cleanup has run is one nothing will ever
     * remove - the silent battery drain GEO-004 section 9 calls the most likely field
     * complaint.
     */
    let cancelled = false;

    const start = async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status !== 'granted' || cancelled) {
          return;
        }
        const subscription = await Location.watchPositionAsync(WATCH_OPTIONS, (res) => {
          fixRef.current = res;
          setFix(res);
        });
        if (cancelled) {
          subscription.remove();
          return;
        }
        subscriptionRef.current = subscription;
      } catch (err) {
        Sentry.captureException(err);
      }
    };

    if (mode) {
      start();
    }
    if (mode === 'automatic') {
      const seconds =
        Number(intervalSeconds) > 0 ? Number(intervalSeconds) : DEFAULT_INTERVAL_SECONDS;
      intervalRef.current = setInterval(recordNow, seconds * 1000);
    }

    // Always returned, in every branch: an effect that sometimes returns a function and
    // sometimes returns nothing is how one of these paths ends up without a teardown.
    return () => {
      cancelled = true;
      subscriptionRef.current?.remove();
      subscriptionRef.current = null;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [mode, recordNow, intervalSeconds]);

  return { fix, recordNow };
};

export default useBoundaryRecorder;
