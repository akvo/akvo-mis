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
    type: "section_title",
    label: "Section title",
    desc: "Group your widgets",
    iconBg: "#f0f1f4",
  },
];

export const WIDGET_DEFAULTS = {
  kpi: {
    col_span: 6,
    color: "#1890ff",
    config: { measure: "current_state", value_type: "number" },
  },
  bar: {
    col_span: 12,
    color: "#1890ff",
    config: { measure: "current_state", group_by: "option" },
  },
  line: {
    col_span: 12,
    color: "#1651b6",
    config: { measure: "current_state", group_by: "month" },
  },
  pie: {
    col_span: 8,
    color: "#64A73B",
    config: {
      measure: "current_state",
      group_by: "option",
      variant: "pie",
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
    config: {},
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

export const NEEDS_FORM = new Set([
  "kpi",
  "bar",
  "line",
  "pie",
  "table",
  "map",
]);
export const NEEDS_QUESTION = new Set(["kpi", "bar", "line", "pie", "map"]);
export const NEEDS_GROUP_BY = new Set(["bar", "line", "pie"]);
export const NEEDS_STACK_BY = new Set(["bar", "line"]);
export const NEEDS_VALUE_TYPE = new Set(["kpi", "bar", "line", "pie"]);
export const NEEDS_REPEAT_AGG = new Set(["kpi", "bar", "line"]);
export const NEEDS_COLOR = new Set(["kpi", "bar", "line", "pie", "map"]);

export const TYPE_LABELS = {
  kpi: "KPI",
  bar: "Bar",
  line: "Line",
  pie: "Pie",
  table: "Table",
  map: "Map",
  section_title: "Text",
};
