import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { MapCluster } from "akvo-charts";
import "leaflet/dist/leaflet.css";
import { geo } from "../../../lib";

const DEFAULT_COLOR = "#1890ff";
const NO_STATUS_COLOR = "#999";

const VizMap = ({ config, data }) => {
  const widgetConfig = config?.config || {};
  const statusColors = useMemo(
    () => widgetConfig.status_colors || {},
    [widgetConfig.status_colors]
  );
  const chartColors = useMemo(
    () => widgetConfig.chart_colors || [],
    [widgetConfig.chart_colors]
  );
  const fallback = chartColors[0] || DEFAULT_COLOR;

  const colorForStatus = useMemo(() => {
    const rows = Array.isArray(data) ? data : [];
    const statuses = [...new Set(rows.map((r) => r.status).filter(Boolean))];
    const lookup = {};
    statuses.forEach((s, i) => {
      lookup[s] =
        statusColors[s] || chartColors[i % chartColors.length] || fallback;
    });
    return lookup;
  }, [data, statusColors, chartColors, fallback]);

  const points = useMemo(() => {
    const rows = Array.isArray(data) ? data : [];
    return rows.filter(geo.hasValidPoint).map((row) => ({
      id: row.id,
      point: row.geo,
      label: row.name,
      status: row.status,
      color: row.status ? colorForStatus[row.status] || fallback : fallback,
    }));
  }, [data, colorForStatus, fallback]);

  const center = useMemo(() => geo?.defaultPos?.()?.coordinates || [0, 0], []);

  const legendEntries = Object.keys(colorForStatus);
  const uniqueColors = new Set(Object.values(colorForStatus));
  const showLegend = legendEntries.length > 0 && uniqueColors.size > 1;

  const colorKey = Object.values(statusColors).join(",") + fallback;

  return (
    <div className="dashboard-view-map">
      <MapCluster
        key={colorKey}
        data={points}
        groupKey="status"
        type="circle"
        config={{ center, zoom: 5, height: "100%", width: "100%" }}
        tile={geo.tile}
        renderPopup={(point) => point?.label}
      />
      {showLegend && (
        <div className="dashboard-view-map-legend">
          {legendEntries.map((status) => (
            <span key={status} className="dashboard-view-map-legend-item">
              <span
                className="dashboard-view-map-legend-dot"
                style={{
                  background: colorForStatus[status] || NO_STATUS_COLOR,
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
