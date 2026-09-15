import { useEffect, useRef } from "react";
import * as echarts from "echarts";

/**
 * Manages an ECharts instance: init, setOption, resize, dispose.
 *
 * @param {object|null} option  ECharts option object, or null to skip rendering.
 * @returns {{ boxRef: React.RefObject }}  Attach boxRef to the container div.
 */
const useEChartsOption = (option) => {
  const boxRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const box = boxRef.current;
    if (!box || !option) {
      return () => {};
    }

    try {
      if (!chartRef.current) {
        chartRef.current = echarts.init(box);
      }
      chartRef.current.setOption(option, true);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error("useEChartsOption error:", e);
    }

    let cleanup;
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => {
        if (chartRef.current) {
          chartRef.current.resize();
        }
      });
      observer.observe(box);
      cleanup = () => observer.disconnect();
    } else {
      const sync = () => {
        if (chartRef.current) {
          chartRef.current.resize();
        }
      };
      window.addEventListener("resize", sync);
      cleanup = () => window.removeEventListener("resize", sync);
    }

    return () => {
      cleanup();
      if (chartRef.current) {
        chartRef.current.dispose();
        chartRef.current = null;
      }
    };
  }, [option]);

  return { boxRef };
};

export default useEChartsOption;
