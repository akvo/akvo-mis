import React from "react";
import PropTypes from "prop-types";
import { Bar, StackBar } from "akvo-charts";

const VizBar = ({ config, data }) => {
  const widgetConfig = config?.config || {};
  const hasStack = Boolean(widgetConfig.stack_by);
  const Component = hasStack ? StackBar : Bar;

  const chartConfig = {
    title: "",
    color: config?.color ? [config.color] : ["#1890ff"],
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
    <div style={{ width: "100%", height: "100%" }}>
      <Component {...props} />
    </div>
  );
};

VizBar.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizBar;
