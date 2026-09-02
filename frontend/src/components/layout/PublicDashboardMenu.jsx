import React, { useEffect, useState } from "react";
import { Dropdown } from "antd";
import { DownOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";

// =========================================================
// The public dashboard menu
// =========================================================
//
// Anonymous visitors see this; so does everyone signed in, whose list
// widens server-side to include their workspace's private published
// dashboards if their role carries any dashboard access. The widening
// happens in the endpoint, so there is nothing to branch on here.
//
// Renders nothing at all — not an empty menu — when the list is empty.
// A workspace with no public dashboards, and the base domain of a SaaS
// deployment (which names no workspace, so the list is always empty),
// both get no chrome rather than a dead control.

const PublicDashboardMenu = () => {
  const { language, isLoggedIn } = store.useState((s) => s);
  const text = uiText[language.active];
  const [dashboards, setDashboards] = useState([]);

  useEffect(() => {
    let cancelled = false;
    dashboardApi
      .listPublished()
      .then((res) => {
        if (!cancelled) {
          setDashboards(Array.isArray(res.data) ? res.data : []);
        }
      })
      .catch(() => {
        // No menu is the right answer for every failure here: no
        // workspace on this host, a network error, a server fault.
        if (!cancelled) {
          setDashboards([]);
        }
      });
    return () => {
      cancelled = true;
    };
    // Refetched on sign-in and sign-out: the endpoint widens with the
    // session, so the list has to be rebuilt once we know who is asking.
  }, [isLoggedIn]);

  if (dashboards.length === 0) {
    return null;
  }

  const items = dashboards.map((dashboard) => ({
    key: dashboard.slug,
    label: (
      <Link className="usermenu-menu-item" to={`/dashboards/${dashboard.slug}`}>
        {dashboard.name}
      </Link>
    ),
  }));

  return (
    <Dropdown menu={{ items }}>
      <a
        className="ant-dropdown-link public-dashboard-menu"
        onClick={(e) => {
          e.preventDefault();
        }}
      >
        {text?.menuDashboards}
        <span className="icon">
          <DownOutlined />
        </span>
      </a>
    </Dropdown>
  );
};

export default PublicDashboardMenu;
