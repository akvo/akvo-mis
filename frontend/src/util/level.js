import { api, store } from "../lib";

// Levels are tenant-owned and served at runtime (they were previously
// baked into config.js as window.levels). Mirrors util/form.js.
export const getLevels = () => store.getRawState().levels || [];

export const fetchLevels = () =>
  api
    .get("levels")
    .then((res) => {
      const levels = Array.isArray(res.data) ? res.data : [];
      store.update((s) => {
        s.levels = levels;
      });
      return levels;
    })
    .catch(() => {
      store.update((s) => {
        s.levels = [];
      });
      return [];
    });
