import React, { useMemo } from "react";
import PropTypes from "prop-types";
import useEChartsOption from "./useEChartsOption";
import { buildToolboxConfig } from "./toolboxHelper";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const VizScatter = ({ config, data }) => {
  const widgetConfig = useMemo(() => config?.config || {}, [config]);
  const colors = widgetConfig.chart_colors || DEFAULT_COLORS;
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);
  const xLabel = widgetConfig.x_axis_label || "Number of datapoints";
  const yLabel = widgetConfig.y_axis_label || "Number of datapoints";

  const option = useMemo(() => {
    if (chartData.length === 0) {
      return null;
    }
    const toolbox = buildToolboxConfig(widgetConfig, "scatter");
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
      ...(toolbox ? { toolbox } : {}),
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
  }, [chartData, colors, widgetConfig, xLabel, yLabel]);

  const { boxRef } = useEChartsOption(option);

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
