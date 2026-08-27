import React from "react";
import PropTypes from "prop-types";

// The title is rendered here rather than by the caller because the mockup
// puts it inside the body in view mode (12px, above the value) and in the
// card header on the builder canvas. The canvas hides this copy in CSS
// rather than the component taking a `mode` prop — see viewer.scss and
// builder.scss. Sizes live there too, for the same reason.
const VizKPI = ({ config, data }) => {
  const raw = data?.value;
  const color = config?.color || "#1890ff";
  const suffix = config?.config?.value_type === "percentage" ? "%" : "";

  const missing = raw === null || typeof raw === "undefined";
  // Thousands separators: an unformatted "12480" on a dashboard reads as a
  // different order of magnitude at a glance than "12,480".
  const value = missing ? "—" : Number(raw).toLocaleString();

  return (
    <div className="viz-kpi">
      <div className="viz-kpi-title">{config?.title}</div>
      <div className="viz-kpi-value" style={{ color }}>
        {value}
        {missing ? "" : suffix}
      </div>
    </div>
  );
};

VizKPI.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.object,
};

export default VizKPI;
