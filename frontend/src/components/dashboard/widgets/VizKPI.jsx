import React from "react";
import PropTypes from "prop-types";

const VizKPI = ({ config, data }) => {
  const value = data?.value ?? "—";
  const color = config?.color || "#1890ff";
  const suffix = config?.config?.value_type === "percentage" ? "%" : "";

  return (
    <div style={{ padding: "18px 20px" }}>
      <div
        style={{
          fontSize: 28,
          fontWeight: 600,
          lineHeight: 1.2,
          color,
        }}
      >
        {value}
        {suffix}
      </div>
    </div>
  );
};

VizKPI.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.object,
};

export default VizKPI;
