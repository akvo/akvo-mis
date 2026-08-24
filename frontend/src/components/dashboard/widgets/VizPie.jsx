import React from "react";
import PropTypes from "prop-types";
import { Pie, Doughnut } from "akvo-charts";

const VizPie = ({ config, data }) => {
  const widgetConfig = config?.config || {};
  const isDoughnut = widgetConfig.variant === "doughnut";
  const Component = isDoughnut ? Doughnut : Pie;

  const chartConfig = {
    title: "",
    color: config?.color ? [config.color] : ["#1890ff"],
  };

  const chartData = Array.isArray(data) ? data : [];

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        No data
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <Component config={chartConfig} data={chartData} />
    </div>
  );
};

VizPie.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizPie;
