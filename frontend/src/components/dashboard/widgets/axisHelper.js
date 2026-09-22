const UNITS = [
  { v: 1e9, s: "B" },
  { v: 1e6, s: "M" },
  { v: 1e3, s: "K" },
];

export const abbreviateNumber = (value) => {
  if (typeof value !== "number" || !isFinite(value)) {
    return `${value}`;
  }
  const unit = UNITS.find((u) => Math.abs(value) >= u.v);
  if (!unit) {
    return `${value}`;
  }
  const scaled = value / unit.v;
  return `${Number.isInteger(scaled) ? scaled : scaled.toFixed(1)}${unit.s}`;
};

export const valueAxisLabel = (isPercentage = false) => ({
  formatter: (value) => `${abbreviateNumber(value)}${isPercentage ? "%" : ""}`,
});
