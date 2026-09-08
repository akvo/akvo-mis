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

// Browsers cap canvas *area*, and the cap is far lower than it looks —
// around 16.7M pixels on iOS Safari. A 1120px-wide dashboard 4000px tall
// captured at devicePixelRatio 2 is 17.9M pixels, over the line.
//
// The failure mode is the dangerous one: no exception, just a blank
// canvas and an empty file. So the scale is computed to fit under the
// ceiling rather than fixed.
//
// There is deliberately no lower bound. A dashboard tall enough to force
// the scale below 0.5 exports soft, and that is the right way to lose —
// a floor would put the area back over the ceiling and produce nothing
// at all, which is the failure this whole calculation exists to avoid.
//
// The number is empirical rather than specified — browsers do not expose
// their own limit, and this is the lowest figure that holds across the
// devices this app targets. Raise it if iOS stops mattering, or drop the
// clamp entirely if this ever becomes desktop-only.
const MAX_CANVAS_AREA = 16000000;

const captureScale = (width, height) => {
  const areaFit = Math.sqrt(MAX_CANVAS_AREA / (width * height));
  return Math.min(window.devicePixelRatio || 1, areaFit);
};

// `<dashboard-name>-<date>.<ext>`, with anything unsafe collapsed to a
// hyphen. A dashboard named only in a non-Latin script slugs to nothing,
// hence the fallback.
const exportFilename = (name, ext) => {
  const slug = String(name || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const date = new Date().toISOString().slice(0, 10);
  return `${slug || "dashboard"}-${date}.${ext}`;
};

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

// Loaded on demand, not imported at the top. html2canvas-pro and jspdf
// are roughly 550KB minified together, and CRA does no route splitting
// here, so a static import would put all of it in the main bundle for
// every visitor on every page — including everyone who never exports
// anything. Same idiom as reportWebVitals.js.
const capture = async (node) => {
  const { default: html2canvas } = await import("html2canvas-pro");
  return html2canvas(node, {
    // The tile layer asks for CORS mode (VizMap), and this is the other
    // half of that arrangement: without it html2canvas re-fetches images
    // in no-CORS mode and taints the canvas anyway.
    useCORS: true,
    // html2canvas defaults to white. The viewer's ground is grey, and a
    // white one shows through every gap between cards, so the export
    // would not match the screen it is a picture of.
    backgroundColor: "#f0f2f5",
    scale: captureScale(node.scrollWidth, node.scrollHeight),
    logging: false,
  });
};

const toPng = (canvas, name) =>
  new Promise((resolve) => {
    canvas.toBlob((blob) => {
      downloadBlob(blob, exportFilename(name, "png"));
      resolve();
    }, "image/png");
  });

/**
 * Rasterize a dashboard and hand the visitor a file.
 *
 * @param {HTMLElement} node  The capture root — a plain block wrapper
 *                            whose natural height is the whole
 *                            dashboard, NOT the scrolling container.
 * @param {{format: "png"|"pdf", name: string}} options
 * @returns {Promise<void>}   Rejects if the capture fails; the caller
 *                            owns telling the visitor.
 */
export const exportDashboard = async (node, { format, name }) => {
  const canvas = await capture(node);
  await toPng(canvas, name);
};
