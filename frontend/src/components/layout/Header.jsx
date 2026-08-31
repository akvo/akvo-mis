import React, { useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import { Row, Col, Button, Dropdown } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { config, store, uiText } from "../../lib";
import { eraseCookieFromAllPaths } from "../../util/date";

const Header = ({ className = "header", ...props }) => {
  const { isLoggedIn, user } = store.useState();
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const signOut = useCallback(async () => {
    eraseCookieFromAllPaths("AUTH_TOKEN");
    store.update((s) => {
      s.isLoggedIn = false;
      s.user = null;
    });
    navigate("login");
  }, [navigate]);

  const accessUserMenu = useMemo(() => {
    const userMenu = [
      {
        key: "controlCenter",
        label: (
          <Link
            key="controlCenter"
            className="usermenu-menu-item"
            to="/control-center"
          >
            {text?.controlCenter}
          </Link>
        ),
      },
      {
        key: "profile",
        label: (
          <Link
            key="profile"
            className="usermenu-menu-item"
            to="/control-center/profile"
          >
            {text?.myProfile}
          </Link>
        ),
      },
      {
        key: "signOut",
        danger: true,
        label: (
          <a
            key="signOut"
            className="usermenu-menu-item"
            onClick={() => {
              signOut();
            }}
          >
            {text?.signOut}
          </a>
        ),
      },
    ];
    return userMenu;
  }, [text, signOut]);

  return (
    <Row
      className={className}
      align="middle"
      justify="space-between"
      {...props}
    >
      <Col>
        <div className="logo">
          <Link to="/">
            <div className="logo-wrapper">
              <img
                className="small-logo"
                src={config.siteLogo}
                alt={config.siteLogo}
              />
            </div>
          </Link>
        </div>
      </Col>
      {!location.pathname.includes("/report/") && (
        <Col>
          <div className="account">
            {isLoggedIn ? (
              <Dropdown menu={{ items: accessUserMenu }}>
                <a
                  className="ant-dropdown-link"
                  onClick={(e) => {
                    e.preventDefault();
                  }}
                >
                  {user?.name || ""}
                  <span className="icon">
                    <UserOutlined />
                  </span>
                </a>
              </Dropdown>
            ) : (
              <Link to={"/login"}>
                <Button type="primary" shape="round">
                  {text?.login}
                </Button>
              </Link>
            )}
          </div>
        </Col>
      )}
    </Row>
  );
};

Header.propTypes = {
  className: PropTypes.string,
};

export default Header;
