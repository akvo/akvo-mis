import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Spin } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import dashboardApi from "../../util/dashboardApi";
import DashboardGrid from "../../components/dashboard/DashboardGrid";
import DashboardViewFilters from "../../components/dashboard/DashboardViewFilters";
import { store, uiText } from "../../lib";
import "./viewer.scss";

// =========================================================
// /dashboards/:slug — the published dashboard
// =========================================================
//
// Reads the snapshot the author published, plus the widget health the
// server annotates at serve time, and hands both to the shared renderer.
// Layout follows the mockup's view screen (index.html:363-412).

const EMPTY_FILTERS = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
};

const DashboardViewer = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { language, isLoggedIn } = store.useState((s) => s);
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
      .getPublished(slug)
      .then((res) => {
        if (!cancelled) {
          setDashboard(res.data);
          // Filters start unbounded. `default_filters.date.default_range`
          // exists in VIZ-001 §4.4 but the builder inspector never writes
          // it, so honouring a range vocabulary nothing can author would
          // be dead code that is wrong by the time it has a caller.
          setFilters(EMPTY_FILTERS);
        }
      })
      .catch(() => {
        // Unpublished, deleted, another tenant's, or the server failing:
        // one screen for all of them. The client cannot tell them apart
        // and should not guess out loud.
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
        {isLoggedIn && (
          <button
            className="dashboard-view-back"
            title={text.backBtn}
            aria-label={text.backBtn}
            onClick={() => navigate("/control-center/dashboard")}
          >
            <ArrowLeftOutlined />
          </button>
        )}
        <div className="dashboard-view-empty">
          <h2>{text.dashboardNotFound}</h2>
          <p>{text.dashboardNotFoundHint}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-view-shell">
      {/* Fixed, and on its own. The bar that held it also held Edit and a
          copy of the dashboard's name; the list already offers Edit on
          every card and the header repeats the name directly below, so the
          page's widest row was chrome for one button. Fixed rather than
          scrolled away, because "back" is wanted most at the bottom of a
          long dashboard.

          Signed-in only: it targets /control-center/dashboard, a Private
          route. An anonymous visitor who clicked it would land on a login
          wall instead of going back to anything, so they simply get no
          control here. */}
      {isLoggedIn && (
        <button
          className="dashboard-view-back"
          title={text.backBtn}
          aria-label={text.backBtn}
          onClick={() => navigate("/control-center/dashboard")}
        >
          <ArrowLeftOutlined />
        </button>
      )}

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
          rootFormId={dashboard.root_form?.id}
          dashboardSlug={slug}
        />
      </div>
    </div>
  );
};

export default DashboardViewer;
