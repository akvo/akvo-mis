import React from "react";
import PropTypes from "prop-types";

const PIN_POSITIONS = [
  { left: "24%", top: "36%" },
  { left: "52%", top: "54%" },
  { left: "68%", top: "32%" },
  { left: "40%", top: "70%" },
  { left: "80%", top: "50%" },
  { left: "30%", top: "58%" },
];

const DEFAULT_COLOR = "#64A73B";

const VizMap = ({ config, data }) => {
  const statusColors = config?.config?.status_colors || {};
  const points = Array.isArray(data) ? data : [];

  const getPointColor = (point) => {
    if (point.status && statusColors[point.status]) {
      return statusColors[point.status];
    }
    return config?.color || DEFAULT_COLOR;
  };

  const statuses = [...new Set(points.map((p) => p.status).filter(Boolean))];

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 190,
        borderRadius: 6,
        overflow: "hidden",
        background: "linear-gradient(135deg, #e7eef4, #dde8ea)",
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 320 190"
        preserveAspectRatio="none"
        style={{ position: "absolute", inset: 0 }}
      >
        <path
          d="M0 120 Q80 90 150 118 T320 100 V190 H0 Z"
          fill="#d4e4d0"
          opacity="0.6"
        />
        <path
          d="M40 40 Q120 60 180 40 T300 55"
          fill="none"
          stroke="#c3d3dd"
          strokeWidth="2"
        />
      </svg>
      {points.slice(0, PIN_POSITIONS.length).map((point, i) => {
        const pos = PIN_POSITIONS[i];
        return (
          <span
            key={point.id || i}
            title={point.name}
            style={{
              position: "absolute",
              left: pos.left,
              top: pos.top,
              width: 13,
              height: 13,
              borderRadius: "50%",
              background: getPointColor(point),
              border: "2px solid #fff",
              boxShadow: "0 1px 3px rgba(0,0,0,.3)",
            }}
          />
        );
      })}
      {points.length === 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#8a93a0",
            fontSize: 13,
          }}
        >
          Map preview
        </div>
      )}
      {statuses.length > 0 && (
        <div
          style={{
            position: "absolute",
            left: 10,
            bottom: 10,
            display: "flex",
            gap: 10,
            background: "rgba(255,255,255,.9)",
            padding: "5px 10px",
            borderRadius: 6,
            fontSize: 11,
          }}
        >
          {statuses.map((s) => (
            <span
              key={s}
              style={{ display: "flex", alignItems: "center", gap: 5 }}
            >
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: statusColors[s] || DEFAULT_COLOR,
                }}
              />
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

VizMap.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizMap;
