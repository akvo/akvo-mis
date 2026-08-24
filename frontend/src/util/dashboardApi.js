import api from "../lib/api";
import fixtureList from "../pages/dashboards/__fixtures__/dashboardList.json";
import fixtureDetail from "../pages/dashboards/__fixtures__/dashboardDetail.json";
import fixtureSources from "../pages/dashboards/__fixtures__/dashboardSources.json";
import fixturePublished from "../pages/dashboards/__fixtures__/dashboardPublished.json";

const MANAGE = "manage/dashboards";
const PUBLIC = "dashboards";

// ── Fixture-backed session store ──
// While the backend track has not shipped, every mutating call falls back to
// an in-memory list seeded from the fixture file. The list survives
// navigation within the SPA session; a full page reload resets it.
let usingFixtures = false;
let sessionList = null;
let nextId = 1000;

const getSessionList = () => {
  if (!sessionList) {
    sessionList = fixtureList.map((d) => ({ ...d }));
  }
  return sessionList;
};

const isBackendAbsent = (err) => err?.response?.status === 404;

const dashboardApi = {
  list: () =>
    api
      .get(MANAGE)
      .then((res) => {
        usingFixtures = false;
        return res;
      })
      .catch((err) => {
        if (isBackendAbsent(err)) {
          usingFixtures = true;
          return { data: getSessionList() };
        }
        throw err;
      }),

  create: (payload) =>
    api.post(MANAGE, payload).catch((err) => {
      if (isBackendAbsent(err)) {
        nextId += 1;
        const slug = (payload.name || "untitled")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "");
        const created = {
          id: nextId,
          name: payload.name,
          slug,
          description: null,
          status: "draft",
          root_form: { id: payload.root_form, name: "" },
          created: new Date().toISOString(),
          updated: new Date().toISOString(),
          widgets: [],
        };
        getSessionList().push(created);
        return { data: created };
      }
      throw err;
    }),

  get: (id) =>
    api.get(`${MANAGE}/${id}`).catch((err) => {
      if (isBackendAbsent(err)) {
        const found = getSessionList().find((d) => d.id === id);
        if (found) {
          const widgets = Array.isArray(found.widgets) ? found.widgets : [];
          const hasFullWidgets =
            widgets.length > 0 &&
            widgets[0].id !== null &&
            typeof widgets[0].id !== "undefined";
          // List fixture widgets are stubs (no id) — use detail fixture
          // widgets but keep the dashboard metadata from the session list.
          return {
            data: {
              ...found,
              widgets: hasFullWidgets ? widgets : fixtureDetail.widgets,
              default_filters:
                found.default_filters || fixtureDetail.default_filters,
            },
          };
        }
        return { data: fixtureDetail };
      }
      throw err;
    }),

  update: (id, payload) =>
    api.put(`${MANAGE}/${id}`, payload).catch((err) => {
      if (isBackendAbsent(err)) {
        const list = getSessionList();
        const idx = list.findIndex((d) => d.id === id);
        if (idx !== -1) {
          list[idx] = {
            ...list[idx],
            name: payload.name || list[idx].name,
            description: payload.description || list[idx].description,
            default_filters: payload.default_filters,
            widgets: payload.widgets || list[idx].widgets,
            updated: new Date().toISOString(),
          };
          return { data: list[idx] };
        }
      }
      throw err;
    }),

  destroy: (id) =>
    api.delete(`${MANAGE}/${id}`).catch((err) => {
      if (isBackendAbsent(err) && usingFixtures) {
        sessionList = getSessionList().filter((d) => d.id !== id);
        return { data: null };
      }
      throw err;
    }),

  publish: (id) => api.post(`${MANAGE}/${id}/publish`),

  unpublish: (id) => api.post(`${MANAGE}/${id}/unpublish`),

  duplicate: (id) =>
    api.post(`${MANAGE}/${id}/duplicate`).catch((err) => {
      if (isBackendAbsent(err)) {
        const source = getSessionList().find((d) => d.id === id);
        if (source) {
          nextId += 1;
          const copy = {
            ...source,
            id: nextId,
            name: `${source.name} (copy)`,
            slug: `${source.slug}-copy-${nextId}`,
            status: "draft",
            created: new Date().toISOString(),
            updated: new Date().toISOString(),
          };
          getSessionList().push(copy);
          return { data: copy };
        }
      }
      throw err;
    }),

  sources: (id) =>
    api.get(`${MANAGE}/${id}/sources`).catch((err) => {
      if (isBackendAbsent(err)) {
        return { data: fixtureSources };
      }
      throw err;
    }),

  getPublished: (slug) =>
    api.get(`${PUBLIC}/${slug}`).catch((err) => {
      if (isBackendAbsent(err)) {
        return { data: fixturePublished };
      }
      throw err;
    }),
};

export default dashboardApi;
