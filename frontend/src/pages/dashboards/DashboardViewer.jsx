import React from "react";
import { useParams } from "react-router-dom";

const DashboardViewer = () => {
  const { slug } = useParams();
  return (
    <div style={{ padding: 40, textAlign: "center", color: "#8a93a0" }}>
      <h2>Dashboard Viewer</h2>
      <p>
        Viewer for <strong>{slug}</strong> will be implemented in VIZ-008.
      </p>
    </div>
  );
};

export default DashboardViewer;
