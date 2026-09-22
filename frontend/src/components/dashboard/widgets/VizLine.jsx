import React, { useMemo } from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import useEChartsOption from "./useEChartsOption";
import useEmptyWidgetMessage from "./useEmptyWidgetMessage";
import { Line, StackLine } from "akvo-charts";
import { buildToolboxConfig } from "./toolboxHelper";
import { valueAxisLabel } from "./axisHelper";
import AxisLabelWrap from "./AxisLabelWrap";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];
const MAX_LEGEND_LEN = 15;
const truncate = (s) =>
  s && s.length > MAX_LEGEND_LEN ? `${s.slice(0, MAX_LEGEND_LEN)}…` : s;

const CategoryLine = ({ config, data, filters }) => {
  const emptyMessage = useEmptyWidgetMessage(filters);
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);
  const widgetConfig = config?.config || {};
  const xLabel = widgetConfig.x_axis_label || null;
  const yLabel = widgetConfig.y_axis_label || null;

  const option = useMemo(() => {
    const wc = config?.config || {};
    const colors = wc.chart_colors || DEFAULT_COLORS;
    const catColors = wc.category_colors || {};
    const labels = wc.stackMapping?.stack || [];
    if (chartData.length === 0 || labels.length === 0) {
      return null;
    }
    const seriesColors = labels.map(
      (name, idx) => catColors[name] || colors[idx % colors.length]
    );
    const toolboxConfig = config?.toolbox || wc.toolbox || wc;
    const toolbox = buildToolboxConfig(toolboxConfig, "line", config?.title);
    const isTopToolbox = Boolean(
      toolbox?.show && typeof toolbox?.top !== "undefined"
    );
    const isBottomToolbox = Boolean(
      toolbox?.show && typeof toolbox?.bottom !== "undefined"
    );
    return {
      color: seriesColors,
      tooltip: {
        trigger: "axis",
        appendToBody: true,
      },
      legend: {
        type: "scroll",
        data: labels,
        bottom: 0,
        formatter: truncate,
      },
      toolbox: toolbox || { show: false, feature: {} },
      grid: {
        top: isTopToolbox ? 55 : 30,
        right: 20,
        bottom: isBottomToolbox ? 65 : 40,
        left: 20,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: chartData.map((d) => d.label),
      },
      yAxis: {
        type: "value",
        axisLabel: valueAxisLabel(),
      },
      series: labels.map((name, idx) => ({
        name,
        type: "line",
        data: chartData.map((d) => d[name] ?? 0),
        itemStyle: { color: seriesColors[idx] },
      })),
    };
  }, [chartData, config]);

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

CategoryLine.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
  filters: PropTypes.object,
};

const VizLine = ({ config, data, filters }) => {
  const emptyMessage = useEmptyWidgetMessage(filters);
  const widgetConfig = config?.config || {};
  const hasCategory = Boolean(widgetConfig.category_question_id);
  const isAdminGrouped = widgetConfig.stack_by === "administration";
  const hasStack = Boolean(widgetConfig.stack_by || widgetConfig.stackMapping);
  const xAxisLabel = widgetConfig.x_axis_label || null;
  const yAxisLabel = widgetConfig.y_axis_label || null;

  const colors = Array.isArray(config?.color)
    ? config.color
    : widgetConfig.chart_colors || DEFAULT_COLORS;

  const toolboxConfig = config?.toolbox || widgetConfig.toolbox || widgetConfig;
  const toolbox = buildToolboxConfig(toolboxConfig, "line", config?.title);
  const { chartRef, boxRef } = useChartResize(toolbox);

  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  if (hasCategory || isAdminGrouped) {
    return <CategoryLine config={config} data={data} filters={filters} />;
  }

  const Component = hasStack ? StackLine : Line;
  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        {emptyMessage}
      </div>
    );
  }

  const isTopToolbox = Boolean(
    toolbox?.show && typeof toolbox?.top !== "undefined"
  );
  const isBottomToolbox = Boolean(
    toolbox?.show && typeof toolbox?.bottom !== "undefined"
  );

  if (hasStack) {
    const firstItem = chartData[0] || {};
    const stackLabels =
      widgetConfig.stackMapping?.stack ||
      Object.keys(firstItem).filter((k) => {
        return k !== "label" && k !== "value";
      });

    const rawConfig = {
      color: colors,
      tooltip: { trigger: "axis" },
      legend: {
        show: true,
        type: "scroll",
        data: stackLabels,
        bottom: 0,
        formatter: truncate,
      },
      toolbox: toolbox || { show: false, feature: {} },
      grid: {
        top: isTopToolbox ? 55 : 35,
        right: 20,
        bottom: isBottomToolbox ? 65 : 40,
        left: 20,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: chartData.map((d) => d.label),
      },
      yAxis: {
        type: "value",
        axisLabel: valueAxisLabel(),
      },
      series: stackLabels.map((name, idx) => ({
        name,
        type: "line",
        stack: "defaultStack",
        data: chartData.map((d) => {
          return d[name] ?? 0;
        }),
        itemStyle: { color: colors[idx % colors.length] },
      })),
    };

    return (
      <AxisLabelWrap xLabel={xAxisLabel} yLabel={yAxisLabel}>
        <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
          <Component ref={chartRef} rawConfig={rawConfig} />
        </div>
      </AxisLabelWrap>
    );
  }

  const firstItem = chartData[0] || {};
  const categoryKey =
    Object.keys(firstItem).find((k) => {
      return k !== "value";
    }) || "label";

  const rawConfig = {
    color: colors,
    tooltip: { trigger: "axis" },
    legend: { show: false },
    toolbox: toolbox || { show: false, feature: {} },
    grid: {
      top: isTopToolbox ? 55 : 35,
      right: 20,
      bottom: isBottomToolbox ? 55 : 40,
      left: 20,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: chartData.map((d) => d[categoryKey]),
    },
    yAxis: {
      type: "value",
      axisLabel: valueAxisLabel(),
    },
    series: [
      {
        name: config?.title || "Value",
        type: "line",
        data: chartData.map((d) => d.value),
        itemStyle: { color: colors[0] },
      },
    ],
  };

  return (
    <AxisLabelWrap xLabel={xAxisLabel} yLabel={yAxisLabel}>
      <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
        <Component ref={chartRef} rawConfig={rawConfig} />
      </div>
    </AxisLabelWrap>
  );
};

VizLine.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
  filters: PropTypes.object,
};

export default VizLine;
