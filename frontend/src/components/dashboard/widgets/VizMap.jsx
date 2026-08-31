import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { MapCluster } from "akvo-charts";
import "leaflet/dist/leaflet.css";
import { geo } from "../../../lib";

// =========================================================
// The map widget — akvo-charts MapCluster over Leaflet
// =========================================================
//
// VIZ-006 shipped this as a hand-drawn SVG with six hardcoded pin
// positions, standing in until the data layer existed. It placed points at
// fixed percentages of the container and silently dropped everything past
// the sixth, which is wrong in a way a viewer cannot detect.
//
// Two integration details the package does not handle:
//
//  - `type="circle"` rather than the default cluster type. The default
//    renders leaflet.markercluster's own icons, whose stylesheet lives in
//    akvo-charts' nested node_modules and does not resolve from
//    application code. The circle type draws a self-contained inline SVG
//    donut segmented by `groupKey` — dependency-free, and closer to the
//    mockup, where a cluster should show its status mix.
//  - `.custom-marker` gets its rules from viewer.scss. MapCluster's
//    default marker is an empty <span> carrying only an inline
//    background-color and border; the package ships no rule for the class
//    it puts on it.
//
// The imported leaflet.css is the app's own 1.7.1 while MapCluster runs
// its nested 1.9.4. The container, pane and control rules this needs are
// unchanged between the two.

const DEFAULT_COLOR = "#64A73B";
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
  const statusColors = useMemo(
    () => config?.config?.status_colors || {},
    [config]
  );
  const fallback = config?.color || DEFAULT_COLOR;

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
