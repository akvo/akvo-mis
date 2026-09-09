import { useCallback, useEffect, useMemo, useState } from "react";
import useVisualizationRequest from "./useVisualizationRequest";
import { expandMeasure, MONITORING_LATEST } from "../dashboardMeasure";
import stackAcrossForms from "../dashboardCrossForm";

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
// Built on `useVisualizationRequest`, which carries the module-level LRU
// cache and in-flight request sharing that make a twelve-widget page cost
// far fewer than twelve round trips. The Fiji-shaped wrappers that used to
// sit above it took an `apiBlock` from a file-based config; VIZ-009 (#313)
// deleted them, and this module is now the only caller.

// ── Escalation serializers ───────────────────────────────────────────
//
// Written here rather than reused: the legacy versions filtered on `hide`
// and `computed` flags belonging to the Fiji config shape, which the
// VIZ-001 schema does not have. They went with the rest of that tree.

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
const buildRequest = (widget, filters, rootFormId, dashboardSlug, page = 1) => {
  const config = widget?.config || {};
  const type = widget?.type;

  if (!widget || widget.is_broken || type === "section_title") {
    return null;
  }

  if (type === "scatter") {
    if (!widget.form) {
      return null;
    }
    return {
      endpoint: "visualization/values",
      params: compact({
        form_id: widget.form,
        mode: "scatter",
        question_id: widget.question,
        question_y: config.question_y,
        ...expandMeasure(widget, rootFormId),
        administration_id: filters?.administration_id,
        ...dateFilters(filters),
        dashboard_slug: dashboardSlug,
      }),
    };
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
        page,
        page_size: config.page_size || 20,
        administration_id: filters?.administration_id,
        ...dateFilters(filters),
        dashboard_slug: dashboardSlug,
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
        dashboard_slug: dashboardSlug,
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

  if (type === "line") {
    const hasCategory = Boolean(config.category_question_id);
    return {
      endpoint: "visualization/values",
      params: compact({
        form_id: widget.form,
        question_id: hasCategory
          ? config.category_question_id
          : widget.question,
        ...expandMeasure(widget, rootFormId),
        group_by: "month",
        stack_by: hasCategory ? "option" : null,
        administration_id: filters?.administration_id,
        ...dateFilters(filters),
        date_question_id: config.date_question_id,
        dashboard_slug: dashboardSlug,
      }),
    };
  }

  return {
    endpoint: "visualization/values",
    params: compact({
      form_id: widget.form,
      question_id: widget.question,
      ...expandMeasure(widget, rootFormId),
      group_by: config.group_by,
      stack_by: config.stack_by,
      // Same-form stacking only. A cross-form widget gets its stacks from
      // the second request, and sending the id here would name a question
      // on ANOTHER form — which the serializer rejects twice over: not on
      // `form_id`, and stack_question_id requires group_by=option while a
      // cross-form chart is pinned to parent_id.
      //
      // Null otherwise, and compact() drops it, so an unstacked or
      // self-stacked widget sends nothing new.
      stack_question_id: isCrossForm(widget) ? null : config.stack_question,
      // The number question the bars are measured by. Null unless the
      // author picked one, and compact() drops it, so a counting widget
      // sends nothing new (VIZ-015.b).
      value_question_id: config.value_question,
      value_type: config.value_type,
      repeat_agg: config.repeat_agg,
      option_value: config.option_value,
      administration_id: filters?.administration_id,
      ...dateFilters(filters),
      dashboard_slug: dashboardSlug,
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
const buildStatusRequest = (widget, filters, dashboardSlug) => {
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
      dashboard_slug: dashboardSlug,
    }),
  };
};

/**
 * Is this widget stacked by a question on a DIFFERENT form?
 *
 * The one predicate that decides between the two stacking models, and the
 * only thing that tells them apart in a stored config besides `group_by`.
 */
const isCrossForm = (widget) => {
  const config = widget?.config || {};
  return Boolean(
    config.stack_form &&
      config.stack_form !== widget?.form &&
      config.stack_question
  );
};

/**
 * The cross-form series request, or null.
 *
 * Same grammar as the primary, pointed at the other form. `group_by` and
 * `stack_by` are pinned rather than read from config: the join keys on
 * `row.group`, which is the registration datapoint id only under
 * `group_by=parent_id`, so no other pairing joins at all.
 *
 * Both sides carry the dashboard's filters. Without that the bars and the
 * segments describe different populations, and the discrepancy reads as a
 * data bug rather than a configuration one.
 */
const buildSeriesRequest = (widget, filters, dashboardSlug) => {
  if (!isCrossForm(widget)) {
    return null;
  }
  const config = widget.config;
  return {
    endpoint: "visualization/values",
    params: compact({
      form_id: config.stack_form,
      question_id: config.stack_question,
      group_by: "parent_id",
      stack_by: "option",
      administration_id: filters?.administration_id,
      ...dateFilters(filters),
      dashboard: dashboardSlug,
    }),
  };
};

/**
 * An option-colour array, or null if it cannot be used as a palette.
 *
 * `QuestionOptions.color` is nullable and nothing defaults it, so a
 * question authored in the form builder or imported from XLSForm usually
 * has no colours at all — and may have only some. All-or-nothing is
 * deliberate: akvo-charts reads the array as a palette, so a partial one
 * keeps the authored colours and lets the gaps fall to whatever the
 * library does with a null, which can repeat a colour already used in the
 * same chart. Returning null instead gives every series a distinct
 * automatic colour, which is the failure a reader can interpret.
 */
const usableColors = (colors) =>
  Array.isArray(colors) &&
  colors.length > 0 &&
  colors.every((c) => typeof c === "string" && c.length > 0)
    ? colors
    : null;

// ── Reshaping the answer ─────────────────────────────────────────────

const normalize = (widget, response, statusResponse, seriesResponse) => {
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

  if (type === "scatter") {
    return { data: Array.isArray(response) ? response : [] };
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

  // `config.stack_by` says what the author asked for; `stack_labels` says
  // what the server actually returned. They can disagree: asked to
  // cross-tab a question against itself the backend declines the diagonal
  // and answers with the plain option breakdown instead, which carries no
  // stacks at all. Trusting the config there projected eight rows of real
  // counts down to bare labels and drew an empty chart. Read the shape,
  // not the intent.
  //
  // `category_question_id` is the line chart's own way of asking for the
  // same shape (VIZ-013): it carries no `stack_by` of its own, because
  // buildRequest derives `stack_by=option` from it rather than storing it.
  const stacked =
    Boolean(config.stack_by || config.category_question_id) &&
    ((isCrossForm(widget) ? seriesResponse : response)?.stack_labels || [])
      .length > 0;

  if (stacked) {
    // Cross-form: the bars come from `response` and the stacks from
    // `seriesResponse`, joined on `row.group` — the registration datapoint
    // id both carry. The join MUST run here, before the projection below,
    // which drops `group` along with every other non-stack key. Reversed,
    // it would see no matching ids and render an empty chart with no error
    // anywhere.
    //
    // The legend then describes the SERIES question, not the measured one:
    // the category response's labels are the bars.
    const crossForm = isCrossForm(widget);
    const legend = crossForm ? seriesResponse : response;
    const stackLabels = legend?.stack_labels || [];
    const stackRows = crossForm
      ? stackAcrossForms({ category: response, series: seriesResponse })
      : rows;

    // In stacked mode each row carries one numeric column per stack, keyed
    // dynamically — those columns ARE the data. But they are not the only
    // keys the server sends, and akvo-charts turns EVERY key but the first
    // into a series (`dimensions.slice(1)` in its StackBar). Passing the
    // row through whole therefore plotted `group` as a bar of its own —
    // and on the parent path `group` is the datapoint's id, so a chart of
    // counts under 5 grew bars in the thousands.
    //
    // So project to the category first, followed by exactly the stack
    // columns, in `stack_labels` order.
    //
    // The category key is not always `label`: the parent-stacked number
    // paths key their rows `month` or `date` instead
    // (`_stack_parent_by_month` / `_stack_parent_by_date`). That went
    // unnoticed while this branch passed rows through whole, because
    // akvo-charts reads whatever the FIRST key is — the projection is
    // what made the name matter, and hardcoding `label` drew a chart of
    // undefined categories for a number question stacked by site.
    const categoryOf = (row) => row.label ?? row.month ?? row.date ?? null;
    return {
      data: stackRows.map((row) =>
        stackLabels.reduce(
          (projected, key) => ({ ...projected, [key]: row[key] ?? 0 }),
          { label: categoryOf(row) }
        )
      ),
      extraConfig: { stackMapping: { stack: stackLabels } },
      color: usableColors(legend?.colors),
    };
  }

  const chartColors = widget?.config?.chart_colors;
  const optionColors = widget?.config?.option_colors;
  if (chartColors && chartColors.length > 0) {
    return {
      data: rows.map((row) => ({ label: row.label, value: row.value })),
      color: rows.map((row, i) => {
        if (optionColors && optionColors[row.label]) {
          return optionColors[row.label];
        }
        return chartColors[i % chartColors.length];
      }),
    };
  }

  return {
    data: rows.map((row) => ({ label: row.label, value: row.value })),
    color:
      config.group_by === "option"
        ? usableColors(rows.map((row) => row.color))
        : null,
  };
};

// ── The hook ─────────────────────────────────────────────────────────

/**
 * @param {object} widget      One widget from published_config or builder state.
 * @param {object} filters     {from_date, to_date, date_question_id, administration_id}
 * @param {object} options     {rootFormId, dashboardSlug}
 * @returns {{data, renderWidget, loading, error, refetch, pagination}}
 */
export const useWidgetData = (
  widget,
  filters,
  { rootFormId, dashboardSlug } = {}
) => {
  // /escalation pages on the server: it reports `count` for the whole set
  // and returns one page of `results`. The page therefore has to live here,
  // where the request is built — the renderer only ever sees one page and
  // cannot page through a set it was never given.
  const [page, setPage] = useState(1);
  const pageSize = widget?.config?.page_size || 20;

  // A narrower set can leave the current page past the end of it, which the
  // backend answers with an empty page and no way back.
  useEffect(() => {
    setPage(1);
  }, [widget?.id, widget?.form, filters, pageSize]);

  const request = useMemo(
    () => buildRequest(widget, filters, rootFormId, dashboardSlug, page),
    [widget, filters, rootFormId, dashboardSlug, page]
  );
  const statusRequest = useMemo(
    () => buildStatusRequest(widget, filters, dashboardSlug),
    [widget, filters, dashboardSlug]
  );
  const seriesRequest = useMemo(
    () => buildSeriesRequest(widget, filters, dashboardSlug),
    [widget, filters, dashboardSlug]
  );

  // All three called unconditionally, with a null endpoint when the widget
  // needs no request: hook order must not vary with widget type or state.
  const primary = useVisualizationRequest(
    request?.endpoint || null,
    request?.params
  );
  const status = useVisualizationRequest(
    statusRequest?.endpoint || null,
    statusRequest?.params
  );
  const series = useVisualizationRequest(
    seriesRequest?.endpoint || null,
    seriesRequest?.params
  );

  const {
    data = null,
    extraConfig = null,
    color = null,
    pagination = null,
  } = useMemo(
    () => normalize(widget, primary.data, status.data, series.data),
    [widget, primary.data, status.data, series.data]
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

  const onChange = useCallback((next) => setPage(next), []);

  return {
    data,
    renderWidget,
    // Only a paged widget reports pagination; a chart has none. `total` is
    // the whole set, `current` and `pageSize` describe the slice in `data`,
    // and `onChange` fetches another one.
    pagination: pagination
      ? { ...pagination, current: page, pageSize, onChange }
      : null,
    // The series call counts toward both: a cross-form chart drawn from
    // only half its data is a wrong chart, not a partial one.
    loading: primary.loading || status.loading || series.loading,
    error: primary.error || status.error || series.error,
    refetch: primary.refetch,
  };
};

export default useWidgetData;
