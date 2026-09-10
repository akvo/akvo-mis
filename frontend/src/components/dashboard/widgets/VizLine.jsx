import React, { useEffect, useMemo } from "react";
import PropTypes from "prop-types";
import useChartResize from "./useChartResize";
import useEChartsOption from "./useEChartsOption";
import { Line, StackLine } from "akvo-charts";
import { buildToolboxConfig } from "./toolboxHelper";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const CategoryLine = ({ config, data }) => {
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

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
    const toolbox = buildToolboxConfig(wc, "line");
    return {
      color: seriesColors,
      tooltip: {
        trigger: "axis",
        appendToBody: true,
      },
      legend: {
        data: labels,
        bottom: 0,
      },
      ...(toolbox ? { toolbox } : {}),
      grid: { top: 20, right: 20, bottom: 40, left: 40, containLabel: true },
      xAxis: {
        type: "category",
        data: chartData.map((d) => d.label),
      },
      yAxis: {
        type: "value",
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
        No data
      </div>
    );
  }

  return <div ref={boxRef} style={{ width: "100%", height: "100%" }} />;
};

const VizLine = ({ config, data }) => {
  const { chartRef, boxRef } = useChartResize();
  const widgetConfig = config?.config || {};
  const hasCategory = Boolean(widgetConfig.category_question_id);
  const hasStack = Boolean(widgetConfig.stack_by);

  const colors = Array.isArray(config?.color)
    ? config.color
    : widgetConfig.chart_colors || DEFAULT_COLORS;

  const toolbox = buildToolboxConfig(widgetConfig, "line");
  const chartConfig = {
    title: "",
    color: colors,
  };
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  useEffect(() => {
    if (
      !hasCategory &&
      chartRef.current &&
      typeof chartRef.current.setOption === "function"
    ) {
      chartRef.current.setOption({
        toolbox: toolbox || { show: false },
      });
    }
  }, [hasCategory, toolbox, chartData, config, chartRef]);

  if (hasCategory) {
    return <CategoryLine config={config} data={data} />;
  }

  const Component = hasStack ? StackLine : Line;

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

CategoryLine.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizLine;
