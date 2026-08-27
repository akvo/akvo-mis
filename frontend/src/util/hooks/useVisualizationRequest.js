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

// `body` is part of the key: a POST for an unsaved widget is identified by
// what it sends, since its URL is the same for every widget on the
// dashboard.
const buildKey = (endpoint, params, body) =>
  `${endpoint}?${JSON.stringify(params)}${
    body ? `#${JSON.stringify(body)}` : ""
  }`;

const sendRequest = (endpoint, params, body) =>
  (body ? api.post(endpoint, body) : api.get(endpoint, { params })).then(
    (res) => res.data
  );

/**
 * Generic visualization fetch hook. Reused by useDashboardValues,
 * useDashboardEscalation, useDashboardProgress.
 *
 * @param {string|null} endpoint  e.g. "visualization/values". null skips the fetch.
 * @param {object}       params   Plain object serialized into query string.
 * @param {object|null}  body     When given, the request is a POST of this
 *                                body rather than a GET. Used for the
 *                                builder's unsaved widgets, which have no
 *                                id to address (VIZ-010).
 * @returns {{ data, loading, error, refetch: () => void }}
 */
export const useVisualizationRequest = (endpoint, params, body = null) => {
  const [state, setState] = useState({
    data: null,
    loading: Boolean(endpoint),
    error: null,
  });
  const mountedRef = useRef(true);
  const keyRef = useRef(null);

  const key = endpoint ? buildKey(endpoint, params, body) : null;

  const run = useCallback(
    (bypassCache = false) => {
      if (!endpoint) {
        return;
      }
      const cacheKey = buildKey(endpoint, params, body);
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
        promise = sendRequest(endpoint, params, body);
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
