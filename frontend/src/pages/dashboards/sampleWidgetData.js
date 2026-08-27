const SAMPLE_BAR = [
  { label: "Borehole", value: 42 },
  { label: "Protected spring", value: 28 },
  { label: "Piped supply", value: 65 },
  { label: "Rainwater", value: 17 },
];

const SAMPLE_LINE = [
  { label: "Jan", value: 12 },
  { label: "Feb", value: 19 },
  { label: "Mar", value: 15 },
  { label: "Apr", value: 25 },
  { label: "May", value: 22 },
  { label: "Jun", value: 30 },
];

const SAMPLE_PIE = [
  { label: "Operational", value: 55 },
  { label: "Needs repair", value: 25 },
  { label: "Non-functional", value: 20 },
];

const SAMPLE_KPI = { value: 284 };

const SAMPLE_TABLE = [
  {
    id: 1,
    parent_name: "Nadi Central EPS",
    administration: "Nadi",
    latest_date: "2026-07-09",
  },
  {
    id: 2,
    parent_name: "Lautoka North EPS",
    administration: "Lautoka",
    latest_date: "2026-07-06",
  },
  {
    id: 3,
    parent_name: "Ba Riverside EPS",
    administration: "Ba",
    latest_date: "2026-07-02",
  },
];

// Matches what useWidgetData produces for a map: geolocation rows joined
// with their status bucket. `geo` is [lat, lng], as /maps/geolocation
// returns it.
const SAMPLE_MAP = [
  {
    id: 1,
    name: "Nadi Central EPS",
    geo: [-17.78, 177.94],
    status: "Operational",
  },
  {
    id: 2,
    name: "Lautoka North EPS",
    geo: [-17.62, 177.45],
    status: "Issue",
  },
  {
    id: 3,
    name: "Ba Riverside EPS",
    geo: [-17.53, 177.67],
    status: "Operational",
  },
  {
    id: 4,
    name: "Suva South EPS",
    geo: [-18.14, 178.44],
    status: "Operational",
  },
];

const getSampleData = (type) => {
  if (type === "kpi") {
    return SAMPLE_KPI;
  }
  if (type === "bar") {
    return SAMPLE_BAR;
  }
  if (type === "line") {
    return SAMPLE_LINE;
  }
  if (type === "pie") {
    return SAMPLE_PIE;
  }
  if (type === "table") {
    return SAMPLE_TABLE;
  }
  if (type === "map") {
    return SAMPLE_MAP;
  }
  return null;
};

export default getSampleData;
