import React, { useMemo } from "react";
import { Row, Col, Space, Dropdown } from "antd";
import {
  Link,
  Outlet,
  useLocation,
  useNavigate,
  Navigate,
} from "react-router-dom";
import { UserOutlined } from "@ant-design/icons";
import { store, uiText } from "../../lib";
import { eraseCookieFromAllPaths } from "../../util/date";
import "./style.scss";

// The console's own shell rather than a reuse of ControlCenterLayout,
// which is built around a workspace's sidebar and breadcrumbs. Bending
// that one to a tenant-less context would couple two things that change
// for different reasons.
//
// It carries sign-out because App suppresses the app's own header on
// this host: that header fetches published dashboards for the workspace
// and links to /control-center, neither of which exists here. Dropping
// it would otherwise leave an operator with no way out of the session.
const AdminLayout = () => {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const signOut = () => {
    eraseCookieFromAllPaths("AUTH_TOKEN");
    store.update((s) => {
      s.isLoggedIn = false;
      s.user = null;
    });
    navigate("/login");
  };

  // The same account dropdown the workspace header carries, so the two
  // products behave alike where they overlap. It holds one item today
  // because the console has no profile page to link to.
  const accountMenu = [
    {
      key: "signOut",
      danger: true,
      label: (
        <a
          onClick={(e) => {
            e.preventDefault();
            signOut();
          }}
        >
          {text?.signOut}
        </a>
      ),
    },
  ];

  // Every console page is behind this. An expired or absent session
  // lands on the login page rather than on an empty table. App gates
  // RouteList behind its bootstrap loader, so `user` here is the
  // settled answer rather than the not-asked-yet one.
  if (!user?.is_platform_admin) {
    return <Navigate to="/login" replace />;
  }

  const tab = (to, label) => (
    <Link to={to} className={pathname.startsWith(to) ? "admin-nav-active" : ""}>
      {label}
    </Link>
  );

  return (
    <div id="admin-console">
      <Row className="admin-header" align="middle" justify="space-between">
        <Col>
          <Space size={28}>
            <span className="admin-brand">{text.platformConsole}</span>
            <Space size={24} className="admin-nav">
              {tab("/admin/tenants", text.consoleTenants)}
              {tab("/admin/operators", text.consoleOperators)}
            </Space>
          </Space>
        </Col>
        <Col>
          <Dropdown menu={{ items: accountMenu }}>
            <a
              className="admin-account"
              onClick={(e) => {
                e.preventDefault();
              }}
            >
              <Space size={8}>
                {user?.email}
                <UserOutlined />
              </Space>
            </a>
          </Dropdown>
        </Col>
      </Row>
      <div className="admin-body">
        <Outlet />
      </div>
    </div>
  );
};

export default AdminLayout;
