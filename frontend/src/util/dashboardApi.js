import api from "../lib/api";
import { store } from "../lib";

const MANAGE = "manage/dashboards";
const PUBLIC = "dashboards";

// One module per VIZ-004: no component calls api.get directly, so the
// widget payload shape (VIZ-006) and the measure expansion (VIZ-008)
// each have exactly one place to live.
//
// Until VIZ-005 there was a fixture fallback here, keyed on a 404
// response. It cannot survive that slice: 404 is now the
// tenant-isolation answer for an unknown or foreign dashboard id, and
// a fallback cannot tell "the backend is not built" from "that
// dashboard is not yours".
// Any write to a dashboard can change what the header menu should list:
// publishing, unpublishing, flipping visibility, renaming and deleting
// all move a dashboard in or out of it, and a rename changes its label.
// Marking the list stale here rather than at each call site means no
// caller has to remember to, and a mutation added later inherits it —
// the menu lives in the header and is not on speaking terms with the
// builder or the list page.
//
// Only on success: a rejected write changed nothing.
const invalidatesTheList = (request) =>
  request.then((res) => {
    store.update((s) => {
      s.dashboardsVersion += 1;
    });
    return res;
  });

const dashboardApi = {
  list: () => api.get(MANAGE),

  create: (payload) => invalidatesTheList(api.post(MANAGE, payload)),

  get: (id) => api.get(`${MANAGE}/${id}`),

  update: (id, payload) =>
    invalidatesTheList(api.put(`${MANAGE}/${id}`, payload)),

  destroy: (id) => invalidatesTheList(api.delete(`${MANAGE}/${id}`)),

  publish: (id) => invalidatesTheList(api.post(`${MANAGE}/${id}/publish`)),

  unpublish: (id) => invalidatesTheList(api.post(`${MANAGE}/${id}/unpublish`)),

  duplicate: (id) => invalidatesTheList(api.post(`${MANAGE}/${id}/duplicate`)),

  sources: (id) => api.get(`${MANAGE}/${id}/sources`),

  // Preview must show what a viewer sees, and a viewer sees the
  // snippet running on the embed host. Unsaved markup has no published
  // snapshot to serve, so the server parks it briefly and hands back a
  // URL. Not a list-invalidating write: nothing about the dashboard
  // changes.
  embedPreview: (id, snippet) =>
    api.post(`${MANAGE}/${id}/embed-preview`, { embed_snippet: snippet }),

  getPublished: (slug) => api.get(`${PUBLIC}/${slug}`),

  listPublished: () => api.get(PUBLIC),

  setVisibility: (id, isPublic) =>
    invalidatesTheList(
      api.post(`${MANAGE}/${id}/visibility`, { is_public: isPublic })
    ),
};

export default dashboardApi;
