import React from "react";
import PropTypes from "prop-types";
import Header from "./Header";
import Banner from "./Banner";
import InspectionBanner from "./InspectionBanner";
import Body from "./Body";
import { Row } from "antd";
import "./style.scss";

const Layout = ({ children, className = "", ...props }) => {
  return (
    <Row className={`${className} layout`} {...props}>
      {children}
    </Row>
  );
};

Layout.propTypes = {
  children: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.element,
    PropTypes.node,
  ]).isRequired,
  className: PropTypes.string,
};

Layout.Header = Header;
Layout.Banner = Banner;
Layout.InspectionBanner = InspectionBanner;
Layout.Body = Body;

export default Layout;
