import React from "react";
import PropTypes from "prop-types";

const VizSectionTitle = ({ config }) => {
  const text = config?.config?.text || config?.title || "";
  return (
    <div style={{ padding: "10px 14px" }}>
      <div
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: "#081c40",
        }}
      >
        {text}
      </div>
    </div>
  );
};

VizSectionTitle.propTypes = {
  config: PropTypes.object.isRequired,
};

export default VizSectionTitle;
