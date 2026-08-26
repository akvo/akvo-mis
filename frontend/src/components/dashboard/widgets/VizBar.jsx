import React from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import { Bar, StackBar } from "akvo-charts";

const VizBar = ({ config, data }) => {
  const { chartRef, boxRef } = useChartResize();
  const widgetConfig = config?.config || {};
  const hasStack = Boolean(widgetConfig.stack_by);
  const Component = hasStack ? StackBar : Bar;

  const chartConfig = {
    title: "",
    // An array arrives when the hook lifted per-option colours off a
    // group_by=option response; a string is the widget's own accent.
    // Wrapping an array would hand ECharts [[...]], and ECharts cycles a
    // one-colour palette — so without this every slice of a pie grouped
    // by option comes out the same blue.
    color: Array.isArray(config?.color)
      ? config.color
      : [config?.color || "#1890ff"],
    horizontal: widgetConfig.orientation === "horizontal",
  };

  const chartData = Array.isArray(data) ? data : [];

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        No data
      </div>
    );
  }

  const props = { config: chartConfig, data: chartData };
  if (hasStack && widgetConfig.stackMapping) {
    props.stackMapping = widgetConfig.stackMapping;
  }

  return (
    <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
      <Component ref={chartRef} {...props} />
    </div>
  );
};

VizBar.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizBar;
