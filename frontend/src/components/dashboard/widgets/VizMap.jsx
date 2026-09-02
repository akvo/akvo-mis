import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { MapCluster } from "akvo-charts";
import "leaflet/dist/leaflet.css";
import { geo } from "../../../lib";

const DEFAULT_COLOR = "#1890ff";
const NO_STATUS_COLOR = "#999";

const OSM_TILE = {
  url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
};

const VizMap = ({ config, data }) => {
  // Memoised, not just destructured: `|| {}` mints a fresh object on every
  // render, which would make the points memo below recompute every time and
  // hand MapCluster a new data array — remounting every marker.
  const widgetConfig = config?.config || {};
  const statusColors = useMemo(
    () => widgetConfig.status_colors || {},
    [widgetConfig.status_colors]
  );
  const fallback = (widgetConfig.chart_colors || [])[0] || DEFAULT_COLOR;

  const points = useMemo(() => {
    const rows = Array.isArray(data) ? data : [];
    return (
      rows
        // A datapoint with no geo is not a point. Rendering it at [0, 0]
        // would put a site in the Gulf of Guinea.
        .filter((row) => Array.isArray(row?.geo) && row.geo.length === 2)
        .map((row) => ({
          id: row.id,
          // /maps/geolocation returns geo as [lat, lng], which is what
          // Leaflet wants — no reordering.
          point: row.geo,
          label: row.name,
          status: row.status,
          color: row.status ? statusColors[row.status] || fallback : fallback,
        }))
    );
  }, [data, statusColors, fallback]);

  const center = useMemo(() => geo?.defaultPos?.()?.coordinates || [0, 0], []);

  const legend = Object.keys(statusColors);

  return (
    <div className="dashboard-view-map">
      <MapCluster
        data={points}
        groupKey="status"
        type="circle"
        config={{ center, zoom: 5, height: "100%", width: "100%" }}
        tile={OSM_TILE}
        renderPopup={(point) => point?.label}
      />
      {/* Overlaid rather than drawn inside the chart, which is why it is
          this component's job and not akvo-charts'. */}
      {legend.length > 0 && (
        <div className="dashboard-view-map-legend">
          {legend.map((status) => (
            <span key={status} className="dashboard-view-map-legend-item">
              <span
                className="dashboard-view-map-legend-dot"
                style={{
                  background: statusColors[status] || NO_STATUS_COLOR,
                }}
              />
              {status}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

VizMap.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizMap;
