export const WIDGET_TYPES = [
  {
    type: "kpi",
    label: "KPI card",
    desc: "Single metric",
    iconBg: "#e8f2ff",
  },
  {
    type: "bar",
    label: "Bar chart",
    desc: "Compare categories",
    iconBg: "#e8f2ff",
  },
  {
    type: "line",
    label: "Line chart",
    desc: "Trend over time",
    iconBg: "#eef2fb",
  },
  {
    type: "pie",
    label: "Pie / doughnut",
    desc: "Share of total",
    iconBg: "#eaf5e6",
  },
  {
    type: "scatter",
    label: "Scatter plot",
    desc: "X/Y correlation",
    iconBg: "#eef2fb",
  },
  {
    type: "table",
    label: "Table",
    desc: "Rows of records",
    iconBg: "#f0f1f4",
  },
  {
    type: "map",
    label: "Map",
    desc: "Geographic points",
    iconBg: "#eaf5e6",
  },
  {
    type: "section_title",
    label: "Section title",
    desc: "Group your widgets",
    iconBg: "#f0f1f4",
  },
];

const DEFAULT_CHART_COLORS = [
  "#1890ff",
  "#64A73B",
  "#F5A623",
  "#e41a1c",
  "#9b59b6",
];

export const WIDGET_DEFAULTS = {
  kpi: {
    col_span: 6,
    color: null,
    config: {
      value_type: "number",
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
    },
  },
  bar: {
    col_span: 12,
    color: null,
    config: {
      group_by: "option",
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
    },
  },
  line: {
    col_span: 12,
    color: null,
    config: {
      group_by: "month",
      date_question_id: null,
      category_question_id: null,
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
    },
  },
  pie: {
    col_span: 8,
    color: null,
    config: {
      group_by: "option",
      variant: "pie",
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
    },
  },
  table: {
    col_span: 24,
    color: null,
    config: { columns: [], criteria: [] },
  },
  map: {
    col_span: 24,
    color: null,
    config: {
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
    },
  },
  scatter: {
    col_span: 12,
    color: null,
    config: {
      color_scheme: "categorical",
      chart_colors: DEFAULT_CHART_COLORS,
    },
  },
  section_title: {
    col_span: 24,
    color: null,
    config: { text: "" },
  },
};

export const VALID_GROUP_BY = [
  // "This question's options", not "Option value": Stack by carries an
  // entry with that exact label meaning something else — segments rather
  // than bars — and the two sat one above the other in the panel.
  { value: "option", label: "This question's options" },
  { value: "month", label: "Month" },
  { value: "date", label: "Date" },
  { value: "parent_id", label: "Registration site" },
];

export const VALID_VALUE_TYPE = [
  { value: "number", label: "Count" },
  { value: "percentage", label: "Percentage" },
];

export const VALID_REPEAT_AGG = [
  { value: "average", label: "Average" },
  { value: "sum", label: "Sum" },
  { value: "max", label: "Max" },
  { value: "min", label: "Min" },
  { value: "last", label: "Last" },
];

export const VALID_STACK_BY = [
  { value: "", label: "None" },
  { value: "option", label: "Option value" },
  { value: "parent_id", label: "Registration site" },
];

/**
 * Question types that can supply the stacks of a stacked chart.
 *
 * A stack needs a bounded set of series, which only an option set
 * provides. A number or date question would produce one series per
 * distinct answer, which is not a stacked bar; the backend refuses them
 * too, so the picker and the serializer agree.
 */
export const STACK_QUESTION_TYPES = new Set(["option", "multiple_option"]);

// Types whose grouping differs from the plain count of submissions.
export const SUPPORTED_GROUP_QUESTION_TYPES = new Set([
  "option",
  "multiple_option",
  "number",
]);

/**
 * The "Stack by" choices that actually compute, given the rest of the
 * widget.
 *
 * Every entry this returns produces a chart. That is a lower bar than it
 * sounds: the control used to offer all four combinations unconditionally
 * and most of them returned an empty chart, because the compute layer
 * routes on the QUESTION's type, not the widget's:
 *
 *   - No question at all — `stack_by` is refused by both the values
 *     endpoint and the save validator, so nothing can be offered.
 *   - An option question stacks by its own options (`option`), over any
 *     grouping. `parent_id` is silently ignored on this path.
 *   - A number question stacks by site (`parent_id`), and only when
 *     grouped by month or date. `option` is ignored on this path.
 *   - Another question's options require `group_by=option`: that
 *     cross-tab is the only shape reading both questions. Grouped by
 *     month or site the measured question contributes nothing, and the
 *     same chart is already spelled by measuring the other question
 *     directly.
 *
 * The `q:` prefix exists only because antd's Select carries a scalar
 * value and this control writes two config fields. It is unwrapped on
 * change and never stored in `config` nor sent to the API — what gets
 * stored is `{stack_by: "option", stack_question: <id>}`.
 */
