import {
  buildToolboxConfig,
  parseChartDataForView,
  renderDataViewTable,
  exportDataViewToExcel,
} from "../widgets/toolboxHelper";
import { Excel } from "antd-table-saveas-excel";

jest.mock("antd-table-saveas-excel", () => ({
  Excel: class MockExcel {
    addSheet() {
      return this;
    }
    addColumns() {
      return this;
    }
    addDataSource() {
      return this;
    }
    saveAs() {
      return this;
    }
  },
}));

describe("toolboxHelper - buildToolboxConfig", () => {
  test("returns null if toolboxConfig is missing or disabled", () => {
    expect(buildToolboxConfig(null, "bar")).toBeNull();
    expect(buildToolboxConfig({}, "bar")).toBeNull();
    expect(buildToolboxConfig({ enabled: false }, "bar")).toBeNull();
    expect(buildToolboxConfig({ show: false }, "bar")).toBeNull();
    expect(buildToolboxConfig({ show_toolbox: false }, "bar")).toBeNull();
  });

  test("returns toolbox config when enabled: true or show: true", () => {
    const config = { enabled: true };
    const toolbox = buildToolboxConfig(config, "bar", "Water Points");

    expect(toolbox).toMatchObject({
      show: true,
      right: 10,
      top: 0,
      orient: "horizontal",
      feature: {
        saveAsImage: { show: true, title: "Save as image" },
        dataView: {
          show: true,
          readOnly: true,
          optionToContent: expect.any(Function),
        },
        restore: { show: true, title: "Restore" },
        dataZoom: { show: true, yAxisIndex: "none" },
      },
    });
  });

  test("omits disabled features completely from feature object", () => {
    const config = {
      enabled: true,
      features: {
        saveAsImage: true,
        dataView: true,
        restore: true,
        dataZoom: false,
      },
    };
    const toolbox = buildToolboxConfig(config, "bar");

    expect(toolbox.feature.saveAsImage).toEqual({
      show: true,
      title: "Save as image",
    });
    expect(toolbox.feature.dataView.show).toBe(true);
    expect(toolbox.feature.restore).toEqual({ show: true, title: "Restore" });
    expect(toolbox.feature.dataZoom).toBeUndefined();
  });

  test("respects position presets (top-left, bottom-right, bottom-left)", () => {
    const topLeft = buildToolboxConfig(
      { enabled: true, position: "top-left" },
      "line"
    );
    expect(topLeft.left).toBe(10);
    expect(topLeft.top).toBe(0);
    expect(topLeft.right).toBeUndefined();

    const bottomRight = buildToolboxConfig(
      { enabled: true, position: "bottom-right" },
      "scatter"
    );
    expect(bottomRight.right).toBe(10);
    expect(bottomRight.bottom).toBe(0);
    expect(bottomRight.top).toBeUndefined();

    const bottomLeft = buildToolboxConfig(
      { enabled: true, position: "bottom-left" },
      "bar"
    );
    expect(bottomLeft.left).toBe(10);
    expect(bottomLeft.bottom).toBe(0);
  });

  test("filters dataZoom for pie chart type", () => {
    const config = {
      enabled: true,
      features: {
        saveAsImage: true,
        dataView: true,
        restore: true,
        dataZoom: true,
      },
    };
    const toolbox = buildToolboxConfig(config, "pie");

    expect(toolbox.feature.saveAsImage).toEqual({
      show: true,
      title: "Save as image",
    });
    expect(toolbox.feature.dataView.show).toBe(true);
    expect(toolbox.feature.restore).toEqual({ show: true, title: "Restore" });
    expect(toolbox.feature.dataZoom).toBeUndefined();
  });

  test("returns null if all features are disabled", () => {
    const config = {
      enabled: true,
      features: {
        saveAsImage: false,
        dataView: false,
        restore: false,
        dataZoom: false,
      },
    };
    expect(buildToolboxConfig(config, "bar")).toBeNull();
  });
});

