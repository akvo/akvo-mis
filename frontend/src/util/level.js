import { api, store } from "../lib";

// Levels are tenant-owned and served at runtime (they were previously
// baked into config.js as window.levels). Mirrors util/form.js.
export const getLevels = () => store.getRawState().levels || [];

// The rejection path matters on a refetch: it clears the previous
// tenant's levels rather than leaving them for the next session.
export const fetchLevels = () =>
  api
    .get("levels")
    .then(
      (res) => (Array.isArray(res.data) ? res.data : []),
      () => []
    )
    .then((levels) => {
      store.update((s) => {
        s.levels = levels;
      });
      return levels;
    });
