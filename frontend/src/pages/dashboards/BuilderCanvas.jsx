import React, { memo, useCallback, useRef } from "react";
import PropTypes from "prop-types";
import { Button, Skeleton } from "antd";
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import WidgetRenderer from "../../components/dashboard/widgets/WidgetRenderer";
import useWidgetData from "../../util/hooks/useWidgetData";
import DashboardViewFilters from "../../components/dashboard/DashboardViewFilters";
import { WIDGET_BODY_HEIGHT } from "../../components/dashboard/widgetLayout";
import { TYPE_LABELS, NEEDS_FORM } from "./builderConstants";

// The canvas fetches through the same hook as the viewer and the preview.
// It used to render a hardcoded array keyed on widget.type, which meant a
// bar chart showed the same four invented categories whatever question it
// was pointed at, and changing that question produced no request and no
// visible change. A chart of plausible numbers for the wrong question is
// worse than no chart at all — see VIZ-006's opening note.
//
// What stays different from the viewer's cell is the chrome: the canvas
// draws its own header, actions and heights, because it is an editing
// surface. Only the body is shared.
const CanvasWidgetCard = memo(
  ({
    widget,
    index,
    filters,
    rootFormId,
    isSelected,
    onSelect,
    onMove,
    onDelete,
    onDragStart,
    onDragOver,
    onDrop,
  }) => {
    const { data, renderWidget, loading, error, refetch } = useWidgetData(
      widget,
      filters,
      { rootFormId }
    );

    const body = () => {
      // Before anything else: a widget still being configured has no data
      // source, so there is nothing to ask for and nothing honest to draw.
      // Saying so is the point — this is where the author is told what the
      // widget still needs.
      if (NEEDS_FORM.has(widget.type) && !widget.form) {
        return (
          <div className="builder-widget-note">
            Choose a data source in the panel on the right.
          </div>
        );
      }
      if (loading) {
        return <Skeleton active paragraph={{ rows: 2 }} />;
      }
      if (error) {
        return (
          <div className="builder-widget-note">
            <div>Could not load this widget&apos;s data.</div>
            <Button type="link" size="small" onClick={refetch}>
              Retry
            </Button>
          </div>
        );
      }
      // An empty successful response reaches the renderer, which shows its
      // own "No data". Under current_state, sites never monitored are
      // excluded unless include_unmonitored is set, so empty is a routine
      // answer rather than a fault.
      return <WidgetRenderer widget={renderWidget || widget} data={data} />;
    };

    return (
      <div
        className={`builder-widget-card${
          isSelected ? " builder-widget-card--selected" : ""
        }`}
        style={{ gridColumn: `span ${widget.col_span || 24}` }}
        draggable
        onClick={(e) => {
          e.stopPropagation();
          onSelect(widget.id);
        }}
        onDragStart={(e) => onDragStart(e, index)}
        onDragOver={onDragOver}
        onDrop={(e) => onDrop(e, index)}
      >
        <div className="builder-widget-header">
          <div className="builder-widget-title">
            {widget.title || "Untitled"}
          </div>
          <div className="builder-widget-actions">
            <span className="builder-widget-type-label">
              {TYPE_LABELS[widget.type] || widget.type}
            </span>
            <button
              className="builder-widget-btn"
              title="Move up"
              onClick={(e) => {
                e.stopPropagation();
                onMove(index, -1);
              }}
            >
              <ArrowUpOutlined />
            </button>
            <button
              className="builder-widget-btn"
              title="Move down"
              onClick={(e) => {
                e.stopPropagation();
                onMove(index, 1);
              }}
            >
              <ArrowDownOutlined />
            </button>
            <button
              className="builder-widget-btn builder-widget-btn--danger"
              title="Delete"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(widget.id);
              }}
            >
              <DeleteOutlined />
            </button>
          </div>
        </div>
        <div
          className="builder-widget-body"
          // The same per-type height the viewer uses. Without it the
          // canvas card grew around App.scss's global 500px chart and the
          // author reviewed a taller chart than anyone else would see.
          style={
            WIDGET_BODY_HEIGHT[widget.type]
              ? { height: WIDGET_BODY_HEIGHT[widget.type] }
              : {}
          }
        >
          {body()}
        </div>
      </div>
    );
  }
);

CanvasWidgetCard.displayName = "CanvasWidgetCard";

CanvasWidgetCard.propTypes = {
  widget: PropTypes.object.isRequired,
  index: PropTypes.number.isRequired,
  filters: PropTypes.object,
  rootFormId: PropTypes.number,
  isSelected: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
  onMove: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onDragStart: PropTypes.func.isRequired,
  onDragOver: PropTypes.func.isRequired,
  onDrop: PropTypes.func.isRequired,
};

const noop = () => {};

const BuilderCanvas = ({
  widgets,
  selectedId,
  dashboardName,
  dashboardDesc,
  filters,
  rootFormId,
  defaultFilters,
  onSelect,
  onDeselect,
  onMove,
  onDelete,
  onReorder,
}) => {
  const dragIndex = useRef(null);

  const handleDragStart = useCallback((e, idx) => {
    dragIndex.current = idx;
    e.dataTransfer.effectAllowed = "move";
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const handleDrop = useCallback(
    (e, toIdx) => {
      e.preventDefault();
      const fromIdx = dragIndex.current;
      if (fromIdx !== null && fromIdx !== toIdx) {
        onReorder(fromIdx, toIdx);
      }
      dragIndex.current = null;
    },
    [onReorder]
  );

  const handleCanvasClick = useCallback(
    (e) => {
      if (e.target === e.currentTarget) {
        onDeselect();
      }
    },
    [onDeselect]
  );

  return (
    <div className="builder-canvas" onClick={handleCanvasClick}>
      <div className="builder-canvas-inner">
        {/* The viewer's own filter bar, inert. It used to be three
            hand-drawn chips that only resembled it; the moment the real
            bar was restyled to match Manage Data the two drifted apart,
            which is exactly what a look-alike guarantees. The canvas is
            unfiltered by design, so the controls are disabled rather than
            wired. */}
        <DashboardViewFilters
          defaultFilters={defaultFilters}
          value={filters}
          onChange={noop}
          disabled
        />

        <div className="builder-canvas-title">{dashboardName}</div>
        <div className="builder-canvas-desc">{dashboardDesc}</div>

        {widgets.length === 0 ? (
          <div className="builder-canvas-empty">
            <div className="builder-canvas-empty-icon">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 5v14M5 12h14"
                  stroke="#1651b6"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <div className="builder-canvas-empty-title">
              Your canvas is empty
            </div>
            <div className="builder-canvas-empty-sub">
              Add a widget from the left panel to start building.
            </div>
          </div>
        ) : (
          <div className="builder-canvas-grid">
            {widgets.map((w, idx) => (
              <CanvasWidgetCard
                key={w.id}
                widget={w}
                index={idx}
                filters={filters}
                rootFormId={rootFormId}
                isSelected={w.id === selectedId}
                onSelect={onSelect}
                onMove={onMove}
                onDelete={onDelete}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

BuilderCanvas.propTypes = {
  widgets: PropTypes.array.isRequired,
  selectedId: PropTypes.number,
  dashboardName: PropTypes.string,
  dashboardDesc: PropTypes.string,
  filters: PropTypes.object,
  rootFormId: PropTypes.number,
  defaultFilters: PropTypes.object,
  onSelect: PropTypes.func.isRequired,
  onDeselect: PropTypes.func.isRequired,
  onMove: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onReorder: PropTypes.func.isRequired,
};

export default BuilderCanvas;