export const stackByOptions = (
  questions = [],
  widgetQuestionId = null,
  groupBy = null,
  family = [],
  widgetFormId = null
) => {
  const none = VALID_STACK_BY.filter((s) => s.value === "");
  const question = (questions || []).find((q) => q.id === widgetQuestionId);
  if (!question) {
    return none;
  }
  if (question.type === "number") {
    return groupBy === "month" || groupBy === "date"
      ? [...none, ...VALID_STACK_BY.filter((s) => s.value === "parent_id")]
      : none;
  }
  if (!STACK_QUESTION_TYPES.has(question.type)) {
    return none;
  }
  const own = VALID_STACK_BY.filter((s) => s.value === "option");

  // Cross-form joins per site, so it lives under `parent_id` — the only
  // grouping where both responses key on the registration datapoint id.
  // A multi-select measured question is excluded: the join takes a site's
  // single category answer, and offering a question whose answer it would
  // truncate is offering a chart that quietly drops data.
  if (groupBy === "parent_id") {
    if (question.type !== "option") {
      return [...none, ...own];
    }
    const groups = (family || [])
      .filter((f) => f.id !== widgetFormId)
      .map((f) => ({
        label: f.name,
        options: (f.questions || [])
          .filter((q) => STACK_QUESTION_TYPES.has(q.type))
          .map((q) => ({
            value: `f:${f.id}:${q.id}`,
            label: q.label || q.name,
            type: q.type,
          })),
      }))
      .filter((g) => g.options.length > 0);
    return [...none, ...own, ...groups];
  }

  if (groupBy !== "option") {
    return [...none, ...own];
  }
  return [
    ...none,
    ...own,
    // The widget's own question is left out: stacking by it is already
    // spelled "Option value", and cross-tabbing a question against
    // itself is a diagonal — one non-zero segment per bar.
    ...(questions || [])
      .filter(
        (q) => STACK_QUESTION_TYPES.has(q.type) && q.id !== widgetQuestionId
      )
      .map((q) => ({
        value: `q:${q.id}`,
        label: q.label || q.name,
        type: q.type,
      })),
  ];
};

/**
 * The `group_by` values that actually draw, for this question and stack.
 *
 * Measured against the compute layer rather than assumed, because the
 * control offered four choices and — for the most common widget on the
 * board, an unstacked option question — exactly one of them returned any
 * rows. The other three drew an empty chart and said nothing, which is
 * the same defect the Stack by list had.
 *
 *   - No question, or a date question: the request is a count of
 *     submissions, which can be bucketed by time or by site. `option`
 *     collapses to a single "Total" bar.
 *   - An option question, unstacked: only its own options. Grouping by
 *     month or site returns nothing at all — the compute layer has no
 *     branch for it.
 *   - An option question, stacked: all four, because the stack handlers
 *     cover every grouping.
 *   - A number question: bucketed by time or by site; `option` is
 *     meaningless and collapses to one bar. Stacked by site it narrows
 *     to time, which is the only shape handle_stack_by_parent draws.
 */
export const groupByOptions = (question = null, config = {}) => {
  const by = (...values) =>
    VALID_GROUP_BY.filter((g) => values.includes(g.value));
  const stackBy = config?.stack_by;
  const stackQuestion = config?.stack_question;

  // A cross-form stack joins two responses on the registration datapoint,
  // which is only a key under parent_id. Checked before the question type
  // because it holds whatever the question is — and checked FIRST because
  // omitting it snapped a working cross-form widget's grouping to
  // `option`, which the serializer then refused.
  if (config?.stack_form) {
    return by("parent_id");
  }

  if (!question || !SUPPORTED_GROUP_QUESTION_TYPES.has(question.type)) {
    return by("month", "date", "parent_id");
  }
  if (question.type === "number") {
    return stackBy === "parent_id"
      ? by("month", "date")
      : by("month", "date", "parent_id");
  }

  // option / multiple_option, where the stack decides what the bars can
  // be:
  //
  //   no stack           its own options, and nothing else draws at all
  //   another question   a cross-tab, which is defined only over options
  //   itself             the bars must be something ELSE — a question
  //                      crossed with itself is a diagonal, one segment
  //                      per bar, and the backend declines to draw it
  if (!stackBy) {
    return by("option");
  }
  return stackQuestion ? by("option") : by("month", "date", "parent_id");
};

