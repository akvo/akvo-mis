import fs from "fs";
import path from "path";

// =========================================================
// D-10: charts come from akvo-charts, and only from akvo-charts
// =========================================================
//
// A ratchet rather than a bug hunt — it passes the day it is written. It
// exists because the legacy dashboard drifted the other way one component
// at a time: `DotStripChart` and `DotsChart` are bespoke ECharts widgets
// that grew inside `components/dashboard/` because nothing stopped them.
// akvo-charts is Akvo's own ECharts wrapper, maintained alongside the
// platform, and it already covers every chart type the widget schema has.
//
// The walk follows relative imports only. `akvo-charts` itself depends on
// echarts, which is the entire point of using it.

const SRC = path.join(__dirname, "..", "..", "..");
const ENTRY = path.join(SRC, "pages", "dashboards", "DashboardViewer.jsx");

const BANNED = /from\s+["'](echarts|echarts-for-react)(\/[^"']*)?["']/;
const IMPORTS = /from\s+["'](\.[^"']*)["']/g;

// The one file that breaks the ratchet, listed rather than ignored.
//
// It was VizScatter (#364), which drove ECharts inline. VIZ-013 extracted
// that into `useEChartsOption` and put CategoryLine on it too, so the
// direct import now sits in one shared hook instead of once per widget —
// the debt moved and shrank rather than being paid off. akvo-charts still
// exports a `ScatterPlot` and a `Line`, so the premise holds; what stops
// the port is that akvo-charts derives `xAxis.type` from its `horizontal`
// flag ('category' when false), so a numeric X axis needs `rawConfig`
// overrides, and it has no tooltip formatter to match. That is a rewrite
// of shipped widgets with a visible failure mode, so it wants its own
// ticket.
//
// Naming the file keeps the guard live for every other component: a
// second offender fails this test, and deleting the entry is how the
// debt gets closed.
const KNOWN_OFFENDERS = ["components/dashboard/widgets/useEChartsOption.js"];

const resolve = (fromFile, spec) => {
  const base = path.resolve(path.dirname(fromFile), spec);
  const candidates = [
    base,
    `${base}.js`,
    `${base}.jsx`,
    path.join(base, "index.js"),
    path.join(base, "index.jsx"),
  ];
  return candidates.find(
    (candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile()
  );
};

const reachableFrom = (entry) => {
  const seen = new Set();
  const queue = [entry];
  while (queue.length) {
    const file = queue.shift();
    if (seen.has(file)) {
      continue;
    }
    seen.add(file);
    const source = fs.readFileSync(file, "utf8");
    let match = IMPORTS.exec(source);
    while (match) {
      const next = resolve(file, match[1]);
      if (next && !seen.has(next)) {
        queue.push(next);
      }
      match = IMPORTS.exec(source);
    }
  }
  return seen;
};

describe("the viewer path imports no charting library directly", () => {
  test("nothing reachable from DashboardViewer imports echarts", () => {
    const offenders = [...reachableFrom(ENTRY)]
      .filter((file) => BANNED.test(fs.readFileSync(file, "utf8")))
      .map((file) => path.relative(SRC, file));
    expect(offenders).toEqual(KNOWN_OFFENDERS);
  });

  test("the known offender is still there to be fixed", () => {
    // toEqual above is exact both ways, so this only states the intent
    // out loud: the entry is a debt to remove, and once its callers move
    // to akvo-charts this test is what tells you to delete it, rather
    // than leaving a list that quietly means nothing.
    KNOWN_OFFENDERS.forEach((offender) => {
      expect(fs.existsSync(path.join(SRC, offender))).toBe(true);
    });
  });

  test("the walk actually reaches the widget renderers", () => {
    // Without this, a resolver bug that returned an empty set would make
    // the assertion above pass forever while checking nothing.
    const reached = [...reachableFrom(ENTRY)].map((f) => path.relative(SRC, f));
    expect(reached).toContain("components/dashboard/DashboardGrid.jsx");
    expect(reached).toContain(
      "components/dashboard/widgets/WidgetRenderer.jsx"
    );
    expect(reached).toContain("components/dashboard/widgets/VizPie.jsx");
    expect(reached).toContain("util/hooks/useWidgetData.js");
  });
});
