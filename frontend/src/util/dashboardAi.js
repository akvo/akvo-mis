import api from "../lib/api";

const MANAGE = "manage/dashboards";

const dashboardAi = {
  getStatus: (signal) =>
    api.get(`${MANAGE}/ai/status`, signal ? { signal } : {}),

  suggestDashboard: (payload, signal) =>
    api.post(
      `${MANAGE}/ai/suggest-dashboard`,
      payload,
      signal ? { signal } : {}
    ),

  suggestWidgets: (dashboardId, payload, signal) =>
    api.post(
      `${MANAGE}/${dashboardId}/ai/suggest-widgets`,
      payload,
      signal ? { signal } : {}
    ),
};

export default dashboardAi;
