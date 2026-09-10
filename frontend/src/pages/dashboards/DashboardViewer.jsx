import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Dropdown, Spin, message } from "antd";
import { ArrowLeftOutlined, DownloadOutlined } from "@ant-design/icons";
import dashboardApi from "../../util/dashboardApi";
import { exportDashboard } from "../../util/dashboardExport";
import DashboardGrid from "../../components/dashboard/DashboardGrid";
import DashboardViewFilters from "../../components/dashboard/DashboardViewFilters";
import EmbedFrame from "../../components/dashboard/EmbedFrame";
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
  const { language } = store.useState((s) => s);
  const text = useMemo(() => uiText[language.active], [language.active]);

  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  // The element html2canvas photographs. It wraps the header, the filter
  // bar and the grid — but NOT `.dashboard-view-content`, which is the
  // scrolling box: capturing that would capture a viewport-sized window
  // onto the dashboard rather than the dashboard.
  const captureRef = useRef(null);
  const [exporting, setExporting] = useState(false);

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

  const handleExport = async ({ key }) => {
    setExporting(true);
    try {
      await exportDashboard(captureRef.current, {
        format: key,
        name: dashboard.name,
      });
    } catch {
      // Nothing actionable to tell them apart: a tainted canvas, an
      // out-of-memory canvas and a browser that refused the download all
      // arrive here, and none of them is the visitor's to fix.
      message.error(text.dashboardExportFailed);
    } finally {
      setExporting(false);
    }
  };

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
        <button
          className="dashboard-view-back"
          title={text.backBtn}
          aria-label={text.backBtn}
          onClick={() => navigate(-1)}
        >
          <ArrowLeftOutlined />
        </button>
        <div className="dashboard-view-empty">
          <h2>{text.dashboardNotFound}</h2>
          <p>{text.dashboardNotFoundHint}</p>
        </div>
      </div>
    );
  }

  const isEmbed = dashboard.kind === "embed";

  const header = (
    <div className="dashboard-view-header">
      <div className="dashboard-view-header-inner">
        <div className="dashboard-view-header-text">
          <div className="dashboard-view-title">{dashboard.name}</div>
          {dashboard.description && (
            <div className="dashboard-view-desc">{dashboard.description}</div>
          )}
        </div>
        {/* No Export for an embed: the frame is another origin's
            document, so the capture would be an empty box where the
            report is. The external tool has its own export. */}
        {!isEmbed && (
          <div
            className="dashboard-view-header-actions"
            data-html2canvas-ignore
          >
            <Dropdown
              trigger={["click"]}
              placement="bottomRight"
              disabled={exporting}
              menu={{
                onClick: handleExport,
                items: [
                  { key: "png", label: text.dashboardExportPng },
                  { key: "pdf", label: text.dashboardExportPdf },
                ],
              }}
            >
              <Button icon={<DownloadOutlined />} loading={exporting}>
                {text.dashboardExport}
              </Button>
            </Dropdown>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="dashboard-view-shell">
      <button
        className="dashboard-view-back"
        title={text.backBtn}
        aria-label={text.backBtn}
        onClick={() => navigate(-1)}
      >
        <ArrowLeftOutlined />
      </button>

      {/* The embed branch needs a flex column to hand the frame the
          height it fills; the modifier keeps that off the widget grid,
          which shares this element. */}
      <div
        className={`dashboard-view-content${
          isEmbed ? " dashboard-view-content-embed" : ""
        }`}
      >
        {isEmbed ? (
          <>
            {header}
            {/* No filter bar: an embed has no data of ours to filter, and
                a control that changes nothing is worse than no control. */}
            <EmbedFrame src={dashboard.embed_url} title={dashboard.name} />
          </>
        ) : (
          <div className="dashboard-view-capture" ref={captureRef}>
            {header}

            <DashboardViewFilters
              defaultFilters={dashboard.default_filters}
              rootAdministrationId={dashboard.root_administration_id}
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
        )}
      </div>
    </div>
  );
};

export default DashboardViewer;
