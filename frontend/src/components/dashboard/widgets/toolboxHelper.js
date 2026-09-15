import { Excel } from "antd-table-saveas-excel";

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
 * Extracts clean tabular columns and rows from ECharts option object.
 *
 * @param {Object} opt - ECharts option object passed to dataView.optionToContent
 * @param {string} [widgetTitle] - Fallback title for value columns
 * @returns {{ columns: Array<{title: string, key: string}>, rows: Array<Object> }}
 */
export const parseChartDataForView = (opt, widgetTitle = "Value") => {
  if (!opt) {
    return { columns: [], rows: [] };
  }

  // 1. Dataset source format (if akvo-charts uses dataset)
  const dataset = Array.isArray(opt.dataset) ? opt.dataset[0] : opt.dataset;
  if (dataset && Array.isArray(dataset.source) && dataset.source.length > 0) {
    const source = dataset.source;
    if (Array.isArray(source[0])) {
      const headers = source[0].map((h, i) => ({
        title: String(h || `Column ${i + 1}`),
        key: `col_${i}`,
      }));
      const rows = source.slice(1).map((row) =>
        headers.reduce((acc, h, i) => {
          acc[h.key] =
            row[i] !== null && typeof row[i] !== "undefined" ? row[i] : "";
          return acc;
        }, {})
      );
      return { columns: headers, rows };
    }
    if (typeof source[0] === "object" && source[0] !== null) {
      const keys = Object.keys(source[0]);
      const columns = keys.map((k) => ({
        title: k === "label" ? "Category" : k,
        key: k,
      }));
      return { columns, rows: source };
    }
  }

  // 2. Series data format
  const seriesList = Array.isArray(opt.series) ? opt.series : [];
  if (seriesList.length === 0) {
    return { columns: [], rows: [] };
  }

  // 2A. Pie / Doughnut series
  const firstSeries = seriesList[0] || {};
  if (firstSeries.type === "pie" && Array.isArray(firstSeries.data)) {
    const columns = [
      { title: "Category", key: "category" },
      { title: widgetTitle || "Value", key: "value" },
    ];
    const rows = firstSeries.data.map((item) => ({
      category: item.name || "-",
      value:
        item.value !== null && typeof item.value !== "undefined"
          ? item.value
          : 0,
    }));
    return { columns, rows };
  }

  // 2B. Scatter series
  if (firstSeries.type === "scatter" && Array.isArray(firstSeries.data)) {
    const xName = opt.xAxis?.[0]?.name || opt.xAxis?.name || "X Value";
    const yName = opt.yAxis?.[0]?.name || opt.yAxis?.name || "Y Value";
    const columns = [
      { title: "Name", key: "name" },
      { title: xName, key: "x" },
      { title: yName, key: "y" },
    ];
    const rows = firstSeries.data.map((item) => {
      const point = Array.isArray(item) ? item : item.value || [];
      const xVal =
        point[0] !== null && typeof point[0] !== "undefined" ? point[0] : 0;
      const yVal =
        point[1] !== null && typeof point[1] !== "undefined" ? point[1] : 0;
      return {
        name: point[2] || "-",
        x: xVal,
        y: yVal,
      };
    });
    return { columns, rows };
  }

  // 2C. Bar / Line (single or multi-series / stacked)
  const xAxis = Array.isArray(opt.xAxis) ? opt.xAxis[0] : opt.xAxis;
  const yAxis = Array.isArray(opt.yAxis) ? opt.yAxis[0] : opt.yAxis;
  const categories =
    (xAxis && Array.isArray(xAxis.data) && xAxis.data) ||
    (yAxis && Array.isArray(yAxis.data) && yAxis.data) ||
    [];

  const columns = [
    { title: "Category", key: "category" },
    ...seriesList.map((s, idx) => {
      const isGeneric = !s.name || /^series[_\s\d]*$/i.test(s.name);
      let seriesTitle = s.name;
      if (isGeneric) {
        seriesTitle =
          seriesList.length === 1
            ? widgetTitle || "Value"
            : `Series ${idx + 1}`;
      }
      return {
        title: seriesTitle,
        key: `series_${idx}`,
      };
    }),
  ];

  const rows = categories.map((cat, rowIdx) => {
    const row = { category: cat };
    seriesList.forEach((s, sIdx) => {
      const val = Array.isArray(s.data) ? s.data[rowIdx] : null;
      let cellValue = 0;
      if (typeof val === "object" && val !== null) {
        cellValue = val.value;
      } else if (val !== null && typeof val !== "undefined") {
        cellValue = val;
      }
      row[`series_${sIdx}`] = cellValue;
    });
    return row;
  });

  return { columns, rows };
};

/**
 * Exports data to an Excel (.xlsx) spreadsheet using antd-table-saveas-excel.
 */
