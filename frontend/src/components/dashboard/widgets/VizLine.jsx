import React from "react";
import PropTypes from "prop-types";
import { Line, StackLine } from "akvo-charts";

const VizLine = ({ config, data }) => {
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
    <div style={{ width: "100%", height: "100%" }}>
      <Component {...props} />
    </div>
  );
};

VizLine.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizLine;
