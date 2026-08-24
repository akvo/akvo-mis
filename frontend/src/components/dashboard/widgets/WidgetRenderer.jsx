import React from "react";
import PropTypes from "prop-types";
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
