import React from "react";
import PropTypes from "prop-types";
import { WIDGET_TYPES } from "./builderConstants";

const typeIcons = {
  kpi: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 15l4-4 3 3 5-6 4 4"
        stroke="#1890ff"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <text x="4" y="8" fontSize="7" fill="#1890ff" fontWeight="700">
        123
      </text>
    </svg>
  ),
  bar: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <rect x="4" y="11" width="3.6" height="9" fill="#1890ff" />
      <rect x="10" y="6" width="3.6" height="14" fill="#1890ff" />
      <rect x="16" y="9" width="3.6" height="11" fill="#1890ff" />
    </svg>
  ),
  line: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 16l4-5 4 3 8-8"
        stroke="#1651b6"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  pie: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <circle
        cx="12"
        cy="12"
        r="8"
        stroke="#64A73B"
        strokeWidth="4"
        strokeDasharray="30 100"
      />
      <circle
        cx="12"
        cy="12"
        r="8"
        stroke="#cfe4c3"
        strokeWidth="4"
        strokeDasharray="20 100"
        strokeDashoffset="-30"
      />
    </svg>
  ),
  table: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <rect
        x="4"
        y="5"
        width="16"
        height="14"
        rx="1.5"
        stroke="#5b6472"
        strokeWidth="1.6"
      />
      <path d="M4 10h16M4 15h16M10 5v14" stroke="#5b6472" strokeWidth="1.4" />
    </svg>
  ),
  map: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 21s7-6.5 7-12a7 7 0 10-14 0c0 5.5 7 12 7 12z"
        stroke="#64A73B"
        strokeWidth="1.7"
      />
      <circle cx="12" cy="9" r="2.4" stroke="#64A73B" strokeWidth="1.7" />
    </svg>
  ),
  section_title: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <path
        d="M5 6h14M5 6v-.5M12 6v13M9 19h6"
        stroke="#5b6472"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  ),
};

const BuilderPalette = ({ onAdd }) => (
  <div className="builder-palette">
    <div className="builder-palette-heading">Add widget</div>
    <div className="builder-palette-list">
      {WIDGET_TYPES.map((wt) => (
        <button
          key={wt.type}
          className="builder-palette-item"
          onClick={() => onAdd(wt.type)}
        >
          <span
            className="builder-palette-icon"
            style={{ background: wt.iconBg }}
          >
            {typeIcons[wt.type]}
          </span>
          <span>
            <span className="builder-palette-label">{wt.label}</span>
            <span className="builder-palette-desc">{wt.desc}</span>
          </span>
        </button>
      ))}
    </div>
    <div className="builder-palette-hint">
      Widgets stack top to bottom. Set each widget&apos;s width in the inspector
      to place two or three side by side.
    </div>
  </div>
);

BuilderPalette.propTypes = {
  onAdd: PropTypes.func.isRequired,
};

export default BuilderPalette;
