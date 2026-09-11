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

  const hasAnyFeature =
    features.saveAsImage !== false ||
    features.dataView !== false ||
    features.restore !== false ||
    (features.dataZoom !== false && widgetType !== "pie");

  if (!hasAnyFeature) {
    return null;
  }

  const feature = {
    saveAsImage: { show: features.saveAsImage !== false },
    dataView: { show: features.dataView !== false, readOnly: false },
    restore: { show: features.restore !== false },
  };

  if (widgetType !== "pie") {
    feature.dataZoom = { show: features.dataZoom !== false };
  }

  return {
    show: true,
    ...positionCoords,
    orient: widgetConfig.toolbox_orient || "horizontal",
    feature,
  };
};
