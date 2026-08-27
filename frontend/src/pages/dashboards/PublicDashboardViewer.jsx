import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Spin } from "antd";
import dashboardApi from "../../util/dashboardApi";
import DashboardGrid from "../../components/dashboard/DashboardGrid";
import DashboardViewFilters from "../../components/dashboard/DashboardViewFilters";
import { store, uiText } from "../../lib";
import "./viewer.scss";

// =========================================================
// /public/dashboards/:slug — the anonymous viewer (VIZ-010)
// =========================================================
//
// The same page as the authenticated viewer, minus the parts that assume
// somewhere to go back to: an anonymous visitor arrived by link and has no
// dashboard list to return to.
//
// It renders through `DashboardGrid` like every other surface, and the
// only difference reaches the data layer as `isPublic` — which changes the
// namespace and nothing else. That is what keeps "what the public sees"
// and "what a colleague sees" the same rendering, so a public dashboard
// cannot quietly diverge from the one its author reviewed.

const EMPTY_FILTERS = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
};

const PublicDashboardViewer = () => {
  const { slug } = useParams();
  const { language } = store.useState((s) => s);
  const text = useMemo(() => uiText[language.active], [language.active]);

  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    dashboardApi
      .getPublic(slug)
      .then((res) => {
        if (!cancelled) {
          setDashboard(res.data);
          setFilters(EMPTY_FILTERS);
        }
      })
      .catch(() => {
        // Internal, unpublished, deleted, another workspace's, or the
        // wrong host: one screen for all of them. The client cannot tell
        // them apart and should not guess out loud.
        if (!cancelled) {
          setNotFound(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (loading) {
    return (
      <div className="dashboard-view-shell">
        <div className="dashboard-view-loading">
          <Spin size="large" />
        </div>
      </div>
    );
  }

  if (notFound || !dashboard) {
    return (
      <div className="dashboard-view-shell">
        <div className="dashboard-view-empty">
          <h2>{text.dashboardNotFound}</h2>
          <p>{text.dashboardNotFoundHint}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-view-shell">
      <div className="dashboard-view-content">
        <div className="dashboard-view-header">
          <div className="dashboard-view-header-inner">
            <div className="dashboard-view-title">{dashboard.name}</div>
            {dashboard.description && (
              <div className="dashboard-view-desc">{dashboard.description}</div>
            )}
          </div>
        </div>

        <DashboardViewFilters
          defaultFilters={dashboard.default_filters}
          value={filters}
          onChange={setFilters}
        />

        <DashboardGrid
          widgets={dashboard.widgets}
          filters={filters}
          source={{ slug, isPublic: true }}
        />
      </div>
    </div>
  );
};

export default PublicDashboardViewer;
