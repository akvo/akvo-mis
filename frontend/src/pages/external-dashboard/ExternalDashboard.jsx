import React from "react";
import "./style.scss";

const ExternalDashboard = () => {
  return (
    <div className="external-dashboard-container">
      <iframe
        src="https://rmi-mohhs.data.akvotest.org/"
        title="RMI Dashboard"
        className="external-dashboard-iframe"
      />
    </div>
  );
};

export default ExternalDashboard;