export const exportDataViewToExcel = (columns, rows, title = "chart_data") => {
  if (!columns || columns.length === 0) {
    return;
  }
  const tableColumns = columns.map((col) => ({
    title: col.title,
    key: col.key,
    dataIndex: col.key,
  }));
  const dataSource = rows.map((r) =>
    columns.reduce(
      (acc, col) => ({
        ...acc,
        [col.key]:
          r[col.key] !== null && typeof r[col.key] !== "undefined"
            ? r[col.key]
            : "",
      }),
      {}
    )
  );

  const cleanTitle =
    (title || "chart_data").replace(/[^a-zA-Z0-9_\-\s]/g, "").trim() ||
    "chart_data";
  const excel = new Excel();
  excel
    .addSheet("Data")
    .addColumns(tableColumns)
    .addDataSource(dataSource)
    .saveAs(`${cleanTitle}.xlsx`);
};

/**
 * Builds custom DataView DOM element with clean table and XLSX export button.
 */
export const renderDataViewTable = (opt, widgetTitle) => {
  const { columns, rows } = parseChartDataForView(opt, widgetTitle);

  const container = document.createElement("div");
  container.style.cssText =
    "height: 100%; display: flex; flex-direction: column; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; box-sizing: border-box;";

  // Toolbar
  const toolbar = document.createElement("div");
  toolbar.style.cssText =
    "margin-bottom: 12px; display: flex; justify-content: flex-end;";

  const btn = document.createElement("button");
  btn.innerText = "Download Excel (.xlsx)";
  btn.style.cssText =
    "background: #1890ff; color: #fff; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: background 0.2s ease;";
  btn.onmouseover = () => {
    btn.style.background = "#40a9ff";
  };
  btn.onmouseout = () => {
    btn.style.background = "#1890ff";
  };
  btn.onclick = () => {
    exportDataViewToExcel(columns, rows, widgetTitle);
  };
  toolbar.appendChild(btn);
  container.appendChild(toolbar);

  // Table wrapper
  const tableWrap = document.createElement("div");
  tableWrap.style.cssText =
    "flex: 1; overflow: auto; border: 1px solid #f0f0f0; border-radius: 4px; background: #fff;";

  const table = document.createElement("table");
  table.style.cssText =
    "width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;";

  const thead = document.createElement("thead");
  thead.style.cssText = "background: #fafafa; position: sticky; top: 0;";
  const trHead = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.innerText = col.title;
    th.style.cssText =
      "padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-weight: 600; color: #262626;";
    trHead.appendChild(th);
  });
  thead.appendChild(trHead);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    tr.style.background = idx % 2 === 0 ? "#ffffff" : "#fafafa";
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.innerText =
        row[col.key] !== null && typeof row[col.key] !== "undefined"
          ? String(row[col.key])
          : "-";
      td.style.cssText =
        "padding: 8px 12px; border-bottom: 1px solid #f0f0f0; color: #595959;";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  container.appendChild(tableWrap);

  return container;
};

/**
 * Builds an ECharts toolbox configuration object based on dashboard/widget settings.
 *
 * @param {Object} toolboxConfig - Toolbox settings object (e.g. dashboard.default_filters.toolbox or widget.config).
 * @param {string} widgetType - Type of the widget ('bar', 'line', 'pie', 'scatter').
 * @param {string} [widgetTitle] - Title of the widget.
 * @returns {Object|null} ECharts toolbox option or null if disabled.
 */
export const buildToolboxConfig = (
  toolboxConfig,
  widgetType,
  widgetTitle = ""
) => {
  if (!toolboxConfig) {
    return null;
  }

  // Handle { show: true }, { enabled: true }, and { show_toolbox: true }
  const isEnabled = Boolean(
    toolboxConfig.show ?? toolboxConfig.enabled ?? toolboxConfig.show_toolbox
  );
  if (!isEnabled) {
    return null;
  }

  const features =
    toolboxConfig.features ||
    toolboxConfig.toolbox_features ||
    DEFAULT_TOOLBOX_FEATURES;
  const positionKey =
    toolboxConfig.position || toolboxConfig.toolbox_position || "top-right";
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

  const feature = {};

  if (features.saveAsImage !== false) {
    feature.saveAsImage = { show: true, title: "Save as image" };
  }

  if (features.dataView !== false) {
    feature.dataView = {
      show: true,
      readOnly: true,
      title: "Data view",
      optionToContent: (opt) => renderDataViewTable(opt, widgetTitle),
    };
  }

  if (features.restore !== false) {
    feature.restore = { show: true, title: "Restore" };
  }

  if (widgetType !== "pie" && features.dataZoom !== false) {
    feature.dataZoom = {
      show: true,
      yAxisIndex: "none",
      title: {
        zoom: "Zoom",
        back: "Reset zoom",
      },
    };
  }

  if (Object.keys(feature).length === 0) {
    return null;
  }

  return {
    show: true,
    ...positionCoords,
    orient:
      toolboxConfig.orient || toolboxConfig.toolbox_orient || "horizontal",
    feature,
  };
};