/**
 * The same config with a grouping the new question cannot draw replaced.
 *
 * Switching an option question for a number one strands `group_by=option`,
 * which draws a single "Total" bar rather than erroring — the quiet kind
 * of wrong. Snapping to the first valid value keeps the chart honest
 * without asking the author to notice.
 */
export const withValidGroupBy = (config, choices) => {
  const current = config?.group_by || "option";
  if (choices.some((c) => c.value === current)) {
    return config;
  }
  return { ...config, group_by: choices[0]?.value || null };
};

/**
 * The number questions a bar can be measured by (VIZ-015.b).
 *
 * Offered only when the measured question is option-typed: the value
 * supplies the bar's HEIGHT and the measured question supplies the bars,
 * so with a number question there would be nothing to give a height to.
 */
export const valueQuestionOptions = (questions = [], question = null) => {
  if (!question || !STACK_QUESTION_TYPES.has(question.type)) {
    return [];
  }
  return (questions || [])
    .filter((q) => q.type === "number")
    .map((q) => ({ value: q.id, label: q.label || q.name, type: q.type }));
};

/**
 * The value types offered, given whether the bars carry a value question.
 *
 * Counting bars keep both. A value question keeps Percentage only under
 * `sum`, because a percentage needs a denominator that is a total of the
 * same quantity: summed bars have one — the bar's own total, so "of the
 * households this agency serves, 85% are under an approved plan" — and
 * average/max/min/last do not. A sum of averages is not a quantity, which
 * leaves only submission counts as denominators, and dividing money by
 * rows is the number D-2 refused to draw.
 */
export const valueTypeOptions = (config = {}) => {
  if (!config.value_question) {
    return VALID_VALUE_TYPE;
  }
  return config.repeat_agg === "sum"
    ? VALID_VALUE_TYPE
    : VALID_VALUE_TYPE.filter((v) => v.value !== "percentage");
};

/**
 * The aggregations offered for a given split.
 *
 * `sum` is withheld when the split is multi-choice. A submission
 * selecting three options contributes its full value to each, which is
 * right for an average — "average cost among projects involving X" — and
 * wrong for a sum, because the bar would then total three times the money
 * that exists and a stacked bar reads as a partition of a whole (D-1).
 */
export const repeatAggOptions = (splitIsMulti = false, stacked = false) =>
  splitIsMulti && stacked
    ? VALID_REPEAT_AGG.filter((a) => a.value !== "sum")
    : VALID_REPEAT_AGG;

/**
 * The one "Break down by" list a bar chart needs (VIZ-015 S-13).
 *
 * Group by and Stack by were two controls over one idea, and neither
 * could be read without the other: the cross-form questions only
 * appeared once Group by was already `parent_id`, and Group by hid
 * itself whenever the stack left it one value. Both are folded into a
 * single list of *the other dimension* — the axis when that is time or
 * site, the segments when it is another question.
 *
 * Bar only. A line chart's request path fixes `group_by=month` and has
 * its own X axis and Category controls (VIZ-013), and a pie has no
 * stack, so neither has two controls to merge.
 *
 * Entries carry `icon` for the fixed choices and `type` for questions,
 * so the picker never has to map a value back to a glyph.
 */
