import React from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import { Line, StackLine } from "akvo-charts";

const VizLine = ({ config, data }) => {
  const { chartRef, boxRef } = useChartResize();
  const widgetConfig = config?.config || {};
  const hasStack = Boolean(widgetConfig.stack_by);
  const Component = hasStack ? StackLine : Line;

  const chartConfig = {
    title: "",
    color: config?.color ? [config.color] : ["#1651b6"],
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

VizLine.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizLine;
