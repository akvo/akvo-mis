export const TOOLBOX_POSITIONS = {
  "top-right": { top: 0, right: 10 },
  "top-left": { top: 0, left: 10 },
  "bottom-right": { bottom: 0, right: 10 },
  "bottom-left": { bottom: 0, left: 10 },
};

export const DEFAULT_TOOLBOX_FEATURES = {
  saveAsImage: true,
  dataView: true,
  restore: true,
  dataZoom: true,
};

/**
 * Builds an ECharts toolbox configuration object based on widget settings.
 *
 * @param {Object} widgetConfig - The widget's config object (e.g. widget.config).
 * @param {string} widgetType - Type of the widget ('bar', 'line', 'pie', 'scatter').
 * @returns {Object|null} ECharts toolbox option or null if disabled.
 */
export const buildToolboxConfig = (widgetConfig, widgetType) => {
  if (!widgetConfig || !widgetConfig.show_toolbox) {
    return null;
  }

  const features = widgetConfig.toolbox_features || DEFAULT_TOOLBOX_FEATURES;
  const positionKey = widgetConfig.toolbox_position || "top-right";
  const positionCoords =
    TOOLBOX_POSITIONS[positionKey] || TOOLBOX_POSITIONS["top-right"];

  const feature = {};

  if (features.saveAsImage !== false) {
    feature.saveAsImage = {};
  }
  if (features.dataView !== false) {
    feature.dataView = { readOnly: false };
  }
  if (features.restore !== false) {
    feature.restore = {};
  }
  if (features.dataZoom !== false && widgetType !== "pie") {
    feature.dataZoom = {};
  }

  if (Object.keys(feature).length === 0) {
    return null;
  }

  return {
    show: true,
    ...positionCoords,
    orient: widgetConfig.toolbox_orient || "horizontal",
    feature,
  };
};
