import React, { useMemo } from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import useEmptyWidgetMessage from "./useEmptyWidgetMessage";
import { Bar, StackBar } from "akvo-charts";
import { buildToolboxConfig } from "./toolboxHelper";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const VizBar = ({ config, data, filters }) => {
  const emptyMessage = useEmptyWidgetMessage(filters);
  const widgetConfig = config?.config || {};
  const hasStack = Boolean(widgetConfig.stack_by);
  const Component = hasStack ? StackBar : Bar;

  const colors = Array.isArray(config?.color)
    ? config.color
    : widgetConfig.chart_colors || DEFAULT_COLORS;

  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  const horizontal = widgetConfig.orientation === "horizontal";
  const toolbox = buildToolboxConfig(widgetConfig, "bar");
  const { chartRef, boxRef } = useChartResize(toolbox);

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        {emptyMessage}
      </div>
    );
  }

  if (hasStack) {
    const chartConfig = {
      title: "",
      color: colors,
      horizontal,
    };
    const props = { config: chartConfig, data: chartData };
    if (widgetConfig.stackMapping) {
      props.stackMapping = widgetConfig.stackMapping;
    }

    return (
      <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
        <Component ref={chartRef} {...props} />
      </div>
    );
  }

  const firstItem = chartData[0] || {};
  const categoryKey =
    Object.keys(firstItem).find((k) => k !== "value") || "label";
  const rawConfig = {
    color: colors,
    tooltip: { trigger: "axis" },
    legend: { show: false },
    toolbox: toolbox || { show: false },
    grid: { top: 40, right: 20, bottom: 40, left: 50, containLabel: true },
    xAxis: {
      type: horizontal ? "value" : "category",
      data: horizontal ? null : chartData.map((d) => d[categoryKey]),
    },
    yAxis: {
      type: horizontal ? "category" : "value",
      data: horizontal ? chartData.map((d) => d[categoryKey]) : null,
    },
    series: [
      {
        type: "bar",
        colorBy: "data",
        data: chartData.map((d) => d.value),
      },
    ],
  };

  return (
    <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
      <Bar ref={chartRef} rawConfig={rawConfig} />
    </div>
  );
};

VizBar.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
  filters: PropTypes.object,
};

export default VizBar;
