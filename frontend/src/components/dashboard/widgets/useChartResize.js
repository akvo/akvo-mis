import { useCallback, useEffect, useRef } from "react";

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
 * In addition, when `toolbox` is provided, this hook wraps `chartInstance.setOption`
 * so that when `akvo-charts` initialises and sets chart options on initial mount or
 * data update, the `toolbox` configuration is automatically merged in.
 *
 * @param {object|null} [toolbox] ECharts toolbox configuration object or null.
 * @returns {{chartRef: function|object, boxRef: object}} `chartRef` goes on the
 *   akvo-charts component (it forwards the ECharts instance), `boxRef` on
 *   the wrapper whose size the chart should follow.
 */
export const useChartResize = (toolbox) => {
  const chartRef = useRef(null);
  const boxRef = useRef(null);
  const toolboxRef = useRef(toolbox);
  toolboxRef.current = toolbox;

  const setChartRef = useCallback((chart) => {
    chartRef.current = chart;
    setChartRef.current = chart;
    if (
      chart &&
      !chart.__mis_toolbox_patched &&
      typeof chart.setOption === "function"
    ) {
      chart.__mis_toolbox_patched = true;
      const originalSetOption = chart.setOption.bind(chart);
      chart.setOption = (opts, ...args) => {
        const tb = toolboxRef.current;
        const finalOpts =
          opts && typeof opts === "object"
            ? {
                ...opts,
                toolbox: tb || { show: false },
              }
            : opts;
        return originalSetOption(finalOpts, ...args);
      };
      if (toolboxRef.current) {
        chart.setOption({ toolbox: toolboxRef.current });
      }
    }
  }, []);

  setChartRef.current = chartRef.current;

  useEffect(() => {
    const chart = chartRef.current;
    if (chart && typeof chart.setOption === "function") {
      chart.setOption({
        toolbox: toolbox || { show: false },
      });
    }
  }, [toolbox]);

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

  return { chartRef: setChartRef, boxRef };
};

export default useChartResize;
