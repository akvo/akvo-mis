import React from "react";
import { useParams } from "react-router-dom";

const DashboardBuilder = () => {
  const { slug } = useParams();
  return (
    <div style={{ padding: 40, textAlign: "center", color: "#8a93a0" }}>
      <h2>Dashboard Builder</h2>
      <p>
        Builder for <strong>{slug}</strong> will be implemented in VIZ-006.
      </p>
    </div>
  );
};

export default DashboardBuilder;
