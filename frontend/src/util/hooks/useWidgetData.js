import { useMemo } from "react";
import useVisualizationRequest from "./useVisualizationRequest";
import { expandMeasure, MONITORING_LATEST } from "../dashboardMeasure";

// =========================================================
// One widget → one request → data the VIZ-006 renderers accept
// =========================================================
//
// Three jobs, in order: decide what to ask for, ask, then reshape the
// answer into the shape the seven `Viz*` renderers already read. That last
// step is why none of them needed changing for a data reason: their input
// contract was fixed before this hook existed, and matching it is cheaper
// than teaching seven presentational components to read API envelopes.
//
// Built on `useVisualizationRequest`, which is deliberately left alone: it
// is already endpoint-and-params generic and carries the module-level LRU
// cache and in-flight request sharing that make a twelve-widget page cost
// far fewer than twelve round trips. The Fiji-shaped wrappers above it
// (`useDashboardValues`, `useDashboardEscalation`) are not reused — they
// take an `apiBlock` from a file-based config that VIZ-009 deletes.

// ── Escalation serializers ───────────────────────────────────────────
//
// Written here rather than imported from `useDashboardEscalation.js`:
// those versions filter on `hide` and `computed` flags that belong to the
// Fiji config shape and do not exist in the VIZ-001 schema. Importing them
// would tie this module to one scheduled for deletion.

// Sources the backend refuses without a question id
// (EscalationFilterSerializer.validate_columns).
const QID_REQUIRED = ["answer", "parent_answer", "latest_date"];

const isUsableColumn = (c) =>
  Boolean(c && c.key && c.source) &&
  (!QID_REQUIRED.includes(c.source) || Boolean(c.question));

// `?? ""` rather than a falsy test: 0 is a legitimate threshold value.
const isUsableCriterion = (c) =>
  Boolean(c && c.type && c.question) && (c.value ?? "") !== "";

// Incomplete entries are dropped rather than serialized. Two ways they
// arise, both routine: the inspector seeds a new criterion row as
// `{type, question: null, value: ""}` before the author picks anything,
// and its "Last submission" checkbox writes `latest_date` with no
// question id at all, which the backend rejects and which would take the
// whole table down with it. Dropping the unusable entry costs one column;
// sending it costs the widget. See the VIZ-008 spec's follow-on notes.
export const serializeCriteria = (criteria = []) =>
  criteria
    .filter(isUsableCriterion)
    .map((c) => `${c.type}:${c.question}:${c.value}`)
    .join(",");

export const serializeColumns = (columns = []) =>
  columns
    .filter(isUsableColumn)
    .map((c) =>
      QID_REQUIRED.includes(c.source)
        ? `${c.key}:${c.source}:${c.question}`
        : `${c.key}:${c.source}`
    )
    .join(",");

// Drop null/undefined/empty entries so the query string stays minimal and
// two widgets that differ only in an unset optional share a cache key.
const compact = (params) =>
  Object.fromEntries(
    Object.entries(params).filter(
      ([, v]) => v !== null && typeof v !== "undefined" && v !== ""
    )
  );

const dateFilters = (filters) => ({
  from_date: filters?.from_date,
  to_date: filters?.to_date,
  date_question_id: filters?.date_question_id,
});

// ── What to ask for ──────────────────────────────────────────────────

/**
 * The widget's primary request, or null when it needs none.
 *
 * The parameter names below are NOT uniform across the three endpoints,
 * and the differences are invisible at the call site — a wrong name is
 * accepted and silently dropped rather than rejected. Each divergence is
 * commented where it happens.
 */
const buildRequest = (widget, filters, rootFormId) => {
  const config = widget?.config || {};
  const type = widget?.type;

  if (!widget || widget.is_broken || type === "section_title") {
    return null;
  }

  if (type === "table") {
    // Columns are still `required=True` on EscalationFilterSerializer, so
    // a table with none is a guaranteed 400 — re-issued on every filter
    // change and rendered as a network error for a configuration gap.
    //
    // Criteria are NOT required: they narrow the datapoint list, they do
    // not define it, so a table with no conditions is the plain list of
    // every datapoint. That is the useful default for a dashboard table
    // and it is what the endpoint now returns.
    const criteria = serializeCriteria(config.criteria);
    const columns = serializeColumns(config.columns);
    if (!columns) {
      return null;
    }
    return {
      // The path form is the registration parent and the widget's own form
      // is the monitoring child: /escalation is inherently a "parent plus
      // its latest monitoring child" query.
      endpoint: `visualization/escalation/${rootFormId}`,
      params: compact({
        monitoring_form_id: widget.form,
        criteria,
        columns,
        page: 1,
        page_size: config.page_size || 20,
        administration_id: filters?.administration_id,
        ...dateFilters(filters),
      }),
    };
  }

  if (type === "map") {
    const isMonitoringForm = Boolean(
      widget.form && rootFormId && widget.form !== rootFormId
    );
    return {
      // Always the REGISTRATION form, never widget.form. `geo` is captured
      // once, when a site is registered; monitoring submissions carry
      // none, so asking a monitoring form for geolocation returns an empty
      // list every time. The widget's own form is the *colour* source, and
      // it reaches the request below as monitoring_form_id.
      //
      // This is also what makes the status join work: /values/formula on a
      // monitoring form groups by parent_id, which IS the registration
      // datapoint id these points are keyed by.
      endpoint: `maps/geolocation/${rootFormId}`,
      params: compact({
        // `administration`, not `administration_id`. This endpoint predates
        // the /visualization grammar and never adopted it.
        administration: filters?.administration_id,
        from_date: filters?.from_date,
        to_date: filters?.to_date,
        // It has no date_question_id either. Bounding the window on
        // monitoring activity rather than on registration date is spelled
        // include_monitoring + monitoring_form_id instead.
        include_monitoring: isMonitoringForm ? true : null,
        monitoring_form_id: isMonitoringForm ? widget.form : null,
      }),
    };
  }

  // kpi, bar, line, pie
  if (!widget.form) {
    // form_id is `required=True` on ValuesFilterSerializer, so a widget
    // whose data source has not been picked yet is a guaranteed 400. That
    // was harmless while only the viewer fetched — the server never stores
    // such a widget — but the builder canvas renders unsaved state, where
    // a half-built widget is the normal case for as long as it takes to
    // configure it. question_id is deliberately not part of this check:
    // it is optional, and a count-only KPI has none.
    return null;
  }
  return {
    endpoint: "visualization/values",
    params: compact({
      form_id: widget.form,
      question_id: widget.question,
      ...expandMeasure(widget, rootFormId),
      group_by: config.group_by,
      stack_by: config.stack_by,
      value_type: config.value_type,
      repeat_agg: config.repeat_agg,
      option_value: config.option_value,
      administration_id: filters?.administration_id,
      ...dateFilters(filters),
    }),
  };
};

