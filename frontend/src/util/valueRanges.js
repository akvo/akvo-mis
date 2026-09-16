// =========================================================
// Value ranges for a map bound to a value question (#387)
// =========================================================
//
// Lives here rather than in builderConstants because the RENDERER needs
// two of the three: a published dashboard colours its points and draws
// its legend with no builder loaded at all. Importing the builder's
// constants into a widget would pull the whole authoring vocabulary —
// colour schemes, table columns, stack rules — into the viewer bundle
// to read one lookup.

// Only reached when a caller passes no palette at all; every real one
// passes the widget's `chart_colors`. Importing the builder's default
// here would re-create exactly the dependency this module exists to
// avoid.
const FALLBACK_PALETTE = ["#1890ff"];

//
// A map bound to a value question colours each point by which band its
// answer falls in. The bands live in `config.value_ranges`, ordered
// ascending, the last one open:
//
//   [{to: 340, color}, {to: 890, color}, {to: null, color}]
//
// `to` is exclusive, so a point takes the FIRST band whose `to` it falls
// under. That matches how the bands read on screen — "under 340",
// "340 – 890" — and puts a value sitting exactly on a break in the band
// above it, where a reader looking at those labels would expect it.

/**
 * Round a raw step up to a "nice" number: 1, 2, 5, 10, 20, 50, …
 */
const niceStep = (raw) => {
  if (raw <= 0) {
    return 1;
  }
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  if (norm <= 1) {
    return mag;
  }
  if (norm <= 2) {
    return 2 * mag;
  }
  if (norm <= 5) {
    return 5 * mag;
  }
  return 10 * mag;
};

/**
 * Seed bands from the values a map is about to draw.
 *
 * Quantiles, not equal intervals. The numbers a value question carries —
 * population served, litres per day, beneficiaries — cluster low with a
 * long tail, and equal intervals put nearly every point in the first
 * band and draw the map one colour. Quantiles spread the points across
 * the palette, which is the whole reason to colour them.
 *
 * Runs once, when the author turns ranges on. After that the numbers are
 * theirs: breaks recomputed from live data would move with the
 * dashboard's date and administration filters, so the same colour would
 * mean different things on the same map and the legend would rewrite
 * itself under the reader.
 *
 * Non-numeric answers are dropped rather than read as zero — a site that
 * did not answer would otherwise drag the lowest break down and take the
 * first band with it.
 */
export const quantileRanges = (values = [], colors = [], count = 3) => {
  const palette = colors?.length ? colors : FALLBACK_PALETTE;
  const at = (i) => palette[i % palette.length];

  const sorted = (values || [])
    .map((v) => (v === null || v === "" ? NaN : Number(v)))
    .filter((v) => Number.isFinite(v))
    .sort((a, b) => a - b);

  if (!sorted.length) {
    return [{ to: null, color: at(0) }];
  }

  const max = sorted[sorted.length - 1];
  const step = niceStep(max / count);

  const breaks = [];
  for (let i = 1; i < count; i += 1) {
    breaks.push(step * i);
  }

  return [
    ...breaks.map((to, i) => ({ to, color: at(i) })),
    { to: null, color: at(breaks.length) },
  ];
};

/**
 * The colour a point takes, or `fallback` when it has no band.
 *
 * A point with no answer falls back rather than colouring as zero: on a
 * map of population served, "not reported" and "nobody" are different
 * facts and must not share a colour.
 */
export const colorForValue = (value, ranges = [], fallback = null) => {
  if (!ranges?.length) {
    return fallback;
  }
  const v = value === null || value === "" ? NaN : Number(value);
  if (!Number.isFinite(v)) {
    return fallback;
  }
  const band = ranges.find((r) => r.to !== null && v < r.to);
  return (band || ranges[ranges.length - 1])?.color ?? fallback;
};

/**
 * A band boundary as a reader sees it — grouped, never raw.
 *
 * Exported because the inspector labels the open band with it and the
 * legend labels every band with it, and a boundary printed two ways in
 * two places is a boundary a reader has to reconcile.
 */
export const readable = (n) => Number(n).toLocaleString();

/**
 * How one band reads in the legend and the inspector.
 *
 * Bounds are spelled out rather than written as "0–340", because the
 * first band has no floor the author set and the last has no ceiling;
 * printing 0 would claim a lower bound the data never promised.
 */
export const rangeLabel = (ranges = [], index = 0) => {
  const band = ranges[index];
  if (!band) {
    return "";
  }
  const previous = index > 0 ? ranges[index - 1]?.to : null;
  if (band.to === null) {
    return previous === null || typeof previous === "undefined"
      ? "All values"
      : `${readable(previous)} and above`;
  }
  return index === 0
    ? `under ${readable(band.to)}`
    : `${readable(previous)} – ${readable(band.to)}`;
};
