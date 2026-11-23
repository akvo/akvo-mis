import React from "react";
import PropTypes from "prop-types";
import { useLocation } from "react-router-dom";

const Body = ({ children, className = "body", ...props }) => {
  const { pathname } = useLocation();
  if (["/not-found", "/coming-soon"].includes(pathname)) {
    return "";
  }
  // Full-bleed for the public landing surface (landing + onboarding wizard):
  // drops the workspace `.body` padding/gutters so their own shell reaches the
  // viewport edges (the rule lives in landing.css, keyed on `.body-home`).
  if (["/", "/onboarding"].includes(pathname)) {
    className += " body-home";
  }
  return (
    <div className={className} {...props}>
      {children}
    </div>
  );
};

Body.propTypes = {
  children: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.element,
    PropTypes.node,
  ]).isRequired,
  className: PropTypes.string,
};

export default Body;
