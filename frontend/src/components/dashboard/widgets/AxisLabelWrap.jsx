import React from "react";
import PropTypes from "prop-types";

const baseLabelStyle = {
  fontWeight: "bold",
  fontSize: 13,
  color: "#555",
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const yLabelStyle = {
  ...baseLabelStyle,
  writingMode: "vertical-rl",
  transform: "rotate(180deg)",
  textAlign: "center",
  maxHeight: "100%",
  padding: "4px 2px",
};

const xLabelStyle = {
  ...baseLabelStyle,
  textAlign: "center",
  padding: "2px 0",
  maxWidth: "100%",
};

const AxisLabelWrap = ({ xLabel, yLabel, children }) => {
  if (!xLabel && !yLabel) {
    return children;
  }
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
      }}
    >
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {yLabel && (
          <div style={yLabelStyle} title={yLabel}>
            {yLabel}
          </div>
        )}
        <div style={{ flex: 1, minWidth: 0, height: "100%" }}>{children}</div>
      </div>
      {xLabel && (
        <div style={xLabelStyle} title={xLabel}>
          {xLabel}
        </div>
      )}
    </div>
  );
};

AxisLabelWrap.propTypes = {
  xLabel: PropTypes.string,
  yLabel: PropTypes.string,
  children: PropTypes.node.isRequired,
};

export default AxisLabelWrap;
