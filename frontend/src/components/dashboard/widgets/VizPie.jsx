import React, { useMemo } from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import useEmptyWidgetMessage from "./useEmptyWidgetMessage";
import { Pie, Doughnut } from "akvo-charts";
import { buildToolboxConfig } from "./toolboxHelper";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const VizPie = ({ config, data, filters }) => {
  const emptyMessage = useEmptyWidgetMessage(filters);
  const widgetConfig = config?.config || {};
  const isDoughnut = widgetConfig.variant === "doughnut";
  const Component = isDoughnut ? Doughnut : Pie;

  const colors = Array.isArray(config?.color)
    ? config.color
    : widgetConfig.chart_colors || DEFAULT_COLORS;

  const toolboxConfig = config?.toolbox || widgetConfig.toolbox || widgetConfig;
  const toolbox = buildToolboxConfig(toolboxConfig, "pie", config?.title);
  const { chartRef, boxRef } = useChartResize(toolbox);

  const chartConfig = {
    title: "",
    color: colors,
  };
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  const rawConfig = useMemo(
    () => ({
      color: colors,
      tooltip: {
        trigger: "item",
      },
      legend: {
        orient: "horizontal",
        bottom: 0,
      },
      toolbox: toolbox || { show: false, feature: {} },
      series: [
        {
          type: "pie",
          radius: isDoughnut ? ["40%", "70%"] : "70%",
          data: chartData.map((d) => ({
            name: d.name ?? d.label ?? "-",
            value: d.value ?? 0,
          })),
        },
      ],
    }),
    [colors, isDoughnut, toolbox, chartData]
  );

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
      <Component
        ref={chartRef}
        config={chartConfig}
        rawConfig={rawConfig}
        data={chartData}
      />
    </div>
  );
};

VizPie.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
  filters: PropTypes.object,
};

export default VizPie;
