/**
 * Cross-form stacked bars: joining two /values responses by site.
 *
 * VIZ-015 stacks a bar by another question of the SAME form, in one
 * request the backend computes. This is the other shape: the bars come
 * from one form and the stacks from another, which no single query can
 * express — so it is two ordinary `group_by=parent_id&stack_by=option`
 * calls joined here, on the registration datapoint id both of them carry
 * as `row.group`. That id is the only key two forms in a family share.
 *
 * The two count different things, and the difference is the whole reason
 * this file exists rather than a flag on the other path: VIZ-015 counts
 * SUBMISSIONS per (option, option) cell, this counts SITES. A site
 * monitored twelve times contributes 12 there and 1 here.
 */

// Structural keys on a /values row. Everything else is an option column.
const NON_OPTION_KEYS = new Set(["label", "group"]);

/**
 * The option labels a row actually answered.
 *
 * `> 0` rather than `in row`: the response carries every option of the
 * question, zero-filled. Treating the counts as booleans is also what
 * lets one join serve both sides — a registration row's counts are 0 or
 * 1, a monitoring row's can be higher, and neither magnitude matters
 * here.
 */
const answeredOptions = (row) =>
  Object.keys(row).filter((key) => !NON_OPTION_KEYS.has(key) && row[key] > 0);

/**
 * Join a category and a series /values response into stacked bar rows.
 *
 * Both responses must be `group_by=parent_id`, which makes `row.group`
 * the registration datapoint's id on either side.
 *
 * @param {object} category  /values response whose options become the bars.
 * @param {object} series    /values response whose options become the stacks.
 * @returns {Array<object>}  One row per bar: `{label, [stackLabel]: count}`.
 */
export const stackAcrossForms = ({ category, series } = {}) => {
  const categoryRows = category?.data || [];
  const seriesRows = series?.data || [];
  if (categoryRows.length === 0) {
    return [];
  }

  // Pass 1: which bar each site belongs to. The category question is
  // validated single-select, so a site has one answer and `[0]` is it
  // rather than the first of several silently dropped.
  const barBySite = new Map();
  const ordered = [];
  categoryRows.forEach((row) => {
    const answered = answeredOptions(row);
    if (answered.length === 0) {
      // No category answer, so no bar to belong to. The site leaves the
      // chart entirely — which is why a chart over a sparsely monitored
      // family shows far fewer sites than exist, and is still correct.
      return;
    }
    barBySite.set(row.group, answered[0]);
    if (!ordered.includes(answered[0])) {
      ordered.push(answered[0]);
    }
  });

  // `label`, not `category`: akvo-charts reads the first key of a row as
  // its category axis, and the rest of the pipeline already assumes that
  // name.
  const bars = new Map(ordered.map((label) => [label, { label }]));

  // Pass 2: every site adds ONE per series option it selected, into its
  // own bar. `+ 1` and never `+ row[option]` — that single choice is the
  // per-site semantics, and reading the count instead would silently turn
  // this back into a submission count.
  seriesRows.forEach((row) => {
    const label = barBySite.get(row.group);
    if (typeof label === "undefined") {
      // In the series response but not the category one: a site that has
      // registration answers but has never been monitored. It has no bar,
      // and inventing one would be inventing data.
      return;
    }
    const bar = bars.get(label);
    answeredOptions(row).forEach((option) => {
      bar[option] = (bar[option] || 0) + 1;
    });
  });

  return Array.from(bars.values());
};

export default stackAcrossForms;
