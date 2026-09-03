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
    type: "scatter",
    label: "Scatter plot",
    desc: "X/Y correlation",
    iconBg: "#eef2fb",
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
  { value: "option", label: "Option value" },
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
export const NEEDS_GROUP_BY = new Set(["bar", "line", "pie"]);
export const NEEDS_STACK_BY = new Set(["bar", "line"]);
export const NEEDS_VALUE_TYPE = new Set(["kpi", "bar", "line", "pie"]);
export const NEEDS_REPEAT_AGG = new Set(["kpi", "bar", "line"]);
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
 */
export const pruneConfigForForm = (config, questions = []) => {
  const allowed = new Set((questions || []).map((q) => q.id));
  const belongs = (entry) => !entry?.question || allowed.has(entry.question);
  const next = { ...(config || {}) };
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
