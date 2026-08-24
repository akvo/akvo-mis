import React, { memo, useCallback, useMemo, useRef } from "react";
import PropTypes from "prop-types";
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import WidgetRenderer from "../../components/dashboard/widgets/WidgetRenderer";
import getSampleData from "./sampleWidgetData";
import { TYPE_LABELS } from "./builderConstants";

const CanvasWidgetCard = memo(
  ({
    widget,
    index,
    isSelected,
    onSelect,
    onMove,
    onDelete,
    onDragStart,
    onDragOver,
    onDrop,
  }) => {
    const sampleData = useMemo(() => getSampleData(widget.type), [widget.type]);

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
        <div className="builder-widget-body">
          <WidgetRenderer widget={widget} data={sampleData} />
        </div>
      </div>
    );
  }
);

CanvasWidgetCard.displayName = "CanvasWidgetCard";

CanvasWidgetCard.propTypes = {
  widget: PropTypes.object.isRequired,
  index: PropTypes.number.isRequired,
  isSelected: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
  onMove: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onDragStart: PropTypes.func.isRequired,
  onDragOver: PropTypes.func.isRequired,
  onDrop: PropTypes.func.isRequired,
};

const BuilderCanvas = ({
  widgets,
  selectedId,
  dashboardName,
  dashboardDesc,
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
        <div className="builder-canvas-filters">
          <span className="builder-filter-chip">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
              <rect
                x="3"
                y="4"
                width="18"
                height="17"
                rx="2"
                stroke="#a7aeb8"
                strokeWidth="1.6"
              />
              <path
                d="M3 9h18M8 2v4M16 2v4"
                stroke="#a7aeb8"
                strokeWidth="1.6"
              />
            </svg>
            Monitoring period
          </span>
          <span className="builder-filter-chip">
            Location
            <svg width="10" height="7" viewBox="0 0 10 7">
              <path
                d="M1 1l4 4 4-4"
                stroke="#a7aeb8"
                strokeWidth="1.4"
                fill="none"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span className="builder-filter-chip builder-filter-chip--right">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
              <path
                d="M3 5h18l-7 8v5l-4 2v-7L3 5z"
                stroke="#a7aeb8"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
            </svg>
            Filters
          </span>
        </div>

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
  onSelect: PropTypes.func.isRequired,
  onDeselect: PropTypes.func.isRequired,
  onMove: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onReorder: PropTypes.func.isRequired,
};

export default BuilderCanvas;