describe("toolboxHelper - parseChartDataForView", () => {
  test("extracts clean category and value headers for single-series bar/line chart without series_0", () => {
    const opt = {
      xAxis: { data: ["Urban", "Rural"] },
      series: [{ name: "series_0", data: [42, 58] }],
    };
    const { columns, rows } = parseChartDataForView(opt, "Population");

    expect(columns).toEqual([
      { title: "Category", key: "category" },
      { title: "Population", key: "series_0" },
    ]);
    expect(rows).toEqual([
      { category: "Urban", series_0: 42 },
      { category: "Rural", series_0: 58 },
    ]);
  });

  test("extracts meaningful series names for multi-series / stacked bar chart", () => {
    const opt = {
      xAxis: { data: ["2022", "2023"] },
      series: [
        { name: "Operational", data: [100, 120] },
        { name: "Broken", data: [20, 15] },
      ],
    };
    const { columns, rows } = parseChartDataForView(opt, "Water Status");

    expect(columns).toEqual([
      { title: "Category", key: "category" },
      { title: "Operational", key: "series_0" },
      { title: "Broken", key: "series_1" },
    ]);
    expect(rows).toEqual([
      { category: "2022", series_0: 100, series_1: 20 },
      { category: "2023", series_0: 120, series_1: 15 },
    ]);
  });

  test("extracts clean category and value columns for pie chart", () => {
    const opt = {
      series: [
        {
          type: "pie",
          data: [
            { name: "Functional", value: 75 },
            { name: "Non-Functional", value: 25 },
          ],
        },
      ],
    };
    const { columns, rows } = parseChartDataForView(opt, "Status Share");

    expect(columns).toEqual([
      { title: "Category", key: "category" },
      { title: "Status Share", key: "value" },
    ]);
    expect(rows).toEqual([
      { category: "Functional", value: 75 },
      { category: "Non-Functional", value: 25 },
    ]);
  });

  test("extracts name, x, and y columns for scatter chart", () => {
    const opt = {
      xAxis: { name: "Population" },
      yAxis: { name: "Water Points" },
      series: [
        {
          type: "scatter",
          data: [
            [500, 10, "District A"],
            [1200, 25, "District B"],
          ],
        },
      ],
    };
    const { columns, rows } = parseChartDataForView(opt, "Correlation");

    expect(columns).toEqual([
      { title: "Name", key: "name" },
      { title: "Population", key: "x" },
      { title: "Water Points", key: "y" },
    ]);
    expect(rows).toEqual([
      { name: "District A", x: 500, y: 10 },
      { name: "District B", x: 1200, y: 25 },
    ]);
  });

  test("extracts columns and rows from dataset source object format", () => {
    const opt = {
      dataset: {
        source: [
          { label: "Jan", count: 10 },
          { label: "Feb", count: 20 },
        ],
      },
    };
    const { columns, rows } = parseChartDataForView(opt);

    expect(columns).toEqual([
      { title: "Category", key: "label" },
      { title: "count", key: "count" },
    ]);
    expect(rows).toHaveLength(2);
  });
});

describe("toolboxHelper - renderDataViewTable & exportDataViewToExcel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renderDataViewTable generates an HTML container with a table and download button", () => {
    const opt = {
      xAxis: { data: ["Site A", "Site B"] },
      series: [{ name: "Flow Rate", data: [15, 22] }],
    };
    const dom = renderDataViewTable(opt, "Water Flow");

    expect(dom).toBeInstanceOf(HTMLElement);
    const button = dom.querySelector("button");
    expect(button).not.toBeNull();
    expect(button.innerText).toBe("Download Excel (.xlsx)");

    const table = dom.querySelector("table");
    expect(table).not.toBeNull();
    expect(table.querySelectorAll("th")).toHaveLength(2);
    expect(table.querySelectorAll("tbody tr")).toHaveLength(2);

    const saveSpy = jest.spyOn(Excel.prototype, "saveAs");
    // Clicking the download button triggers exportDataViewToExcel
    button.click();
    expect(saveSpy).toHaveBeenCalledWith("Water Flow.xlsx");
    saveSpy.mockRestore();
  });

  test("exportDataViewToExcel creates and saves Excel sheet", () => {
    const saveSpy = jest.spyOn(Excel.prototype, "saveAs");
    const columns = [
      { title: "Category", key: "category" },
      { title: "Value", key: "value" },
    ];
    const rows = [{ category: "Test", value: 100 }];

    exportDataViewToExcel(columns, rows, "Test Export");
    expect(saveSpy).toHaveBeenCalledWith("Test Export.xlsx");
    saveSpy.mockRestore();
  });
});