export const breakdownOptions = (
  question = null,
  questions = [],
  family = [],
  widgetFormId = null
) => {
  if (!question) {
    return [];
  }

  const time = [
    { value: "month", label: "Month", icon: "date" },
    { value: "date", label: "Date", icon: "date" },
  ];
  const site = { value: "parent_id", label: "Registration site", icon: "site" };

  // A number question has no options of its own, so there is no "None":
  // an ungrouped number is one bar labelled Total, which is a KPI.
  if (question.type === "number") {
    return [...time, site];
  }
  if (!STACK_QUESTION_TYPES.has(question.type)) {
    return [];
  }

  const own = [
    { value: "", label: "None — this question's options", icon: null },
  ];
  // The widget's own question is left out: it is already spelled
  // "None", and crossing a question with itself is a diagonal the
  // backend declines to draw.
  const siblings = (questions || [])
    .filter((q) => STACK_QUESTION_TYPES.has(q.type) && q.id !== question.id)
    .map((q) => ({
      value: `q:${q.id}`,
      label: q.label || q.name,
      type: q.type,
    }));

  // Cross-form entries used to be reachable only after setting Group by
  // to Registration site, which is the discoverability problem this
  // merge exists to remove. They now sit in the same list, and picking
  // one writes `group_by=parent_id` itself.
  //
  // Withheld for a multi-select measured question: the join takes a
  // site's single category answer, so offering it would offer a chart
  // that quietly drops data.
  const crossForm =
    question.type === "option"
      ? (family || [])
          .filter((f) => f.id !== widgetFormId)
          .map((f) => ({
            label: f.name,
            options: (f.questions || [])
              .filter((q) => STACK_QUESTION_TYPES.has(q.type))
              .map((q) => ({
                value: `f:${f.id}:${q.id}`,
                label: q.label || q.name,
                type: q.type,
              })),
          }))
          .filter((g) => g.options.length > 0)
      : [];

  return [...own, ...time, site, ...siblings, ...crossForm];
};

/** The merged Select's value for a stored config. */
export const breakdownValueOf = (config = {}) => {
  if (config.stack_form && config.stack_question) {
    return `f:${config.stack_form}:${config.stack_question}`;
  }
  if (config.stack_question) {
    return `q:${config.stack_question}`;
  }
  // `group_by` is the axis for every remaining entry; absent reads as
  // "the question's own options", which is what `option` means.
  const groupBy = config.group_by || "option";
  return groupBy === "option" ? "" : groupBy;
};

/**
 * The config fields one merged choice writes.
 *
 * All four in one object: `stack_question` and `stack_form` must be
 * cleared as deliberately as they are set, or switching from a cross-tab
 * to Month leaves a question id that the endpoint refuses under a
 * grouping it does not belong to.
 */
export const breakdownChangeOf = (value, question = null) => {
  const cleared = {
    group_by: null,
    stack_by: null,
    stack_question: null,
    stack_form: null,
  };
  const isOption = question && STACK_QUESTION_TYPES.has(question.type);
  // An option question keeps `stack_by=option` on every axis: the bars
  // are the axis and its own options are the segments. A number question
  // has nothing to segment by, so it never stacks.
  const ownStack = isOption ? "option" : null;

  if (String(value).startsWith("f:")) {
    const [, formId, questionId] = String(value).split(":");
    return {
      ...cleared,
      group_by: "parent_id",
      stack_by: "option",
      stack_form: Number(formId),
      stack_question: Number(questionId),
    };
  }
  if (String(value).startsWith("q:")) {
    return {
      ...cleared,
      group_by: "option",
      stack_by: "option",
      stack_question: Number(String(value).slice(2)),
    };
  }
  if (!value) {
    return { ...cleared, group_by: "option" };
  }
  return { ...cleared, group_by: value, stack_by: ownStack };
};

/** Snap a breakdown the new question cannot draw onto one it can. */
export const withValidBreakdown = (config, choices) => {
  const flatten = (list) =>
    list.reduce(
      (acc, entry) => acc.concat(entry.options ? entry.options : [entry]),
      []
    );
  const values = flatten(choices).map((c) => c.value);
  const current = breakdownValueOf(config);
  if (values.includes(current)) {
    return config;
  }
  return { ...config, ...breakdownChangeOf(values[0] ?? "", null) };
};

/**
 * The Select value a config represents.
 *
 * Three encodings for one control, because antd carries a scalar while
 * the choice writes up to three config fields. Both prefixes are UI-only
 * and never reach `config` or the API.
 */
export const stackValueOf = (config) => {
  if (config?.stack_form && config?.stack_question) {
    return `f:${config.stack_form}:${config.stack_question}`;
  }
  if (config?.stack_question) {
    return `q:${config.stack_question}`;
  }
  return config?.stack_by || "";
};

/**
 * The config fields a Select value writes.
 *
 * Returned as one object so the caller can apply them in a single state
 * update: two `updateConfig` calls would each close over the same widget,
 * and the second would put the first's field back.
 */
