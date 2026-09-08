// =========================================================
// Exporting the dashboard viewer to PNG or PDF (VIZ-023)
// =========================================================
//
// The whole pipeline runs in the browser: rasterize the viewer's DOM,
// then either hand the canvas over as a PNG or slice it into A4 pages.
// Nothing here is React, and nothing here talks to the API — the DOM
// already is the filtered state, which is why "the export reflects the
// current filters" needs no code at all.
//
// html2canvas needs real layout and does not run under jsdom, so the
// arithmetic that decides where pages break lives in `paginate` below,
// on its own, where it can be tested.

/**
 * Split a dashboard's height into A4-sized pages that never cut a card.
 *
 * @param {number[]} breaks  Candidate cut lines: the bottom edge of every
 *                           widget card, in CSS pixels from the top of
 *                           the captured element. Order does not matter.
 * @param {number} totalHeight  Full height of the captured element.
 * @param {number} pageHeight   How much of it fits on one page. Must be
 *                              greater than zero — a non-positive or NaN
 *                              height cannot advance the walk, so it
 *                              throws rather than hanging.
 * @returns {Array<[number, number]>}  `[startY, endY]` per page, tiling
 *                           `0..totalHeight` with no gaps or overlaps.
 * @throws {Error} If `pageHeight` is not a positive number.
 */
export const paginate = (breaks, totalHeight, pageHeight) => {
  // Refused here rather than at the call site: throwing turns it into
  // the "couldn't export this dashboard" message the viewer already shows.
  if (!(pageHeight > 0)) {
    throw new Error("paginate: pageHeight must be a positive number");
  }

  // Sorted once here rather than required of the caller: `.pop()` below
  // means "the lowest card that still fits", and that is only true of an
  // ascending list.
  const sorted = [...breaks].sort((a, b) => a - b);
  const pages = [];
  let start = 0;

  while (start < totalHeight) {
    const limit = start + pageHeight;

    // The remainder fits: take it whole rather than looking for a break
    // that would only add a page with nothing after it.
    if (limit >= totalHeight) {
      pages.push([start, totalHeight]);
      break;
    }

    const fit = sorted.filter((b) => b > start && b <= limit).pop();

    // No card boundary inside this page means one card is taller than a
    // page — a long table, or a map on a short page. There is nothing to
    // cut at, so cut at the page edge. A seam through one card beats a
    // loop that cannot advance.
    const end = fit ?? limit;

    pages.push([start, end]);
    start = end;
  }

  return pages;
};
