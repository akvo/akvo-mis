import { buildToolboxConfig } from "../toolboxHelper";

describe("toolboxHelper - buildToolboxConfig", () => {
  test("returns null if widgetConfig is missing or show_toolbox is false/falsy", () => {
    expect(buildToolboxConfig(null, "bar")).toBeNull();
    expect(buildToolboxConfig({}, "bar")).toBeNull();
    expect(buildToolboxConfig({ show_toolbox: false }, "bar")).toBeNull();
    expect(buildToolboxConfig({ show_toolbox: null }, "bar")).toBeNull();
  });

  test("returns default toolbox config when show_toolbox is true", () => {
    const widgetConfig = { show_toolbox: true };
    const toolbox = buildToolboxConfig(widgetConfig, "bar");

    expect(toolbox).toEqual({
      show: true,
      right: 10,
      top: 0,
      orient: "horizontal",
      feature: {
        saveAsImage: { show: true },
        dataView: { show: true, readOnly: false },
        restore: { show: true },
        dataZoom: { show: true },
      },
    });
  });

  test("respects position presets (top-left, bottom-right, bottom-left)", () => {
    const topLeft = buildToolboxConfig(
      { show_toolbox: true, toolbox_position: "top-left" },
      "line"
    );
    expect(topLeft.left).toBe(10);
    expect(topLeft.top).toBe(0);
    expect(topLeft.right).toBeUndefined();

    const bottomRight = buildToolboxConfig(
      { show_toolbox: true, toolbox_position: "bottom-right" },
      "scatter"
    );
    expect(bottomRight.right).toBe(10);
    expect(bottomRight.bottom).toBe(0);
    expect(bottomRight.top).toBeUndefined();

    const bottomLeft = buildToolboxConfig(
      { show_toolbox: true, toolbox_position: "bottom-left" },
      "bar"
    );
    expect(bottomLeft.left).toBe(10);
    expect(bottomLeft.bottom).toBe(0);
  });

  test("filters dataZoom for pie chart type", () => {
    const widgetConfig = {
      show_toolbox: true,
      toolbox_features: {
        saveAsImage: true,
        dataView: true,
        restore: true,
        dataZoom: true,
      },
    };
    const toolbox = buildToolboxConfig(widgetConfig, "pie");

    expect(toolbox.feature.saveAsImage).toEqual({ show: true });
    expect(toolbox.feature.dataView).toEqual({ show: true, readOnly: false });
    expect(toolbox.feature.restore).toEqual({ show: true });
    expect(toolbox.feature.dataZoom).toBeUndefined();
  });

  test("respects granular feature flags", () => {
    const widgetConfig = {
      show_toolbox: true,
      toolbox_features: {
        saveAsImage: true,
        dataView: false,
        restore: false,
        dataZoom: true,
      },
    };
    const toolbox = buildToolboxConfig(widgetConfig, "line");

    expect(toolbox.feature).toEqual({
      saveAsImage: { show: true },
      dataView: { show: false, readOnly: false },
      restore: { show: false },
      dataZoom: { show: true },
    });
  });

  test("returns null if show_toolbox is true but all features are false", () => {
    const widgetConfig = {
      show_toolbox: true,
      toolbox_features: {
        saveAsImage: false,
        dataView: false,
        restore: false,
        dataZoom: false,
      },
    };
    expect(buildToolboxConfig(widgetConfig, "bar")).toBeNull();
  });
});
