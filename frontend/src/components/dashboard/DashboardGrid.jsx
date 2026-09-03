import React from "react";
import PropTypes from "prop-types";
import { Button, Skeleton } from "antd";
import WidgetRenderer from "./widgets/WidgetRenderer";
import useWidgetData from "../../util/hooks/useWidgetData";
import { WIDGET_BODY_HEIGHT } from "./widgetLayout";
import { store, uiText } from "../../lib";
const DEFAULT_KPI_COLOR = "#1890ff";

// =========================================================
// The dashboard renderer, shared by the viewer and the preview
// =========================================================
//
// This component takes a widget array and nothing else. No slug, no
// dashboard id, no `mode` flag, and deliberately no way to tell which of
// its two callers it has — the published viewer or the builder's preview.
// That is the whole point: the acceptance criterion is that both produce
// identical output from the same widgets, and a mode prop would let the
// two paths drift while still passing a test that only compares the happy
// case.
//
// The cell owns the chrome — card, header, body padding and height — and
// the `Viz*` components own only the visual inside it. `BuilderCanvas`
// draws its own, different chrome for the editing surface, so the two
// surfaces can differ exactly where the mockup says they differ
// (doc/design/VIZ-Example/index.html, view screen 363-412) without either
// knowing the other exists.

// In view mode only these five carry a card header. A KPI shows its title
// inside the body instead, and a section title is not a card at all.
const HEADER_TYPES = ["bar", "line", "pie", "table", "map"];

// Everything else is 16.
const BODY_PADDING = { table: 0, map: 12 };

const DashboardWidgetCell = ({
  widget,
  filters,
  rootFormId,
  dashboardSlug,
  text,
}) => {
  const { data, renderWidget, pagination, loading, error, refetch } =
    useWidgetData(widget, filters, { rootFormId, dashboardSlug });

  const type = widget.type;
  const height = WIDGET_BODY_HEIGHT[type];

  const cellStyle = { gridColumn: `span ${widget.col_span || 24}` };
  if (type === "kpi") {
    const kpiColor =
      (widget.config?.chart_colors || [])[0] || DEFAULT_KPI_COLOR;
    cellStyle.borderTop = `3px solid ${kpiColor}`;
  }

  const bodyStyle = { padding: BODY_PADDING[type] ?? 16 };
  if (height) {
    bodyStyle.height = height;
  }

  const body = () => {
    // Checked before anything else, and before the request is built: the
    // server already told us this widget cannot resolve, so asking anyway
    // would spend a round trip to be told again — and would sometimes come
    // back plausibly empty, hiding a stale reference behind "No data".
    if (widget.is_broken) {
      return (
        <div className="dashboard-view-cell-note">
          {widget.broken_reason === "form_deleted"
            ? text.dashboardWidgetFormGone
            : text.dashboardWidgetQuestionGone}
        </div>
      );
    }
    if (loading) {
      return <Skeleton active paragraph={{ rows: 3 }} />;
    }
    if (error) {
      return (
        <div className="dashboard-view-cell-note">
          <div>{text.dashboardWidgetError}</div>
          <Button type="link" size="small" onClick={refetch}>
            {text.dashboardWidgetRetry}
          </Button>
        </div>
      );
    }
    // An empty successful response is NOT a state here. It reaches the
    // renderer, which shows its own "No data" — under `current_state`,
    // sites never monitored are excluded unless include_unmonitored is
    // set, so empty is routine rather than a failure.
    return (
      <WidgetRenderer
        widget={renderWidget || widget}
        data={data}
        pagination={pagination}
      />
    );
  };

  return (
    <div
      className={`dashboard-view-cell dashboard-view-cell--${type}`}
      style={cellStyle}
      data-widget-title={widget.title || ""}
    >
      {HEADER_TYPES.includes(type) && (
        <div className="dashboard-view-cell-header">{widget.title}</div>
      )}
      <div className="dashboard-view-cell-body" style={bodyStyle}>
        {body()}
      </div>
    </div>
  );
};

DashboardWidgetCell.propTypes = {
  widget: PropTypes.object.isRequired,
  filters: PropTypes.object,
  rootFormId: PropTypes.number,
  dashboardSlug: PropTypes.string,
  text: PropTypes.object.isRequired,
};

const DashboardGrid = ({ widgets, filters, rootFormId, dashboardSlug }) => {
  const { language } = store.useState((s) => s);
  const text = uiText[language.active];

  if (!widgets || widgets.length === 0) {
    return (
      <div className="dashboard-view-empty">{text.dashboardViewEmpty}</div>
    );
  }

  return (
    <div className="dashboard-view-grid">
      {widgets.map((widget) => (
        <DashboardWidgetCell
          key={widget.id}
          widget={widget}
          filters={filters}
          rootFormId={rootFormId}
          dashboardSlug={dashboardSlug}
          text={text}
        />
      ))}
    </div>
  );
};

DashboardGrid.propTypes = {
  widgets: PropTypes.array,
  filters: PropTypes.object,
  rootFormId: PropTypes.number,
  dashboardSlug: PropTypes.string,
};

export default DashboardGrid;
