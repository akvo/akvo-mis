import React from "react";
import PropTypes from "prop-types";
import { useLocation } from "react-router-dom";
import store from "../../lib/store";

const Body = ({ children, className = "body", ...props }) => {
  const { pathname } = useLocation();
  // A missing tenant host renders <WorkspaceNotFound/> (App.js) at whatever path
  // the visitor typed, so it can't be matched by pathname — full-bleed it here
  // too, so its AuthShell backdrop reaches the edges.
  const tenantMissing = store.useState((s) => s.tenantMissing);
  if (["/not-found", "/coming-soon"].includes(pathname)) {
    return "";
  }
  // Full-bleed for the public onboarding wizard at "/" and the auth pages
  // (login, reset password, workspace finder, email activation), which share
  // the AuthShell backdrop: drops the workspace `.body` padding/gutters so the
  // shell reaches the viewport edges (the rule lives in landing.css, keyed on
  // `.body-home`).
  const fullBleed =
    tenantMissing ||
    pathname === "/" ||
    pathname === "/login" ||
    pathname === "/forgot-password" ||
    pathname === "/find-workspace" ||
    pathname.startsWith("/login/") ||
    pathname.startsWith("/activate");
  if (fullBleed) {
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
