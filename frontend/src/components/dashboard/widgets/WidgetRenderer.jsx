import React from "react";
import PropTypes from "prop-types";
// akvo-charts renders <div className="ae-container"> and sizes the chart to
// that element, but the rule making it fill its parent ships in the
// package's own stylesheet, which nothing had ever imported. Without it the
// chart has no height box, so ECharts picks its own and overflows the card
// — charts came out visibly cropped at the bottom. Imported here because
// every chart reaches the DOM through this component, on both the viewer
// and the builder canvas. Same pattern as akvo-react-form in Forms.jsx.
import "akvo-charts/dist/index.css";
import VizKPI from "./VizKPI";
import VizBar from "./VizBar";
import VizLine from "./VizLine";
import VizPie from "./VizPie";
import VizTable from "./VizTable";
import VizMap from "./VizMap";
import VizSectionTitle from "./VizSectionTitle";

const RENDERERS = {
  kpi: VizKPI,
  bar: VizBar,
  line: VizLine,
  pie: VizPie,
  table: VizTable,
  map: VizMap,
  section_title: VizSectionTitle,
};

const WidgetRenderer = ({ widget, data }) => {
  const Renderer = RENDERERS[widget.type];
  if (!Renderer) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        Unknown widget type: {widget.type}
      </div>
    );
  }
  return <Renderer config={widget} data={data} />;
};

WidgetRenderer.propTypes = {
  widget: PropTypes.object.isRequired,
  data: PropTypes.any,
};

export default WidgetRenderer;
