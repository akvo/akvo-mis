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

import moment from "moment";

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

// A4 portrait in millimetres, which is also jsPDF's unit below. The
// content box is what is left after margins, and it fixes everything
// else: fitting the capture's width to it decides the scale, and the
// scale decides how much dashboard fits on a page.
const MARGIN_MM = 10;
const CONTENT_WIDTH_MM = 210 - MARGIN_MM * 2;
const CONTENT_HEIGHT_MM = 297 - MARGIN_MM * 2;

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
  // Local date, not UTC: `toISOString` would file every export made
  // before 07:00 in this product's UTC+7 deployment under yesterday's date.
  const date = moment().format("YYYY-MM-DD");
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
  // Deferred a tick: Firefox has historically aborted the download when
  // the object URL is revoked in the same tick as the click that starts it.
  setTimeout(() => URL.revokeObjectURL(url), 0);
};

// Loaded on demand, not imported at the top. html2canvas-pro and jspdf
// are roughly 550KB minified together, and CRA does no route splitting
// here, so a static import would put all of it in the main bundle for
// every visitor on every page — including everyone who never exports
// anything. Same idiom as reportWebVitals.js.
/**
 * Stop the clone's CSS animations before it is rasterized.
 *
 * html2canvas renders a *copy* of the DOM in an offscreen iframe, and
 * inserting that copy restarts every CSS animation in it. Widget cards
 * carry `animation: dashFadeUp ... both` (viewer.scss), whose first
 * keyframe is `opacity: 0` — so the render catches them at or near t=0
 * and they come out faded, or missing altogether, while unanimated
 * chrome like the title and filter bar renders fine. Nothing in a still
 * image is meant to be mid-animation, so the whole clone is frozen.
 *
 * @param {Document} clonedDoc  html2canvas's cloned document.
 */
export const freezeAnimations = (clonedDoc) => {
  const frozen = clonedDoc.createElement("style");
  frozen.textContent =
    "*, *::before, *::after { animation: none !important; " +
    "transition: none !important; }";
  clonedDoc.head.appendChild(frozen);
};

const capture = async (node, geometry) => {
  const { default: html2canvas } = await import("html2canvas-pro");
  return html2canvas(node, {
    onclone: freezeAnimations,
    // The tile layer asks for CORS mode (VizMap), and this is the other
    // half of that arrangement: without it html2canvas re-fetches images
    // in no-CORS mode and taints the canvas anyway.
    useCORS: true,
    // White, not the viewer's grey ground. Matching the screen was the
    // first instinct, but the capture root is inset 50px by the layout's
    // gutters, so the grey came out as a band around the whole dashboard
    // — sitting inside the PDF's own 10mm white page margin and framing
    // the thing twice. On paper the margin is the frame; the widgets
    // carry their own white and a box-shadow to separate them.
    backgroundColor: "#ffffff",
    scale: captureScale(geometry.width, geometry.height),
    logging: false,
  });
};

const toPng = (canvas, name) =>
  new Promise((resolve, reject) => {
    // `toBlob` yields null rather than throwing when the encode fails,
    // and a throw inside this callback would not reject the promise —
    // the export would hang with the button spinning and nothing said.
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("toBlob returned no blob"));
        return;
      }
      try {
        downloadBlob(blob, exportFilename(name, "png"));
        resolve();
      } catch (error) {
        reject(error);
      }
    }, "image/png");
  });

// Measured once, before the capture, and passed to both halves. The
// rasterization takes seconds, and reading the live DOM again afterwards
// would let a window resize desynchronise the page geometry from the
// canvas the pages are cut out of — silently, as drifting seams or a
// blank final slice. `breaks` are the widget cards' bottom edges, which
// can only be read while there is still a DOM rather than pixels.
const measure = (node) => {
  const top = node.getBoundingClientRect().top;
  return {
    width: node.scrollWidth,
    height: node.scrollHeight,
    breaks: Array.from(node.querySelectorAll(".dashboard-view-cell")).map(
      (cell) => cell.getBoundingClientRect().bottom - top
    ),
  };
};

const toPdf = async (canvas, geometry, name) => {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });

  // Width fixes the scale: the capture is made to span the content box,
  // and everything else follows from that ratio.
  const mmPerPx = CONTENT_WIDTH_MM / geometry.width;
  const pageHeightCss = CONTENT_HEIGHT_MM / mmPerPx;

  // The master canvas was rendered at `captureScale`, so it is that many
  // times larger than the CSS pixels the page breaks are expressed in.
  // Derived from the canvas rather than recomputed, so the two cannot
  // drift apart.
  const pixelRatio = canvas.width / geometry.width;

  const pages = paginate(geometry.breaks, geometry.height, pageHeightCss);

  pages.forEach(([start, end], index) => {
    const sliceHeight = Math.round((end - start) * pixelRatio);
    const slice = document.createElement("canvas");
    slice.width = canvas.width;
    slice.height = sliceHeight;
    slice
      .getContext("2d")
      .drawImage(
        canvas,
        0,
        Math.round(start * pixelRatio),
        canvas.width,
        sliceHeight,
        0,
        0,
        canvas.width,
        sliceHeight
      );

    if (index > 0) {
      pdf.addPage();
    }

    // PNG rather than JPEG: lossless, and JPEG ringing is plainly
    // visible on thin axis lines and small chart labels. The cost is size — a
    // long dashboard can run to several MB.
    // If real exports come back too heavy to email, the switch is
    // slice.toDataURL("image/jpeg", 0.9).
    pdf.addImage(
      slice.toDataURL("image/png"),
      "PNG",
      MARGIN_MM,
      MARGIN_MM,
      CONTENT_WIDTH_MM,
      (end - start) * mmPerPx
    );
  });

  pdf.save(exportFilename(name, "pdf"));
};

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
  const geometry = measure(node);
  const canvas = await capture(node, geometry);
  if (format === "pdf") {
    await toPdf(canvas, geometry, name);
    return;
  }
  await toPng(canvas, name);
};
