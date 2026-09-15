import React, { useCallback, useEffect, useMemo, useRef } from "react";
import PropTypes from "prop-types";
import { MapCluster } from "akvo-charts";
import "leaflet/dist/leaflet.css";
import { scaleQuantize, scaleThreshold } from "d3-scale";
import { geo, config as appConfig } from "../../../lib";
import GradationLegend from "../../map-view/GradationLegend";

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

/**
 * What a quantity circle prints inside itself.
 *
 * akvo-charts' default shortens thousands and up but returns anything
 * under 1,000 verbatim — fine while a circle only ever held a sum, which
 * is whole. `aggregate="average"` divides, so 11/3 arrived as
 * 3.6666666666 inside a 40px circle.
 *
 * Two decimals, trailing zeros dropped by parseFloat, so 3.67 and 2.5
 * and 7 all read as themselves. The K/M/B thresholds mirror the
 * library's, because replacing formatValue replaces it wholesale —
 * there is no way to keep the default for the range it gets right.
 */
const formatMapValue = (n) => {
  const value = Number(n) || 0;
  const abs = Math.abs(value);
  if (abs >= 1e9) {
    return `${parseFloat((value / 1e9).toFixed(1))}B`;
  }
  if (abs >= 1e6) {
    return `${parseFloat((value / 1e6).toFixed(1))}M`;
  }
  if (abs >= 1e3) {
    return `${parseFloat((value / 1e3).toFixed(1))}K`;
  }
  return `${parseFloat(value.toFixed(2))}`;
};

const VizMap = ({ config, data }) => {
  const widgetConfig = config?.config || {};
  // A map bound to a NUMBER question sizes its circles by the answer
  // instead of colouring them by a status. The two are mutually
  // exclusive because a number has no options to colour by, which is
  // exactly why picking one used to do nothing at all: `status_colors`
  // came back empty and the question was never asked about again.
  const isQuantity = widgetConfig.map_mode === QUANTITY;
  const isRange = widgetConfig.map_mode === RANGE;
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

  const valueRanges = useMemo(
    () => widgetConfig.value_ranges || [],
    [widgetConfig.value_ranges]
  );

  // When the author has set value_ranges with thresholds, use those
  // directly. Otherwise fall back to auto-computed bins from chartColors.
  const hasCustomRanges =
    isRange && valueRanges.length > 1 && valueRanges.some((b) => b.to !== null);

  // Schemes are dark-to-light; reverse for graduated maps (low = light).
  const gradientPalette = useMemo(() => {
    if (hasCustomRanges) {
      return valueRanges.map((b) => b.color || fallback);
    }
    if (chartColors.length >= 5) {
      return [...chartColors.slice(0, 5)].reverse();
    }
    return appConfig.mapConfig.colorRange;
  }, [chartColors, hasCustomRanges, valueRanges, fallback]);

  const colorScale = useMemo(() => {
    if (!isRange) {
      return null;
    }
    if (hasCustomRanges) {
      const domain = valueRanges.filter((b) => b.to !== null).map((b) => b.to);
      const colors = valueRanges.map((b) => b.color || fallback);
      return scaleThreshold().domain(domain).range(colors);
    }
    const rows = Array.isArray(data) ? data : [];
    const numericValues = rows
      .map((r) => Number(r.value))
      .filter((v) => Number.isFinite(v) && v > 0);
    if (numericValues.length === 0) {
      return scaleQuantize().domain([0, 1]).range(gradientPalette);
    }
    const maxValue = Math.max(...numericValues);
    let domainMax = maxValue;
    if (maxValue <= 10) {
      domainMax = Math.ceil(maxValue / 5) * 5;
    } else if (maxValue <= 100) {
      domainMax = Math.ceil(maxValue / 10) * 10;
    } else {
      domainMax = Math.ceil(maxValue / 50) * 50;
    }
    return scaleQuantize().domain([0, domainMax]).range(gradientPalette);
  }, [data, isRange, hasCustomRanges, valueRanges, fallback, gradientPalette]);

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
      // the band is the whole message. The scale falls back rather than
      // treating a missing answer as zero: on a map of population served,
      // "not reported" and "nobody" are different facts.
      color: isRange
        ? Number.isFinite(Number(row.value))
          ? colorScale(Number(row.value))
          : fallback
        : row.status
        ? colorForStatus[row.status] || fallback
        : fallback,
    }));
  }, [data, colorForStatus, fallback, isRange, colorScale]);

  const mapRef = useRef(null);

  const pos = useMemo(
    () => geo.boundsFromPoints(points.map((p) => p.point)),
    [points]
  );

  const fitMap = useCallback(() => {
    const map = mapRef.current?.getMap?.();
    if (map && points.length > 0) {
      map.fitBounds(pos.bbox, { maxZoom: 14, padding: [20, 20] });
    }
  }, [pos, points.length]);

  useEffect(() => {
    fitMap();
  }, [fitMap]);

  const legendEntries = Object.keys(colorForStatus).map((status) => ({
    key: status,
    color: colorForStatus[status],
  }));
  const uniqueColors = new Set(legendEntries.map((e) => e.color));
  const showCategoryLegend =
    !isQuantity &&
    !isRange &&
    legendEntries.length > 0 &&
    uniqueColors.size > 1;

  const thresholds = useMemo(() => {
    if (!colorScale) {
      return [];
    }
    if (hasCustomRanges) {
      return colorScale.domain();
    }
    return colorScale.thresholds();
  }, [colorScale, hasCustomRanges]);
  const showGradationLegend =
    isRange && thresholds.length > 0 && points.length > 0;

  const colorKey =
    Object.values(statusColors).join(",") +
    fallback +
    (widgetConfig.map_mode || "category") +
    (widgetConfig.map_aggregate || "sum") +
    thresholds.join(",") +
    gradientPalette.join(",") +
    valueRanges.map((b) => `${b.to}:${b.color}`).join(",");

  return (
    <div className="dashboard-view-map">
      <MapCluster
        key={colorKey}
        ref={mapRef}
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
              formatValue: formatMapValue,
            }
          : { groupKey: "status" })}
        {...(isRange ? { cluster: false } : {})}
        config={{
          center: pos.coordinates,
          zoom: 5,
          height: "100%",
          width: "100%",
        }}
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
      {showGradationLegend && !hasCustomRanges && (
        <div className="dashboard-view-map-gradation">
          <GradationLegend thresholds={thresholds} colors={gradientPalette} />
        </div>
      )}
      {showGradationLegend && hasCustomRanges && (
        <div className="dashboard-view-map-gradation">
          <div className="shape-legend">
            <div className="legend-wrap" style={{ display: "flex" }}>
              {valueRanges.map((band, idx) => (
                <div
                  key={idx}
                  className="legend-item"
                  style={{
                    flex: 1,
                    backgroundColor: band.color || fallback,
                    textAlign: "center",
                    padding: "2px 0",
                    margin: "0 1px",
                    fontSize: 12,
                    fontWeight: 500,
                  }}
                >
                  {band.to === null
                    ? `Above ${valueRanges[idx - 1]?.to ?? 0}`
                    : idx === 0
                    ? `0 – ${band.to}`
                    : `${valueRanges[idx - 1]?.to ?? 0} – ${band.to}`}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      {showCategoryLegend && (
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
