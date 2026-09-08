import { freezeAnimations, paginate } from "../dashboardExport";

// =========================================================
// Page-break arithmetic
// =========================================================
//
// This is the only part of the export with logic worth testing.
// html2canvas needs real layout and cannot run under jsdom, so the
// module is split to put the arithmetic on this side of that line.
//
// Heights are CSS pixels throughout. A "break" is the bottom edge of a
// widget card: a y-offset the PDF is allowed to cut at.

describe("paginate", () => {
  test("content shorter than a page is one page", () => {
    expect(paginate([300], 500, 1000)).toEqual([[0, 500]]);
  });

  test("a page ends at the last card that fits on it", () => {
    // Cards end at 300, 700 and 1100; a page holds 800. Cutting at 800
    // would saw through the card that runs from 700 to 1100, so the
    // page ends at 700 and gives up 100px of height to stay whole.
    expect(paginate([300, 700, 1100], 1100, 800)).toEqual([
      [0, 700],
      [700, 1100],
    ]);
  });

  test("with no cards to cut at, it falls back to fixed slices", () => {
    expect(paginate([], 2500, 1000)).toEqual([
      [0, 1000],
      [1000, 2000],
      [2000, 2500],
    ]);
  });

  test("a card taller than a page is cut, and the loop still ends", () => {
    // One card spanning the whole height offers no legal break, so
    // there is nothing to do but cut it. The point of the assertion is
    // that this terminates: an implementation that insisted on a legal
    // break here would spin forever.
    expect(paginate([1500], 1500, 1000)).toEqual([
      [0, 1000],
      [1000, 1500],
    ]);
  });

  test("breaks need not arrive sorted", () => {
    expect(paginate([1100, 300, 700], 1100, 800)).toEqual([
      [0, 700],
      [700, 1100],
    ]);
  });

  test("no content is no pages", () => {
    expect(paginate([], 0, 1000)).toEqual([]);
  });

  test("the pages tile the content exactly", () => {
    // The invariant that matters. Any off-by-one here either drops a
    // strip of the dashboard or prints one twice, and neither is
    // visible until someone opens the PDF.
    const breaks = [220, 640, 980, 1310, 1755, 2400, 3050];
    const pages = paginate(breaks, 3050, 700);

    expect(pages[0][0]).toBe(0);
    expect(pages[pages.length - 1][1]).toBe(3050);
    pages.forEach(([start, end], i) => {
      expect(end).toBeGreaterThan(start);
      if (i > 0) {
        expect(start).toBe(pages[i - 1][1]);
      }
    });
  });

  test("a non-positive page height is refused rather than looped on", () => {
    // `pageHeight` is derived from the captured element's width, and a
    // hidden or unlaid-out element measures zero. Without the guard the
    // walk cannot advance and the browser tab freezes; throwing turns it
    // into the viewer's "couldn't export" message instead.
    expect(() => paginate([300], 1000, 0)).toThrow(/positive/);
    expect(() => paginate([300], 1000, -50)).toThrow(/positive/);
    expect(() => paginate([300], 1000, NaN)).toThrow(/positive/);
  });
});

describe("freezeAnimations", () => {
  // The defect this guards against shipped once and was invisible to
  // every code review: widget cards carry `animation: dashFadeUp ...
  // both` whose first keyframe is `opacity: 0`, html2canvas restarts
  // animations in the clone it rasterizes, and the cards came out faded
  // or absent while the unanimated title and filter bar rendered fine.
  test("neutralises animation and transition in the cloned document", () => {
    const clone = document.implementation.createHTMLDocument("clone");

    freezeAnimations(clone);

    const injected = clone.head.querySelector("style");
    expect(injected).not.toBeNull();
    expect(injected.textContent).toContain("animation: none !important");
    expect(injected.textContent).toContain("transition: none !important");
  });

  test("the rule reaches pseudo-elements too", () => {
    // Card chrome is drawn with ::before/::after in places, and a rule
    // that only matched real elements would leave those mid-animation.
    const clone = document.implementation.createHTMLDocument("clone");

    freezeAnimations(clone);

    expect(clone.head.querySelector("style").textContent).toContain(
      "*::before"
    );
  });
});
