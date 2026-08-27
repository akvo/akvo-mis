import React from "react";
import PropTypes from "prop-types";

// 18px in the viewer, 16px on the builder canvas. The size is set by the
// surrounding stylesheet rather than by a prop, so that the shared
// renderer tree has no way to tell which of its two callers it has.
const VizSectionTitle = ({ config }) => {
  const text = config?.config?.text || config?.title || "";
  return <div className="viz-section-title">{text}</div>;
};

VizSectionTitle.propTypes = {
  config: PropTypes.object.isRequired,
};

export default VizSectionTitle;
