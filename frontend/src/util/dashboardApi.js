import api from "../lib/api";

const MANAGE = "manage/dashboards";
const PUBLIC = "dashboards";
const PUBLIC_OPEN = "public/dashboards";

// One module per VIZ-004: no component calls api.get directly, so the
// widget payload shape (VIZ-006) and the measure expansion (VIZ-008)
// each have exactly one place to live.
//
// Until VIZ-005 there was a fixture fallback here, keyed on a 404
// response. It cannot survive that slice: 404 is now the
// tenant-isolation answer for an unknown or foreign dashboard id, and
// a fallback cannot tell "the backend is not built" from "that
// dashboard is not yours". publish, unpublish and duplicate are still
// unimplemented server-side and now surface as errors until VIZ-007.
const dashboardApi = {
  list: () => api.get(MANAGE),

  create: (payload) => api.post(MANAGE, payload),

  get: (id) => api.get(`${MANAGE}/${id}`),

  update: (id, payload) => api.put(`${MANAGE}/${id}`, payload),

  destroy: (id) => api.delete(`${MANAGE}/${id}`),

  publish: (id) => api.post(`${MANAGE}/${id}/publish`),

  unpublish: (id) => api.post(`${MANAGE}/${id}/unpublish`),

  duplicate: (id) => api.post(`${MANAGE}/${id}/duplicate`),

  sources: (id) => api.get(`${MANAGE}/${id}/sources`),

  getPublished: (slug) => api.get(`${PUBLIC}/${slug}`),

  // The anonymous surface (VIZ-010). Served only on a workspace's own
  // subdomain, and only for dashboards that are both published and
  // public — the server decides both from the request host and the row,
  // so there is nothing to pass here.
  listPublic: () => api.get(`${PUBLIC_OPEN}`),

  getPublic: (slug) => api.get(`${PUBLIC_OPEN}/${slug}`),
};

export default dashboardApi;
