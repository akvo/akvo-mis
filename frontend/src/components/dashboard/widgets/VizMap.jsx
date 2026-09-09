import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { MapCluster } from "akvo-charts";
import "leaflet/dist/leaflet.css";
import { geo } from "../../../lib";

const DEFAULT_COLOR = "#1890ff";
const NO_STATUS_COLOR = "#999";

// `config.map_mode`. Absent means "category", which is every map saved
// before #382 and every map bound to an option question.
const QUANTITY = "quantity";

const VizMap = ({ config, data }) => {
  const widgetConfig = config?.config || {};
  // A map bound to a NUMBER question sizes its circles by the answer
  // instead of colouring them by a status. The two are mutually
  // exclusive because a number has no options to colour by, which is
  // exactly why picking one used to do nothing at all: `status_colors`
  // came back empty and the question was never asked about again.
  const isQuantity = widgetConfig.map_mode === QUANTITY;
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
      // Coerced here rather than left to the library. A site that did
      // not answer the question joins to nothing, and `Number(null)` is
      // 0 while `Number(undefined)` and `Number("n/a")` are NaN — which
      // would size the circle as garbage instead of drawing the small
      // circle that honestly says "no number here". Meaningless outside
      // quantity mode, and ignored there.
      value: Number(row.value) || 0,
      color: row.status ? colorForStatus[row.status] || fallback : fallback,
    }));
  }, [data, colorForStatus, fallback]);

  const center = useMemo(() => geo?.defaultPos?.()?.coordinates || [0, 0], []);

  const legendEntries = Object.keys(colorForStatus);
  const uniqueColors = new Set(Object.values(colorForStatus));
  // Never in quantity mode: size carries the meaning there and every
  // circle is one colour, so a colour legend would describe nothing
  // that is on screen.
  const showLegend =
    !isQuantity && legendEntries.length > 0 && uniqueColors.size > 1;

  // MapCluster builds its Leaflet cluster group in an effect, and a
  // Leaflet object does not follow React prop updates — so the mode
  // belongs in the remount key alongside the colours.
  const colorKey =
    Object.values(statusColors).join(",") +
    fallback +
    (isQuantity ? QUANTITY : "circle");

  return (
    <div className="dashboard-view-map">
      <MapCluster
        key={colorKey}
        data={points}
        type={isQuantity ? QUANTITY : "circle"}
        {...(isQuantity
          ? { valueKey: "value", color: fallback }
          : { groupKey: "status" })}
        config={{ center, zoom: 5, height: "100%", width: "100%" }}
        tile={geo.tile}
        // Null, not a function: MapCluster renders its own popup —
        // the label plus the exact value, unrounded — only when
        // renderPopup is absent. Supplying one here would leave the
        // compact "12K" inside the circle as the only figure on screen.
        renderPopup={isQuantity ? null : (point) => point?.label}
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
