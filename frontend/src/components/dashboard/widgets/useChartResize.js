import { useEffect, useRef } from "react";

/**
 * Keep an akvo-charts chart the size of its container.
 *
 * akvo-charts measures the chart exactly once, inside `echarts.init()`, and
 * never again: the package registers no resize listener and never calls
 * `chart.resize()` (grep it — there are zero of both). Whatever height the
 * container happens to have at that first measurement is what the canvas
 * keeps for the life of the component.
 *
 * The legacy dashboard never noticed, because its cards are auto-height —
 * an oversized canvas just makes the card taller. The viewer's cards have
 * a fixed per-type height and `overflow: hidden` (the mockup's
 * `_bodyStyle`), so the same oversized canvas is silently cropped instead,
 * taking the x-axis labels and the bottom of the plot with it.
 *
 * Rather than try to guarantee the container has settled before the
 * library measures it — which is a race we do not control and cannot
 * assert in a test — this re-measures after mount and on every container
 * resize. It also fixes a pre-existing gap: charts in this app currently
 * do not reflow when the window resizes.
 *
 * @returns {{chartRef: object, boxRef: object}} `chartRef` goes on the
 *   akvo-charts component (it forwards the ECharts instance), `boxRef` on
 *   the wrapper whose size the chart should follow.
 */
export const useChartResize = () => {
  const chartRef = useRef(null);
  const boxRef = useRef(null);

  useEffect(() => {
    const box = boxRef.current;
    if (!box) {
      return () => {};
    }

    const sync = () => {
      const chart = chartRef.current;
      // Null while the chart is still initialising, and a plain object
      // under test where akvo-charts is mocked out.
      if (chart && typeof chart.resize === "function") {
        chart.resize();
      }
    };

    // Once immediately: if the library measured a stale size, this is the
    // correction. If it measured correctly, this is a no-op.
    sync();

    // jsdom has no ResizeObserver, and neither do older browsers; the
    // window listener covers the case that actually matters there.
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", sync);
      return () => window.removeEventListener("resize", sync);
    }

    const observer = new ResizeObserver(sync);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  return { chartRef, boxRef };
};

export default useChartResize;
