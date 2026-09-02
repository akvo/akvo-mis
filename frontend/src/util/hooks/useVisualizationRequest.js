import { useEffect, useRef, useState, useCallback } from "react";
import api from "../../lib/api";

/**
 * Module-level LRU cache keyed by serialized request. Values are
 * `{ promise, data }`. In-flight requests share the same promise so multiple
 * widgets hitting the same endpoint don't duplicate work.
 *
 * Recency is tracked via Map insertion order: every cache hit re-inserts the
 * key (moves it to the tail), and writes evict the oldest entry once we hit
 * `CACHE_MAX_ENTRIES`. This keeps memory bounded in long-lived sessions where
 * a user toggles through many filter combinations.
 *
 * The cap is generous (200 entries × ~modest payloads) — enough to cover a
 * full dashboard's working set across several filter switches without
 * thrashing, while still protecting against unbounded growth.
 */
const CACHE_MAX_ENTRIES = 200;
const cache = new Map();

const cacheGet = (key) => {
  const entry = cache.get(key);
  if (!entry) {
    return null;
  }
  // Mark as most-recently-used.
  cache.delete(key);
  cache.set(key, entry);
  return entry;
};

const cacheSet = (key, entry) => {
  if (cache.has(key)) {
    cache.delete(key);
  } else if (cache.size >= CACHE_MAX_ENTRIES) {
    // Evict oldest (first inserted) entry.
    const oldest = cache.keys().next().value;
    if (typeof oldest !== "undefined") {
      cache.delete(oldest);
    }
  }
  cache.set(key, entry);
};

const buildKey = (endpoint, params) => `${endpoint}?${JSON.stringify(params)}`;

const sendRequest = (endpoint, params) =>
  api.get(endpoint, { params }).then((res) => res.data);

/**
 * Generic visualization fetch hook. Endpoint-and-params generic, with a
 * module-level LRU cache and in-flight request sharing, so a page of
 * widgets costs far fewer than one round trip per widget. `useWidgetData`
 * is its caller.
 *
 * @param {string|null} endpoint  e.g. "visualization/values". null skips the fetch.
 * @param {object}       params   Plain object serialized into query string.
 * @returns {{ data, loading, error, refetch: () => void }}
 */
export const useVisualizationRequest = (endpoint, params) => {
  const [state, setState] = useState({
    data: null,
    loading: Boolean(endpoint),
    error: null,
  });
  const mountedRef = useRef(true);
  const keyRef = useRef(null);

  const key = endpoint ? buildKey(endpoint, params) : null;

  const run = useCallback(
    (bypassCache = false) => {
      if (!endpoint) {
        return;
      }
      const cacheKey = buildKey(endpoint, params);
      keyRef.current = cacheKey;

      const existing = bypassCache ? null : cacheGet(cacheKey);
      if (existing && typeof existing.data !== "undefined") {
        setState({ data: existing.data, loading: false, error: null });
        return;
      }

      setState((s) => ({ ...s, loading: true, error: null }));

      let promise;
      if (existing && existing.promise) {
        promise = existing.promise;
      } else {
        promise = sendRequest(endpoint, params);
        cacheSet(cacheKey, { promise });
      }

      promise
        .then((data) => {
          cacheSet(cacheKey, { data });
          if (mountedRef.current && keyRef.current === cacheKey) {
            setState({ data, loading: false, error: null });
          }
        })
        .catch((error) => {
          cache.delete(cacheKey);
          if (mountedRef.current && keyRef.current === cacheKey) {
            setState({ data: null, loading: false, error });
          }
        });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [endpoint, key]
  );

  useEffect(() => {
    mountedRef.current = true;
    run(false);
    return () => {
      mountedRef.current = false;
    };
  }, [run]);

  const refetch = useCallback(() => run(true), [run]);

  return { ...state, refetch };
};

/**
 * Test hook: clears the module cache. Exposed for unit tests only.
 */
export const __clearVisualizationCache = () => cache.clear();

/**
 * Test helper: introspect cache state. Exposed for unit tests only.
 */
export const __visualizationCacheStats = () => ({
  size: cache.size,
  max: CACHE_MAX_ENTRIES,
  keys: Array.from(cache.keys()),
});

export default useVisualizationRequest;
