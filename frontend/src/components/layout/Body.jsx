import React from "react";
import PropTypes from "prop-types";
import { useLocation } from "react-router-dom";

const Body = ({ children, className = "body", ...props }) => {
  const { pathname } = useLocation();
  if (["/not-found", "/coming-soon"].includes(pathname)) {
    return "";
  }
  // Full-bleed for the public onboarding wizard at "/": drops the workspace
  // `.body` padding/gutters so its own shell reaches the viewport edges (the
  // rule lives in landing.css, keyed on `.body-home`).
  if (pathname === "/") {
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