export const stackChangeOf = (value, currentGroupBy) => {
  if (value.startsWith("f:")) {
    const [formId, questionId] = value.slice(2).split(":");
    return {
      stack_by: "option",
      stack_question: Number(questionId),
      stack_form: Number(formId),
      // Cross-form only draws per site. Pinned here rather than left to
      // the Group by control so the config is never momentarily invalid.
      group_by: "parent_id",
    };
  }
  if (value.startsWith("q:")) {
    return {
      stack_by: "option",
      stack_question: Number(value.slice(2)),
      stack_form: null,
      group_by: currentGroupBy,
    };
  }
  return {
    stack_by: value || null,
    stack_question: null,
    stack_form: null,
    group_by: currentGroupBy,
  };
};

/**
 * The same config with a stack choice the new shape cannot draw removed.
 *
 * Changing the question or the grouping can strand a stack selection —
 * picking a number question after stacking by options, say — and the
 * stranded value is not merely cosmetic: the values endpoint 400s on it
 * and the save validator refuses the widget. Clearing it as the shape
 * changes keeps the inspector from producing a config it cannot save.
 */
export const withValidStack = (config, choices) => {
  const current = stackValueOf(config);
  // Groups carry their entries in `options`; flat entries carry `value`.
  const offered = choices.some((c) =>
    c.options ? c.options.some((o) => o.value === current) : c.value === current
  );
  if (offered) {
    return config;
  }
  return { ...config, stack_by: null, stack_question: null, stack_form: null };
};

export const VALID_ORIENTATION = [
  { value: "vertical", label: "Vertical" },
  { value: "horizontal", label: "Horizontal" },
];

export const VALID_PIE_VARIANT = [
  { value: "pie", label: "Pie" },
  { value: "doughnut", label: "Doughnut" },
];

export const VALID_MEASURE = [
  { value: "current_state", label: "Current status of each site" },
  { value: "all_submissions", label: "Every submission over time" },
];

export const VALID_CRITERIA_TYPES = [
  { value: "option_equals", label: "Option equals" },
  { value: "threshold_gt", label: "Greater than" },
  { value: "threshold_lt", label: "Less than" },
];

export const WIDTH_PRESETS = [
  { col_span: 6, frac: "\u00BC", label: "Quarter" },
  { col_span: 8, frac: "\u2153", label: "Third" },
  { col_span: 12, frac: "\u00BD", label: "Half" },
  { col_span: 24, frac: "1", label: "Full" },
];

export const COLOR_SWATCHES = [
  "#1890ff",
  "#1651b6",
  "#64A73B",
  "#F5A623",
  "#e41a1c",
  "#9b59b6",
  "#00bcd4",
  "#795548",
];

// ColorBrewer-derived palettes — 5 colours each, 5 palettes.
// Reference: https://colorbrewer2.org/
export const COLOR_SCHEMES = {
  categorical: {
    label: "Categorical",
    colors: ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"],
  },
  blues: {
    label: "Blue shades",
    colors: ["#084594", "#2171b5", "#4292c6", "#6baed6", "#9ecae1"],
  },
  greens: {
    label: "Green shades",
    colors: ["#006d2c", "#31a354", "#74c476", "#a1d99b", "#c7e9c0"],
  },
  pastel: {
    label: "Pastel",
    colors: ["#b3cde3", "#ccebc5", "#decbe4", "#fed9a6", "#fbb4ae"],
  },
  warm: {
    label: "Warm",
    colors: ["#bd0026", "#f03b20", "#fd8d3c", "#fecc5c", "#ffffb2"],
  },
};

export const DEFAULT_COLOR_SCHEME = "categorical";

export const NEEDS_FORM = new Set([
  "kpi",
  "bar",
  "line",
  "pie",
  "table",
  "map",
  "scatter",
]);
export const NEEDS_QUESTION = new Set([
  "kpi",
  "bar",
  "line",
  "pie",
  "map",
  "scatter",
]);
export const NEEDS_GROUP_BY = new Set(["bar", "pie"]);
export const NEEDS_STACK_BY = new Set(["bar"]);
export const NEEDS_VALUE_TYPE = new Set(["kpi", "bar", "pie"]);
export const NEEDS_REPEAT_AGG = new Set(["kpi", "bar"]);
export const NEEDS_COLOR = new Set([
  "kpi",
  "bar",
  "line",
  "pie",
  "map",
  "scatter",
]);

