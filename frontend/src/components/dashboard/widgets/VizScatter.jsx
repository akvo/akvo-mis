import React, { useEffect, useRef, useMemo } from "react";
import PropTypes from "prop-types";
import * as echarts from "echarts";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const VizScatter = ({ config, data }) => {
  const boxRef = useRef(null);
  const chartRef = useRef(null);
  const widgetConfig = config?.config || {};
  const colors = widgetConfig.chart_colors || DEFAULT_COLORS;
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);
  const xLabel = widgetConfig.x_axis_label || "Number of datapoints";
  const yLabel = widgetConfig.y_axis_label || "Number of datapoints";

  const option = useMemo(() => {
    if (chartData.length === 0) {
      return null;
    }
    return {
      color: colors,
      tooltip: {
        trigger: "item",
        appendToBody: true,
        formatter: (params) => {
          const d = params.data;
          return [
            `<strong>${d[2] || ""}</strong>`,
            `${xLabel}: ${d[0]}`,
            `${yLabel}: ${d[1]}`,
          ].join("<br/>");
        },
      },
      legend: { show: false },
      grid: { top: 40, right: 20, bottom: 50, left: 60, containLabel: true },
      xAxis: {
        type: "value",
        name: xLabel,
        nameLocation: "center",
        nameGap: 30,
      },
      yAxis: {
        type: "value",
        name: yLabel,
        nameLocation: "center",
        nameGap: 40,
      },
      series: [
        {
          type: "scatter",
          data: chartData.map((d) => [d.x, d.y, d.name]),
          symbolSize: 10,
          itemStyle: { color: colors[0] },
        },
      ],
    };
  }, [chartData, colors, xLabel, yLabel]);

  useEffect(() => {
    const box = boxRef.current;
    if (!box || !option) {
      return () => {};
    }

    if (!chartRef.current) {
      chartRef.current = echarts.init(box);
    }
    chartRef.current.setOption(option, true);

    const sync = () => {
      if (chartRef.current) {
        chartRef.current.resize();
      }
    };

    let cleanup;
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(sync);
      observer.observe(box);
      cleanup = () => observer.disconnect();
    } else {
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

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        No data
      </div>
    );
  }

  return <div ref={boxRef} style={{ width: "100%", height: "100%" }} />;
};

VizScatter.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizScatter;
