import React from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import { Pie, Doughnut } from "akvo-charts";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const VizPie = ({ config, data }) => {
  const { chartRef, boxRef } = useChartResize();
  const widgetConfig = config?.config || {};
  const isDoughnut = widgetConfig.variant === "doughnut";
  const Component = isDoughnut ? Doughnut : Pie;

  const colors = Array.isArray(config?.color)
    ? config.color
    : widgetConfig.chart_colors || DEFAULT_COLORS;

  const chartConfig = { title: "", color: colors };
  const chartData = Array.isArray(data) ? data : [];

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        No data
      </div>
    );
  }

  return (
    <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
      <Component ref={chartRef} config={chartConfig} data={chartData} />
    </div>
  );
};

VizPie.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizPie;
