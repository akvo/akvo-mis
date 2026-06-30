import React, { useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import { Row, Col, Button, Dropdown, Space } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { FaChevronDown } from "react-icons/fa";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { config, store, uiText } from "../../lib";
import { eraseCookieFromAllPaths } from "../../util/date";
import { getForms } from "../../util/form";
import { listVisualizations } from "../../config/visualizations";

const Header = ({ className = "header", ...props }) => {
  const { isLoggedIn, user } = store.useState();
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const dashboardForms = useMemo(() => {
    const registered = listVisualizations();
    const availableFormIds = new Set(getForms().map((f) => f.id));
    return registered.filter((d) => availableFormIds.has(d.parent_form_id));
  }, []);
  const showDashboardsMenu =
    location.pathname.startsWith("/control-center") ||
    location.pathname.startsWith("/dashboard");

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

  const DashboardMenu = useMemo(() => {
    return dashboardForms?.map((d) => {
      return {
        key: d.slug,
        label: (
          <Link
            key={d.slug}
            to={`/dashboard/${d.slug}`}
            className="dropdown-menu-item"
          >
            {d.name}
          </Link>
        ),
      };
    });
  }, [dashboardForms]);

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
          {showDashboardsMenu && dashboardForms.length > 0 && (
            <div className="navigation">
              <Space>
                <Dropdown menu={{ items: DashboardMenu }}>
                  <a
                    className="ant-dropdown-link"
                    onClick={(e) => {
                      e.preventDefault();
                    }}
                  >
                    {text?.dashboards}
                    <FaChevronDown />
                  </a>
                </Dropdown>
              </Space>
            </div>
          )}
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
