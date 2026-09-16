import React, { useMemo } from "react";
import PropTypes from "prop-types";
import {
  MapContainer,
  TileLayer,
  Polygon,
  Polyline,
  CircleMarker,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { toPolygonPoints, polygonAreaHectares, QUESTION_TYPES } from "../lib";

const MIN_POINTS_FOR_AREA = 3;
const OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/**
 * Read-only preview of a captured geometry.
 *
 * Without this, a geoshape or geotrace answer reaches the cell as an array of
 * [lat, lng] pairs and React flattens it into one unbroken run of digits — every
 * number is there and none of them mean anything. See GEO-001 §6.8 for the mobile
 * counterpart.
 *
 * Both geometry types share everything but closure: a geoshape is a ring with an
 * enclosed area, a geotrace is an open line with neither. They are siblings in the
 * backend too (`QuestionTypes.geoshape` = 14, `geotrace` = 15).
 */
const GeometryView = ({
  value,
  type = QUESTION_TYPES.geoshape,
  height = 220,
}) => {
  const points = useMemo(() => toPolygonPoints(value), [value]);

  if (!points.length) {
    return <span>-</span>;
  }

  const isClosed = type !== QUESTION_TYPES.geotrace;
  const Shape = isClosed ? Polygon : Polyline;
  const showArea = isClosed && points.length >= MIN_POINTS_FOR_AREA;

  return (
    <div className="geometry-view">
      {/*
        Fully static: this is a preview of a saved answer, so every interaction
        handler is off. Wheel-zoom in particular would swallow the page scroll
        whenever the pointer crossed the map, and panning would let a reviewer lose
        the shape off-screen with no control to bring it back.
      */}
      <MapContainer
        bounds={points}
        boundsOptions={{ padding: [16, 16], maxZoom: 18 }}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        touchZoom={false}
        boxZoom={false}
        keyboard={false}
        zoomControl={false}
        style={{ height, width: "100%" }}
      >
        <TileLayer url={OSM_URL} attribution={OSM_ATTRIBUTION} maxZoom={19} />
        <Shape positions={points} pathOptions={{ color: "#1651b6" }} />
        {points.map(([lat, lng], index) => (
          <CircleMarker
            key={`${lat}-${lng}-${index}`}
            center={[lat, lng]}
            radius={4}
            pathOptions={{
              color: "#ffffff",
              weight: 2,
              fillColor: "#1651b6",
              fillOpacity: 1,
            }}
          />
        ))}
      </MapContainer>
      {/*
        Styled inline rather than in a page stylesheet: EditableCell renders in
        manage-data, manage-draft and RawDataTable, so page-scoped rules would apply
        in some of them and not others.
      */}
      <div
        className="geometry-summary"
        style={{ display: "flex", gap: 16, paddingTop: 4, color: "#6b7280" }}
      >
        <span>Points: {points.length}</span>
        {showArea && (
          <span>Area: {polygonAreaHectares(points).toFixed(2)} ha</span>
        )}
      </div>
    </div>
  );
};

GeometryView.propTypes = {
  value: PropTypes.oneOfType([PropTypes.array, PropTypes.string]),
  type: PropTypes.string,
  height: PropTypes.number,
};

export default GeometryView;
