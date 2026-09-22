import React, { useMemo } from "react";
import PropTypes from "prop-types";
import useEChartsOption from "./useEChartsOption";
import { buildToolboxConfig } from "./toolboxHelper";
import { valueAxisLabel } from "./axisHelper";
import useEmptyWidgetMessage from "./useEmptyWidgetMessage";
import AxisLabelWrap from "./AxisLabelWrap";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const VizScatter = ({ config, data, filters }) => {
  const emptyMessage = useEmptyWidgetMessage(filters);
  const widgetConfig = useMemo(() => config?.config || {}, [config?.config]);
  const colors = widgetConfig.chart_colors || DEFAULT_COLORS;
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);
  const xLabel = widgetConfig.x_axis_label || "Number of datapoints";
  const yLabel = widgetConfig.y_axis_label || "Number of datapoints";

  const option = useMemo(() => {
    if (chartData.length === 0) {
      return null;
    }
    const toolboxConfig =
      config?.toolbox || widgetConfig.toolbox || widgetConfig;
    const toolbox = buildToolboxConfig(toolboxConfig, "scatter", config?.title);
    const isTopToolbox = Boolean(
      toolbox?.show && typeof toolbox?.top !== "undefined"
    );
    const isBottomToolbox = Boolean(
      toolbox?.show && typeof toolbox?.bottom !== "undefined"
    );
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
      toolbox: toolbox || { show: false, feature: {} },
      grid: {
        top: isTopToolbox ? 55 : 35,
        right: 20,
        bottom: isBottomToolbox ? 75 : 30,
        left: 20,
        containLabel: true,
      },
      xAxis: {
        type: "value",
        axisLabel: valueAxisLabel(),
      },
      yAxis: {
        type: "value",
        axisLabel: valueAxisLabel(),
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
  }, [chartData, colors, config, widgetConfig, xLabel, yLabel]);

  const { boxRef } = useEChartsOption(option);

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <AxisLabelWrap xLabel={xLabel} yLabel={yLabel}>
      <div ref={boxRef} style={{ width: "100%", height: "100%" }} />
    </AxisLabelWrap>
  );
};

VizScatter.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
  filters: PropTypes.object,
};

export default VizScatter;