// Every widget type that can carry a measure — a table's rows are already
// "latest per site" by construction, and a section title has no data.
export const NEEDS_MEASURE = new Set([
  "kpi",
  "bar",
  "line",
  "pie",
  "map",
  "scatter",
]);
export const NEEDS_SCATTER_Y = new Set(["scatter"]);
export const NEEDS_LINE_DATE_X = new Set(["line"]);
export const NEEDS_LINE_CATEGORY = new Set(["line"]);

/**
 * The measure a widget should carry for the form it is bound to, or null.
 *
 * `current_state` means "the latest submission per site", which is only
 * defined relative to a monitoring form; the server rejects it anywhere
 * else ("measure current_state requires a monitoring form"). Both places
 * that write a measure — the palette's new-widget defaults and the
 * inspector's form picker — go through here, because when they disagreed
 * every newly added chart widget was born unsavable: WIDGET_DEFAULTS
 * seeded `current_state` unconditionally while a new widget is bound to
 * `/sources.forms[0]`, which is always the root registration form.
 */
export const defaultMeasure = (type, form) =>
  NEEDS_MEASURE.has(type) && form?.type === "monitoring"
    ? "current_state"
    : null;

/**
 * The forms a table widget may bind to.
 *
 * /escalation is a "registration parent plus its latest monitoring child"
 * query and the widget's own form is the monitoring side, so a table bound
 * to the registration form matches nothing — `latest_id__isnull=False`
 * excludes every row — and returns count: 0 whatever its columns say.
 */
export const monitoringForms = (forms = []) =>
  (forms || []).filter((f) => f.type === "monitoring");

/**
 * The columns a table can offer, across both sides of that join.
 *
 * A table's columns come from two forms and the source differs by which:
 * a registration question is read off the parent (`parent_answer`), a
 * monitoring question off the latest submission (`answer`). The inspector
 * used to write `answer` for everything and only offer the widget's own
 * form, so registration attributes were either unreachable or fetched from
 * the wrong side of the join and came back empty.
 *
 * The key carries the source because the response is keyed by it.
 */
export const tableColumnOptions = (forms = [], widgetFormId = null) => {
  const root = (forms || []).find((f) => f.type === "registration");
  const monitoring = (forms || []).find((f) => f.id === widgetFormId);
  const from = (form, source) =>
    (form?.questions || []).map((q) => ({
      key: `${source}_${q.id}`,
      label: q.label || q.name,
      source,
      question: q.id,
      formName: form.name,
    }));
  return [...from(root, "parent_answer"), ...from(monitoring, "answer")];
};

/**
 * Drop config entries bound to questions the new form does not have.
 *
 * Changing a widget's form already clears `widget.question`, but a table's
 * columns and criteria carry question ids of their own and used to survive
 * the switch. That left a table on one form referencing another form's
 * question, which the backend rejects — a column's question must belong to
 * the widget's form — so the whole table went blank with no explanation.
 *
 * Entries with no question (parent_name, administration) are
 * form-independent and are kept.
 *
 * `stack_question` is a bare id rather than an entry in a list, so it
 * needs its own line here — a bar stacked by a question of the old form
 * would otherwise survive the switch and be rejected on save.
 */
export const pruneConfigForForm = (config, questions = []) => {
  const allowed = new Set((questions || []).map((q) => q.id));
  const belongs = (entry) => !entry?.question || allowed.has(entry.question);
  const next = { ...(config || {}) };
  if (next.value_question && !allowed.has(next.value_question)) {
    next.value_question = null;
  }
  if (next.stack_question && !allowed.has(next.stack_question)) {
    next.stack_question = null;
    // The pair is meaningless apart: a stack form with no question asks
    // for nothing, and the save validator refuses it.
    next.stack_form = null;
  }
  if (Array.isArray(next.columns)) {
    next.columns = next.columns.filter(belongs);
  }
  if (Array.isArray(next.criteria)) {
    next.criteria = next.criteria.filter(belongs);
  }
  return next;
};

export const TYPE_LABELS = {
  kpi: "KPI",
  bar: "Bar",
  line: "Line",
  pie: "Pie",
  scatter: "Scatter",
  table: "Table",
  map: "Map",
  section_title: "Text",
};
