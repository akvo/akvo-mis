import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { MapCluster } from "akvo-charts";
import "leaflet/dist/leaflet.css";
import { geo } from "../../../lib";
import { colorForValue, rangeLabel } from "../../../util/valueRanges";

const DEFAULT_COLOR = "#1890ff";
const NO_STATUS_COLOR = "#999";

// `config.map_mode`. Absent means "category", which is every map saved
// before #382 and every map bound to an option question.
const QUANTITY = "quantity";
// A value question's default (#387): individual points, coloured by
// which band the answer falls in. Clustering is what the author opts
// INTO, because a cluster answers "how much in total here" and hides
// the sites that a range map is read one at a time.
const RANGE = "range";

const VizMap = ({ config, data }) => {
  const widgetConfig = config?.config || {};
  // A map bound to a NUMBER question sizes its circles by the answer
  // instead of colouring them by a status. The two are mutually
  // exclusive because a number has no options to colour by, which is
  // exactly why picking one used to do nothing at all: `status_colors`
  // came back empty and the question was never asked about again.
  const isQuantity = widgetConfig.map_mode === QUANTITY;
  const isRange = widgetConfig.map_mode === RANGE;
  const valueRanges = useMemo(
    () => widgetConfig.value_ranges || [],
    [widgetConfig.value_ranges]
  );
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
      // Parsed, but never invented. A site that did not answer joins to
      // nothing, and this component must not turn that into a zero: the
      // popup would then tell a reader the site serves nobody, which is
      // a different fact from nobody having reported. MapCluster reads
      // `Number(d[valueKey]) || 0` itself, so null still draws the small
      // circle that says "no number here" — the coercion belongs there,
      // where it is about drawing, not here, where it would be a claim
      // about the data.
      value:
        Number.isFinite(Number(row.value)) && row.value !== null
          ? Number(row.value)
          : null,
      // A range map ignores status entirely — it has none to read, and
      // the band is the whole message. `colorForValue` falls back rather
      // than treating a missing answer as zero: on a map of population
      // served, "not reported" and "nobody" are different facts.
      color: isRange
        ? colorForValue(row.value, valueRanges, fallback)
        : row.status
        ? colorForStatus[row.status] || fallback
        : fallback,
    }));
  }, [data, colorForStatus, fallback, isRange, valueRanges]);

  const center = useMemo(() => geo?.defaultPos?.()?.coordinates || [0, 0], []);

  // Two legends, one shape: a status name and its colour, or a band
  // label and its colour.
  const legendEntries = isRange
    ? valueRanges.map((band, i) => ({
        key: rangeLabel(valueRanges, i),
        color: band.color,
      }))
    : Object.keys(colorForStatus).map((status) => ({
        key: status,
        color: colorForStatus[status],
      }));
  const uniqueColors = new Set(legendEntries.map((e) => e.color));
  // Never in quantity mode: size carries the meaning there and every
  // circle is one colour, so a colour legend would describe nothing
  // that is on screen. A range map with one band has nothing to
  // distinguish either — the same reason the status legend hides when
  // every pin shares a colour.
  const showLegend =
    !isQuantity && legendEntries.length > 0 && uniqueColors.size > 1;

  // MapCluster builds its Leaflet cluster group in an effect, and a
  // Leaflet object does not follow React prop updates — so the mode
  // belongs in the remount key alongside the colours.
  // Everything a mounted Leaflet object cannot pick up on its own.
  // MapCluster keys its cluster group on `type` and `cluster` only, and
  // MarkerClusterGroup captures `iconCreateFunction` at mount by design —
  // so a changed `aggregate` alone would leave the old closure summing,
  // with nothing on screen to say the switch did nothing.
  const colorKey =
    Object.values(statusColors).join(",") +
    fallback +
    (widgetConfig.map_mode || "category") +
    (widgetConfig.map_aggregate || "sum") +
    valueRanges.map((b) => `${b.to}:${b.color}`).join(",");

  return (
    <div className="dashboard-view-map">
      <MapCluster
        key={colorKey}
        data={points}
        type={isQuantity ? QUANTITY : "circle"}
        {...(isQuantity
          ? {
              valueKey: "value",
              color: fallback,
              // How a cluster combines its points. Sum is right for a
              // total and wrong for a rate — five sites at 50 l/p/d is
              // not 250 — so the author says which.
              aggregate: widgetConfig.map_aggregate || "sum",
            }
          : { groupKey: "status" })}
        {...(isRange ? { cluster: false } : {})}
        config={{ center, zoom: 5, height: "100%", width: "100%" }}
        tile={geo.tile}
        // Null, not a function: MapCluster renders its own popup —
        // the label plus the exact value, unrounded — only when
        // renderPopup is absent. Supplying one here would leave the
        // compact "12K" inside the circle as the only figure on screen.
        renderPopup={
          isQuantity
            ? null
            : isRange
            ? (point) => (
                <>
                  {point?.label}
                  <br />
                  <strong>
                    {point?.value === null ||
                    typeof point?.value === "undefined"
                      ? "No value"
                      : Number(point.value).toLocaleString()}
                  </strong>
                </>
              )
            : (point) => point?.label
        }
      />
      {showLegend && (
        <div className="dashboard-view-map-legend">
          {legendEntries.map((entry) => (
            <span key={entry.key} className="dashboard-view-map-legend-item">
              <span
                className="dashboard-view-map-legend-dot"
                style={{ background: entry.color || NO_STATUS_COLOR }}
              />
              {entry.key}
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