/**
 * The map's second request: one bucket value per point, joined by id.
 *
 * /maps/geolocation returns coordinates and nothing else, so a map
 * coloured by an answer needs a second source. The bucket list comes from
 * `config.status_colors`' own keys — they are option values, which is
 * exactly what the formula needs — so no form metadata has to be fetched
 * or read out of the published-forms store.
 */
const buildStatusRequest = (widget, filters) => {
  const config = widget?.config || {};
  const values = Object.keys(config.status_colors || {});
  if (
    !widget ||
    widget.is_broken ||
    widget.type !== "map" ||
    !widget.question ||
    values.length === 0
  ) {
    // validate_shape() rejects an empty `buckets` array with a 400, so an
    // uncoloured map asks for nothing and every pin takes widget.color.
    return null;
  }
  return {
    endpoint: "visualization/values/formula",
    params: compact({
      form_id: widget.form,
      group_by: "parent_id",
      // Always latest, whatever the widget's own measure says: a pin shows
      // one current status, and the endpoint accepts no other value.
      monitoring: MONITORING_LATEST,
      formula: JSON.stringify({
        buckets: values.map((value) => ({
          value,
          label: value,
          all_of: [
            { question_id: widget.question, op: "option_equals", value },
          ],
        })),
        default: { value: "_no_info", label: "_no_info" },
      }),
      from_date: filters?.from_date,
      to_date: filters?.to_date,
    }),
  };
};

// ── Reshaping the answer ─────────────────────────────────────────────

const normalize = (widget, response, statusResponse) => {
  const config = widget?.config || {};
  const type = widget?.type;
  // Each branch returns only the keys it sets; the caller defaults the rest.
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
    const byParent = (statusResponse?.data || []).reduce((acc, row) => {
      acc[row.group] = row.label;
      return acc;
    }, {});
    const points = Array.isArray(response) ? response : [];
    return {
      data: points.map((point) => ({
        ...point,
        status: byParent[point.id] ?? null,
      })),
    };
  }

  // bar, line, pie
  const rows = response.data || [];

  if (config.stack_by) {
    // In stacked mode each row carries one numeric column per stack, keyed
    // dynamically — those columns ARE the data, so the rows must not be
    // projected. `stack_labels` is the mapping the builder never writes,
    // which is why stacked charts render empty on the branch today.
    return {
      data: rows,
      extraConfig: { stackMapping: { stack: response.stack_labels || [] } },
    };
  }

  return {
    // Project away `group` and `color`: akvo-charts derives its series from
    // the object's keys, so either would be plotted as an extra series.
    data: rows.map((row) => ({ label: row.label, value: row.value })),
    color:
      config.group_by === "option" && rows.some((row) => row.color)
        ? rows.map((row) => row.color)
        : null,
  };
};

// ── The hook ─────────────────────────────────────────────────────────

/**
 * @param {object} widget      One widget from published_config or builder state.
 * @param {object} filters     {from_date, to_date, date_question_id, administration_id}
 * @param {object} options     {rootFormId}
 * @returns {{data, renderWidget, loading, error, refetch, pagination}}
 */
export const useWidgetData = (widget, filters, { rootFormId } = {}) => {
  const request = useMemo(
    () => buildRequest(widget, filters, rootFormId),
    [widget, filters, rootFormId]
  );
  const statusRequest = useMemo(
    () => buildStatusRequest(widget, filters),
    [widget, filters]
  );

  // Both called unconditionally, with a null endpoint when the widget needs
  // no request: hook order must not vary with widget type or state.
  const primary = useVisualizationRequest(
    request?.endpoint || null,
    request?.params
  );
  const status = useVisualizationRequest(
    statusRequest?.endpoint || null,
    statusRequest?.params
  );

  const {
    data = null,
    extraConfig = null,
    color = null,
    pagination = null,
  } = useMemo(
    () => normalize(widget, primary.data, status.data),
    [widget, primary.data, status.data]
  );

  // The two derived values land at different depths — stackMapping inside
  // `config`, the colour array at the top level — so the merge happens here
  // rather than in the grid cell, which would otherwise have to know which
  // goes where purely because of how VIZ-006 happened to read each field.
  const renderWidget = useMemo(() => {
    // Also the null-widget answer: nothing derived means nothing to merge.
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

  return {
    data,
    renderWidget,
    pagination,
    loading: primary.loading || status.loading,
    error: primary.error || status.error,
    refetch: primary.refetch,
  };
};

export default useWidgetData;
