/* global L */
import React, { useCallback, useEffect, useRef } from "react";
import { Button, Space } from "antd";
import { Map } from "akvo-charts";
import { store, geo, config } from "../../lib";

import {
  ZoomInOutlined,
  ZoomOutOutlined,
  FullscreenOutlined,
} from "@ant-design/icons";
import "./style.scss";
import { buildOffsetCoordinates } from "./overlapUtils";

const MapView = ({ dataset, loading, position }) => {
  const selectedForm = store.useState((s) => s.selectedForm);

  const mapInstance = useRef(null);
  const lg = useRef(null);
  const defPos = geo.defaultPos();

  const getMarkerDisplayText = useCallback((value) => {
    const isNullish = value === null || typeof value === "undefined";
    if (isNullish || isNaN(value)) {
      return "";
    }
    if (value < 1000) {
      return String(value);
    }
    const abbreviated = `${Math.floor(value / 1000)}k`;
    return abbreviated.length <= 4 ? abbreviated : "…";
  }, []);

  const renderMarker = useCallback(
    (d) => {
      if (d?.values?.length) {
        return `<span style="background: conic-gradient(${d.values
          .map(
            (v, i) =>
              `${v.color} ${i * (100 / d.values.length)}% ${
                (i + 1) * (100 / d.values.length)
              }%`
          )
          .join(", ")})"></span>`;
      }
      const bgColor = d?.color || "#64A73B";
      return `<span class="custom-marker" style="background-color:${bgColor};">${getMarkerDisplayText(
        d?.value
      )}</span>`;
    },
    [getMarkerDisplayText]
  );

  const initMapControls = useCallback(() => {
    const map = mapInstance.current?.getMap();
    if (map && !loading) {
      map.zoomControl.remove();
      lg.current = L.layerGroup().addTo(map);
    }
  }, [loading]);

  const fitToBounds = useCallback(() => {
    if (mapInstance.current && position?.bbox && !loading) {
      const map = mapInstance.current.getMap();
      if (map) {
        map.fitBounds(position.bbox, { maxZoom: 14, padding: [20, 20] });
      }
    }
  }, [position, loading]);

  useEffect(() => {
    fitToBounds();
  }, [fitToBounds]);

  useEffect(() => {
    initMapControls();
  }, [initMapControls]);

  useEffect(() => {
    if (lg.current && !loading) {
      lg.current.clearLayers();
    }

    return () => {
      if (lg.current) {
        lg.current.clearLayers();
        lg.current = null;
      }
    };
  }, [lg, loading]);

  useEffect(() => {
    if (lg.current && !loading) {
      lg.current.clearLayers();

      const filteredDataset = dataset.filter(
        (d) => !d?.hidden && geo.hasValidPoint(d)
      );

      const offsets = buildOffsetCoordinates(filteredDataset);

      filteredDataset.forEach((d, index) => {
        const offsetCoords = offsets[index];
        const finalCoords = geo.fixCoordinates(offsetCoords);

        const hasNumericValue =
          d?.value !== null &&
          typeof d?.value !== "undefined" &&
          !isNaN(d.value);

        const popupLink = document.createElement("a");
        popupLink.href = `/control-center/data/${encodeURIComponent(
          selectedForm
        )}/monitoring/${encodeURIComponent(d.id)}`;
        popupLink.target = "_blank";
        popupLink.rel = "noopener noreferrer";
        popupLink.style.padding = "0";
        popupLink.textContent = d.name;

        const marker = L.marker(finalCoords, {
          icon: L.divIcon({
            className: `custom-marker ${
              d?.values?.length > 1 ? "multiple-option" : ""
            }`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            html: renderMarker(d),
          }),
        }).bindPopup(popupLink);

        if (hasNumericValue) {
          marker.bindTooltip(String(d.value), {
            sticky: true,
            direction: "top",
          });
        }

        lg.current.addLayer(marker);
      });
    }
  }, [lg, selectedForm, dataset, loading, renderMarker]);

  return (
    <div className="map-container">
      <div className="map-buttons">
        <Space size="small" direction="vertical">
          <Button
            type="secondary"
            icon={<FullscreenOutlined />}
            onClick={() => {
              const maps = mapInstance.current.getMap();
              maps.fitBounds(defPos.bbox);
            }}
          />
          <Button
            type="secondary"
            icon={<ZoomOutOutlined />}
            onClick={() => {
              const currentZoom = mapInstance.current.getMap().getZoom() - 1;
              mapInstance.current.getMap().setZoom(currentZoom);
            }}
          />
          <Button
            // disabled={zoomLevel >= mapMaxZoom}
            type="secondary"
            icon={<ZoomInOutlined />}
            onClick={() => {
              const maps = mapInstance.current.getMap();
              const currentZoom = maps.getZoom() + 1;
              maps.setZoom(currentZoom);
            }}
          />
        </Space>
      </div>
      <Map.Container
        tile={geo.tile}
        config={{
          center: config.mapConfig.defaultCenter,
          zoom: 8,
          height: 600,
          width: "100%",
        }}
        ref={(el) => {
          mapInstance.current = el;
        }}
      />
    </div>
  );
};

export default MapView;
