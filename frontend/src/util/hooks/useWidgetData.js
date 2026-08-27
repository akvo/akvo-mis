import { useCallback, useEffect, useMemo, useState } from "react";
import useVisualizationRequest from "./useVisualizationRequest";

// =========================================================
// One widget → one request → the data its renderer reads
// =========================================================
//
// The browser no longer decides what to ask for. Until VIZ-010 this module
// chose between three `/visualization/*` endpoints, serialized escalation
// criteria and columns, and expanded `config.measure` through
// `dashboardMeasure.js`. All of it moved to `resolve_widget_data` on the
// server, because the public path cannot trust a client to do any of it —
// an anonymous caller authors no query, and a `form_id` on the wire is the
// enumeration hole VIZ-003 exists to close.
//
// Leaving a second copy of the measure expansion here would have been
// exactly what VIZ-008 warned about: "if that expansion is written in two
// places, one of them will eventually be wrong, and the number it produces
// will look perfectly reasonable." So `dashboardMeasure.js` is gone, and
// `monitoring=` appears nowhere in this codebase.
//
// Three sources, by what the caller has:
//
//   saved widget, signed in   GET  dashboards/{slug}/widgets/{id}/data
//   saved widget, anonymous   GET  public/dashboards/{slug}/widgets/{id}/data
//   unsaved widget            POST manage/dashboards/{id}/preview-widget
//
// The third exists because the builder canvas renders unsaved state: a
// widget added a moment ago has no id to address. It is the only path
// where a widget config travels to the server rather than being read from
// it, which is why it is authenticated and gated on `dashboard_edit`.

// Drop null/undefined/empty entries so the query string stays minimal and
// two widgets differing only in an unset optional share a cache key.
const compact = (params) =>
  Object.fromEntries(
    Object.entries(params).filter(
      ([, v]) => v !== null && typeof v !== "undefined" && v !== ""
    )
  );

// A widget saved by the server has a positive id; the builder seeds
// unsaved ones with negative temporary ids.
const isSaved = (widget) => Number(widget?.id) > 0;

const needsNoRequest = (widget) =>
  !widget || widget.is_broken || widget.type === "section_title";

/**
 * Where this widget's data comes from, or null if it needs none.
 */
const buildSource = (widget, filters, page, options) => {
  const { slug, dashboardId, isPublic } = options;
  if (needsNoRequest(widget)) {
    return null;
  }

  // Only VIZ-001 §4.4's dashboard-level filters travel, plus the table's
  // page. Everything else is read from the stored widget.
  const params = compact({
    from_date: filters?.from_date,
    to_date: filters?.to_date,
    date_question_id: filters?.date_question_id,
    administration_id: filters?.administration_id,
    page,
  });

  if (isSaved(widget) && slug) {
    const base = isPublic ? "public/dashboards" : "dashboards";
    return {
      endpoint: `${base}/${slug}/widgets/${widget.id}/data`,
      params,
      body: null,
    };
  }

  if (!isPublic && dashboardId) {
    return {
      endpoint: `manage/dashboards/${dashboardId}/preview-widget`,
      params: {},
      body: { widget, filters: params },
    };
  }

  // An unsaved widget with nowhere to ask. Not an error: the builder
  // renders it as unconfigured until the dashboard has loaded.
  return null;
};

/**
 * Reshape the server's answer into what each renderer reads.
 *
 * The renderers' input contract predates this hook and is not worth
 * changing, so the envelope is unwrapped here rather than in seven
 * presentational components.
 */
const normalize = (widget, response) => {
  const type = widget?.type;
  if (!response) {
    return {};
  }

  if (type === "kpi") {
    const rows = response.data || [];
    return { data: { value: rows.length ? rows[0].value : null } };
  }

  if (type === "table") {
    return {
      data: response.results || [],
      pagination: { total: response.count || 0 },
    };
  }

  if (type === "map") {
    return { data: Array.isArray(response) ? response : [] };
  }

  // bar, line, pie
  const rows = response.data || [];

  if (widget?.config?.stack_by) {
    // In stacked mode each row carries one numeric column per stack,
    // keyed dynamically — those columns ARE the data, so the rows must
    // not be projected.
    return {
      data: rows,
      extraConfig: { stackMapping: { stack: response.stack_labels || [] } },
    };
  }

  return {
    // Project away `group` and `color`: akvo-charts derives its series
    // from the object's keys, so either would be plotted as an extra
    // series.
    data: rows.map((row) => ({ label: row.label, value: row.value })),
    color:
      widget?.config?.group_by === "option" && rows.some((row) => row.color)
        ? rows.map((row) => row.color)
        : null,
  };
};

/**
 * @param {object} widget   A widget from `published_config` or builder state.
 * @param {object} filters  The dashboard-level filters.
 * @param {object} options  {slug, dashboardId, isPublic}
 * @returns {{data, renderWidget, loading, error, refetch, pagination}}
 */
export const useWidgetData = (widget, filters, options = {}) => {
  // The server pages tables: it reports `count` for the whole set and
  // returns one page. The page therefore lives here, where the request is
  // built — the renderer only ever sees one page and cannot page through
  // a set it was never given.
  const [page, setPage] = useState(1);
  const pageSize = widget?.config?.page_size || 20;

  // A narrower set can leave the current page past the end of it, which
  // the backend answers with an empty page and no way back.
  useEffect(() => {
    setPage(1);
  }, [widget?.id, widget?.form, filters, pageSize]);

  const source = useMemo(
    () => buildSource(widget, filters, page, options),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [widget, filters, page, options.slug, options.dashboardId, options.isPublic]
  );

  const request = useVisualizationRequest(
    source?.endpoint || null,
    source?.params,
    source?.body || null
  );

  // Every endpoint answers `{data: ...}`; the shape inside depends on the
  // widget type and is unwrapped by normalize.
  const payload = request.data?.data ?? null;

  const {
    data = null,
    extraConfig = null,
    color = null,
    pagination = null,
  } = useMemo(() => normalize(widget, payload), [widget, payload]);

  // The two derived values land at different depths — stackMapping inside
  // `config`, the colour array at the top level — so the merge happens
  // here rather than in the grid cell.
  const renderWidget = useMemo(() => {
    if (!extraConfig && !color) {
      return widget;
    }
    return {
      ...widget,
      ...(color ? { color } : {}),
      ...(extraConfig
        ? { config: { ...(widget.config || {}), ...extraConfig } }
        : {}),
    };
  }, [widget, extraConfig, color]);

  const onChange = useCallback((next) => setPage(next), []);

  return {
    data,
    renderWidget,
    pagination: pagination
      ? { ...pagination, current: page, pageSize, onChange }
      : null,
    loading: request.loading,
    error: request.error,
    refetch: request.refetch,
  };
};

export default useWidgetData;
